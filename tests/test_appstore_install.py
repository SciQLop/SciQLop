"""AppStore plugin install behind a corporate HTTP proxy.

Two regressions guarded here:

1. ``--native-tls`` — corporate proxies MITM HTTPS with a private root CA that
   lives in the OS certificate store but not in uv's bundled bundle. Without
   ``--native-tls`` uv rejects the intercepted certificate and the install
   fails. The flag makes uv trust the platform store (and the corporate CA).

2. Error visibility — a failed ``uv pip install`` raises ``CalledProcessError``,
   whose ``str()`` is only "Command '…' returned non-zero exit status 1." The
   real cause (proxy/TLS/auth) is in ``.stderr``; the appstore must surface it
   instead of a bare "Failed", otherwise the failure is undiagnosable.
"""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

import SciQLop
from SciQLop.components.appstore.backend import (
    AppStoreBackend,
    _remove_installed_package,
    _save_installed_package,
    _try_load_plugin,
    _uv_install_cmd,
    _uv_uninstall_cmd,
    _write_requirements_file,
)
from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
from SciQLop.components.workspaces.backend.uv import find_uv


@pytest.mark.skipif(find_uv() is None, reason="uv binary not available")
class TestNativeTls:
    def test_install_cmd_requests_native_tls(self):
        cmd = _uv_install_cmd("some-plugin==1.2.3")
        assert "--native-tls" in cmd
        assert cmd[-1] == "some-plugin==1.2.3"

    def test_uninstall_cmd_requests_native_tls(self):
        cmd = _uv_uninstall_cmd("some-plugin")
        assert "--native-tls" in cmd
        assert cmd[-1] == "some-plugin"


@pytest.mark.skipif(find_uv() is None, reason="uv binary not available")
class TestHostIsolation:
    """The appstore install must not pull host-provided packages (SciQLop and
    the pinned base stack) from PyPI. A plugin wheel declares
    ``Requires-Dist: SciQLop>=X``; without an override uv resolves it against
    PyPI and drags a mismatched SciQLop + pyside6/speasy/shiboken6 into the
    workspace venv — the failure a user hit installing onto a 0.12.1.dev0 build.
    """

    def test_install_cmd_passes_override_and_constraint(self):
        cmd = _uv_install_cmd(
            "some-plugin==1.2.3",
            override_file="/tmp/overrides.txt",
            constraint_file="/tmp/constraints.txt",
        )
        assert cmd[cmd.index("--override") + 1] == "/tmp/overrides.txt"
        assert cmd[cmd.index("--constraint") + 1] == "/tmp/constraints.txt"
        # The package spec must stay last so uv treats it as the install target.
        assert cmd[-1] == "some-plugin==1.2.3"

    def test_install_cmd_omits_flags_when_no_files(self):
        cmd = _uv_install_cmd("some-plugin==1.2.3")
        assert "--override" not in cmd
        assert "--constraint" not in cmd


class TestWriteRequirementsFile:
    def test_returns_none_for_empty_lines(self):
        with tempfile.TemporaryDirectory() as d:
            assert _write_requirements_file(d, "x.txt", []) is None

    def test_writes_file_and_returns_path(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_requirements_file(d, "overrides.txt", ["sciqlop ; python_version < '0'"])
            assert path is not None
            assert Path(path).read_text() == "sciqlop ; python_version < '0'\n"


@pytest.fixture
def tmp_config_dir(tmp_path):
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path)):
        yield tmp_path


def _write_legacy_yaml(display_name: str, dist_name: str, pip_spec: str) -> None:
    with open(SciQLopPluginsSettings.config_file(), "w") as f:
        yaml.safe_dump({
            "installed_packages": {display_name: {"pip": pip_spec, "name": dist_name}},
        }, f)


class TestInstalledPackagesStableKeys:
    """A store rename must not orphan the installed-package record: it used
    to be keyed by the store's human display name, so `_remove_installed_package`
    (given the dist name) popped nothing and the old wheel kept re-syncing on
    every launch after "uninstall". Keying by canonical distribution name
    fixes both the fresh-install path and legacy YAML written before the fix.
    """

    def test_legacy_display_name_key_is_rekeyed_on_load(self, tmp_config_dir):
        _write_legacy_yaml("My Cool Plugin", "my_cool_plugin", "my_cool_plugin==1.0.0")

        settings = SciQLopPluginsSettings()

        assert "My Cool Plugin" not in settings.installed_packages
        assert settings.installed_packages["my-cool-plugin"].pip == "my_cool_plugin==1.0.0"

    def test_remove_by_dist_name_drops_legacy_keyed_entry(self, tmp_config_dir):
        _write_legacy_yaml("My Cool Plugin", "my_cool_plugin", "my_cool_plugin==1.0.0")

        _remove_installed_package("my_cool_plugin")

        assert SciQLopPluginsSettings().installed_packages == {}

    def test_save_then_remove_round_trip_by_dist_name(self, tmp_config_dir):
        _save_installed_package("some-plugin==2.0.0", "some_plugin")
        assert "some-plugin" in SciQLopPluginsSettings().installed_packages

        _remove_installed_package("Some_Plugin")

        assert SciQLopPluginsSettings().installed_packages == {}

    def test_duplicate_canonical_key_keeps_the_canonical_keyed_entry(self, tmp_config_dir):
        """A store rename can leave a stale display-name entry sitting next
        to a fresh, canonical-keyed one for the same dist. Both canonicalise
        to the same key; healing must not pick whichever happens to iterate
        last -- ConfigEntry.save() dumps with sort_keys=True (the default),
        so on-disk order is alphabetical by the OLD key, not write order, and
        can't be used to tell which entry is "freshest". The canonical-keyed
        entry was written by this fixed code, so it wins regardless of where
        it lands alphabetically -- the display name below is chosen to sort
        *after* the canonical key, which would flip the outcome under plain
        last-wins.
        """
        with open(SciQLopPluginsSettings.config_file(), "w") as f:
            yaml.safe_dump({
                "installed_packages": {
                    "my-cool-plugin": {"pip": "my_cool_plugin==2.0.0", "name": "my_cool_plugin"},
                    "zz-legacy-display-name": {"pip": "my_cool_plugin==1.0.0", "name": "my_cool_plugin"},
                },
            }, f)

        settings = SciQLopPluginsSettings()

        assert list(settings.installed_packages.keys()) == ["my-cool-plugin"]
        assert settings.installed_packages["my-cool-plugin"].pip == "my_cool_plugin==2.0.0"


