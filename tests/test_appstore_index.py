"""The appstore index pass-through must preserve optional media fields.

`image` and `screenshots` are optional URL fields the client renders (card
thumbnail + screenshot carousel). `_filter_packages` only narrows `versions`;
it must keep every other key so the JS can read these. This guards against a
future refactor that whitelists keys and silently drops media.
"""
import SciQLop
from SciQLop.components.appstore.backend import _filter_packages, _is_compatible


def _entry(**extra):
    base = {
        "name": "Demo",
        "type": "plugin",
        "versions": [{"version": "1.0.0", "sciqlop": ""}],
    }
    base.update(extra)
    return base


def test_image_and_screenshots_preserved():
    pkg = _entry(
        image="https://example.com/card.png",
        screenshots=["https://example.com/01.png", "https://example.com/02.png"],
    )
    out = _filter_packages([pkg])
    assert len(out) == 1
    assert out[0]["image"] == "https://example.com/card.png"
    assert out[0]["screenshots"] == ["https://example.com/01.png", "https://example.com/02.png"]


def test_missing_media_fields_are_simply_absent():
    out = _filter_packages([_entry()])
    assert len(out) == 1
    assert "image" not in out[0]
    assert "screenshots" not in out[0]


def test_dev_build_can_install_plugin_targeting_its_release(monkeypatch):
    """On a 0.13.0.dev0 host, a plugin requiring SciQLop>=0.13.0 must show as
    compatible — otherwise the store hides it and the user can't install the
    plugin built for the very release they're running."""
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    assert _is_compatible({"sciqlop": ">=0.13.0,<0.14.0"}) is True
    assert _is_compatible({"sciqlop": ">=0.12.0,<0.13.0"}) is False
    assert _is_compatible({"sciqlop": ">=0.20"}) is False


def test_update_only_offers_compatible_versions(monkeypatch):
    """On a 0.13.0.dev0 host, an entry whose newest version needs >=0.14.0 must
    have that version filtered out, so the user is only offered the latest
    *compatible* version as an update."""
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    pkg = {
        "name": "Demo", "type": "plugin",
        "versions": [
            {"version": "1.0.0", "sciqlop": ">=0.13.0,<0.14.0"},
            {"version": "2.0.0", "sciqlop": ">=0.14.0,<0.15.0"},
        ],
    }
    out = _filter_packages([pkg])
    assert len(out) == 1
    offered = [v["version"] for v in out[0]["versions"]]
    assert offered == ["1.0.0"]


def test_filter_packages_sorts_versions_ascending():
    """The JS client reads `versions[versions.length - 1]` as the latest
    version; `versions` must come out sorted ascending so that agrees with
    the backend's own `_latest_version` (which uses `max(...)`)."""
    pkg = _entry(versions=[
        {"version": "2.0.0", "sciqlop": ""},
        {"version": "10.0.0", "sciqlop": ""},
        {"version": "1.0.0", "sciqlop": ""},
    ])
    out = _filter_packages([pkg])
    assert [v["version"] for v in out[0]["versions"]] == ["1.0.0", "2.0.0", "10.0.0"]


def test_plugin_with_no_compatible_version_is_hidden(monkeypatch):
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    pkg = {
        "name": "FutureOnly", "type": "plugin",
        "versions": [{"version": "9.0.0", "sciqlop": ">=0.20"}],
    }
    assert _filter_packages([pkg]) == []
