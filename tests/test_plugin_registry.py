"""Tests for the shared appstore-registry lookups used both by the store
page and by the launcher's best-effort plugin auto-update on a SciQLop
version change (workspace_setup._sync_appstore_plugin_pins)."""
from unittest.mock import patch

import SciQLop
from SciQLop.components.plugins.backend.settings import InstalledPackage
from SciQLop.components.plugins.plugin_registry import (
    display_name_for_dist,
    latest_compatible_pip_spec,
    resolve_plugin_updates,
)

MODULE = "SciQLop.components.plugins.plugin_registry"


def _pkg(name: str, *versions: tuple[str, str]) -> dict:
    """versions: (version, pip_spec) pairs, all declared compatible-any."""
    return {
        "name": name,
        "versions": [
            {"version": v, "sciqlop": "", "pip": pip} for v, pip in versions
        ],
    }


class TestLatestCompatiblePipSpec:
    def test_returns_none_when_dist_not_present(self):
        assert latest_compatible_pip_spec("missing", []) is None

    def test_returns_latest_versions_pip_spec(self):
        packages = [_pkg("Demo", ("1.0.0", "demo==1.0.0"), ("2.0.0", "demo==2.0.0"))]
        assert latest_compatible_pip_spec("demo", packages) == "demo==2.0.0"


class TestDisplayNameForDist:
    def test_returns_none_when_never_seen(self):
        assert display_name_for_dist("missing", []) is None

    def test_finds_name_even_via_an_older_non_latest_version(self):
        packages = [_pkg("Demo", ("1.0.0", "demo==1.0.0"), ("2.0.0", "demo==2.0.0"))]
        assert display_name_for_dist("demo", packages) == "Demo"


class TestResolvePluginUpdates:
    def test_offline_returns_none(self):
        with patch(f"{MODULE}.fetch_index", side_effect=OSError("no network")):
            assert resolve_plugin_updates({"demo": InstalledPackage(pip="demo==1.0.0", name="demo")}) is None

    def test_unchanged_pin_is_not_reported_as_an_update(self, monkeypatch):
        monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
        packages = [_pkg("Demo", ("1.0.0", "demo==1.0.0"))]
        with patch(f"{MODULE}.fetch_index", return_value=packages):
            result = resolve_plugin_updates({"demo": InstalledPackage(pip="demo==1.0.0", name="demo")})

        assert result.updates == {}
        assert result.unresolvable == []

    def test_newer_compatible_version_is_offered_as_an_update(self, monkeypatch):
        monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
        packages = [_pkg("Demo", ("1.0.0", "demo==1.0.0"), ("2.0.0", "demo==2.0.0"))]
        with patch(f"{MODULE}.fetch_index", return_value=packages):
            result = resolve_plugin_updates({"demo": InstalledPackage(pip="demo==1.0.0", name="demo")})

        assert result.updates == {"demo": "demo==2.0.0"}
        assert result.unresolvable == []

    def test_plugin_grown_incompatible_is_flagged_by_display_name(self, monkeypatch):
        """Simulates a SciQLop upgrade that leaves the installed plugin
        version's SciQLop range unsatisfied, with no newer version shipped
        yet -- the registry still lists it (so we know its display name),
        but no version is compatible with the new host."""
        monkeypatch.setattr(SciQLop, "__version__", "0.14.0")
        packages = [{
            "name": "Demo",
            "versions": [{"version": "1.0.0", "sciqlop": "<0.14.0", "pip": "demo==1.0.0"}],
        }]
        with patch(f"{MODULE}.fetch_index", return_value=packages):
            result = resolve_plugin_updates({"demo": InstalledPackage(pip="demo==1.0.0", name="demo")})

        assert result.updates == {}
        assert result.unresolvable == ["Demo"]

    def test_dist_unknown_to_the_registry_is_silently_ignored(self, monkeypatch):
        monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
        with patch(f"{MODULE}.fetch_index", return_value=[]):
            result = resolve_plugin_updates({"unrelated": InstalledPackage(pip="unrelated==1.0.0", name="unrelated")})

        assert result.updates == {}
        assert result.unresolvable == []