class TestTryLoadPluginSettingsBookkeeping:
    """Compatibility must never affect enable/disable state -- the settings
    entry for a freshly-installed entry-point plugin must exist regardless of
    whether the host gate skips loading it (mirrors load_all, which creates
    the entry unconditionally before gating)."""

    def test_incompatible_plugin_still_gets_a_settings_entry_but_does_not_load(
        self, tmp_config_dir, monkeypatch
    ):
        monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")

        ep = SimpleNamespace(
            name="future_plugin",
            dist=SimpleNamespace(name="future-plugin", requires=["SciQLop>=0.20"]),
        )
        monkeypatch.setattr("importlib.metadata.entry_points", lambda group=None: [ep])
        monkeypatch.setattr(
            "SciQLop.core.sciqlop_application.sciqlop_app",
            lambda: SimpleNamespace(main_window=object()),
        )
        loaded = []
        monkeypatch.setattr(
            "SciQLop.components.plugins.backend.loader.loader._load_entry_point_plugin",
            lambda ep, main_window: loaded.append(ep.name),
        )

        reason = _try_load_plugin("future-plugin")

        assert "future_plugin" in SciQLopPluginsSettings().plugins
        assert loaded == []
        # I1: the caller (AppStoreBackend._do_hot_load) needs this to tell
        # the store the wheel installed but was not actually loaded.
        assert reason is not None
        assert "SciQLop" in reason

    def test_compatible_plugin_loads_and_returns_none(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")

        ep = SimpleNamespace(
            name="ok_plugin",
            dist=SimpleNamespace(name="ok-plugin", requires=["SciQLop>=0.13.0,<0.14.0"]),
        )
        monkeypatch.setattr("importlib.metadata.entry_points", lambda group=None: [ep])
        monkeypatch.setattr(
            "SciQLop.core.sciqlop_application.sciqlop_app",
            lambda: SimpleNamespace(main_window=object()),
        )
        loaded = []
        monkeypatch.setattr(
            "SciQLop.components.plugins.backend.loader.loader._load_entry_point_plugin",
            lambda ep, main_window: loaded.append(ep.name),
        )

        reason = _try_load_plugin("ok-plugin")

        assert loaded == ["ok_plugin"]
        assert reason is None


class TestDoHotLoadPayload:
    """I1: the store used to report `ok: true` immediately, before the
    hot-load's compat gate even ran -- a gated wheel looked like a
    successful install with no way to tell the user it silently didn't
    load. `_do_hot_load` (the GUI-thread slot the worker thread's install
    hands off to) now builds the `install_finished` payload itself, after
    attempting the hot-load, so it can carry `loaded`/`reason`."""

    def test_gated_plugin_payload_carries_loaded_false_and_a_reason(self, monkeypatch):
        monkeypatch.setattr(
            "SciQLop.components.appstore.backend._try_load_plugin",
            lambda dist_name: "requires SciQLop >=0.20 but host is 0.13.0.dev0",
        )
        backend = AppStoreBackend()
        received = []
        backend.install_finished.connect(lambda payload: received.append(json.loads(payload)))

        backend._do_hot_load("future-plugin", "Future Plugin", "1.2.3")

        assert received == [{
            "name": "Future Plugin",
            "ok": True,
            "version": "1.2.3",
            "loaded": False,
            "reason": "requires SciQLop >=0.20 but host is 0.13.0.dev0",
        }]

    def test_compatible_plugin_payload_carries_loaded_true(self, monkeypatch):
        monkeypatch.setattr(
            "SciQLop.components.appstore.backend._try_load_plugin",
            lambda dist_name: None,
        )
        backend = AppStoreBackend()
        received = []
        backend.install_finished.connect(lambda payload: received.append(json.loads(payload)))

        backend._do_hot_load("ok-plugin", "OK Plugin", "1.0.0")

        assert received == [{
            "name": "OK Plugin", "ok": True, "version": "1.0.0", "loaded": True,
        }]
