"""A placeholder panel offers to install its plugin and becomes the real panel when the kind arrives (plan 2g §5)."""
import json
from urllib.error import URLError

import pytest

from .fixtures import *  # noqa: F401,F403 — main_window
from SciQLop.components.plugins import install_offer
from SciQLop.components.plugins.install_offer import store_entry_for_kind
from SciQLop.core.extensions import owned_by

_KIND = "absent.viewer"
_ROOT = {"kind": _KIND, "config": {"zoom": 2.5, "name": "kept", "area": "kept too"}, "slots": {}}


def _version(version, provides=None, sciqlop=""):
    v = {"version": version, "pip": f"pkg=={version}", "sciqlop": sciqlop}
    if provides is not None:
        v["provides"] = {"sciqlop.panel_kinds": provides}
    return v


def test_lookup_by_provides():
    index = [
        {"name": "Absent", "versions": [_version("1.0")]},
        {"name": "future-only", "versions": [_version("2.0", [_KIND], sciqlop=">=999")]},
        {"name": "dropped-it", "versions": [_version("1.0", [_KIND]), _version("2.0", [])]},
        {"name": "viewers", "versions": [_version("0.9", []), _version("1.0", [_KIND])]},
    ]
    assert store_entry_for_kind(_KIND, index)["name"] == "viewers"


def test_lookup_by_prefix():
    index = [
        {"name": "other", "versions": [_version("1.0", ["other.thing"])]},
        {"name": "Absent_Plugin", "versions": [_version("1.0")]},
    ]
    assert store_entry_for_kind("absent-plugin.viewer", index)["name"] == "Absent_Plugin"


def test_lookup_none():
    index = [{"name": "other", "versions": [_version("1.0")]},
             {"name": "only-future", "versions": [_version("1.0", [_KIND], sciqlop=">=999")]}]
    assert store_entry_for_kind(_KIND, index) is None
    assert store_entry_for_kind(_KIND, []) is None


@pytest.fixture
def warnings(monkeypatch):
    seen = []
    monkeypatch.setattr(install_offer.log, "warning", lambda msg, *a, **k: seen.append(msg))
    return seen


@pytest.fixture
def store(monkeypatch):
    index = [{"name": "absent", "versions": [_version("1.0")]}]
    monkeypatch.setattr(install_offer, "fetch_index", lambda *a, **k: index)
    return index


@pytest.fixture
def installs(monkeypatch):
    """The faked App Store install: records the name, then plays out `outcome` like the real hot-load path."""
    from SciQLop.components.appstore.backend import AppStoreBackend
    calls = []
    outcome = {"ok": True, "loaded": True, "restart_required": False}

    def fake_install(self, name):
        calls.append(name)
        if outcome["ok"] and not outcome["restart_required"]:
            _contribute_kind()
        self.install_finished.emit(json.dumps({"name": name, **outcome}))

    monkeypatch.setattr(AppStoreBackend, "install_package", fake_install)
    yield calls, outcome
    _withdraw_kind()


def _contribute_kind():
    from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind
    with owned_by("absent"):
        PANEL_KINDS.contribute(PanelKind(_KIND, "Viewer", create=lambda n, c: _viewer(c),
                                         to_config=lambda w: dict(w.config)))


def _withdraw_kind():
    from SciQLop.core.panel_kinds import PANEL_KINDS
    PANEL_KINDS.remove_owner("absent")


def _viewer(config):
    from PySide6.QtWidgets import QLabel
    w = QLabel("viewer")
    w.config = dict(config)
    return w


@pytest.fixture
def placeholder(main_window, qtbot):
    from SciQLop.components.plotting.ui.placeholder_panel import open_placeholder
    yield open_placeholder(main_window, json.loads(json.dumps(_ROOT)), name="io_viewer")
    for panel in [p for p in main_window.panels() if p.objectName() == "io_viewer"]:
        main_window.remove_panel(panel)
    _withdraw_kind()


def _area_of(main_window, panel):
    return main_window._dock_of(panel).dockAreaWidget()


def test_offline_shows_no_button(qtbot, monkeypatch, warnings, main_window):
    from SciQLop.components.plotting.ui.placeholder_panel import open_placeholder

    def offline(*a, **k):
        raise URLError("offline")

    monkeypatch.setattr(install_offer, "fetch_index", offline)
    panel = open_placeholder(main_window, dict(_ROOT), name="io_offline")
    try:
        qtbot.waitUntil(lambda: panel.lookup_done)
        assert panel.install_button() is None
        assert len(warnings) == 1
        assert panel in main_window.panels()
    finally:
        main_window.remove_panel(panel)


def test_install_then_swap(qtbot, main_window, store, installs, placeholder):
    calls, _ = installs
    area = _area_of(main_window, placeholder)
    qtbot.waitUntil(lambda: placeholder.install_button() is not None)
    button = placeholder.install_button()
    assert button.text() == "Install absent"
    button.click()
    assert calls == ["absent"]
    qtbot.waitUntil(lambda: placeholder not in main_window.panels())
    [real] = [p for p in main_window.panels() if p.objectName() == "io_viewer"]
    from SciQLop.core.panel_kinds import panel_kind_of
    assert panel_kind_of(real) == _KIND
    assert real.windowTitle() == "io_viewer"
    assert real.config == _ROOT["config"]
    assert _area_of(main_window, real) is area


def test_install_failure_is_shown(qtbot, main_window, store, installs, placeholder):
    calls, outcome = installs
    outcome.update(ok=False, error="boom")
    qtbot.waitUntil(lambda: placeholder.install_button() is not None)
    placeholder.install_button().click()
    qtbot.waitUntil(lambda: "boom" in placeholder.status())
    assert placeholder in main_window.panels()
    assert placeholder.install_button().isEnabled()


def test_an_install_needing_a_restart_keeps_the_button_disabled(qtbot, main_window, store, installs, placeholder):
    _, outcome = installs
    outcome.update(restart_required=True)
    qtbot.waitUntil(lambda: placeholder.install_button() is not None)
    placeholder.install_button().click()
    qtbot.waitUntil(lambda: "Restart" in placeholder.status())
    assert not placeholder.install_button().isEnabled()


def test_contribution_without_install_also_swaps(qtbot, main_window, placeholder):
    _contribute_kind()
    qtbot.waitUntil(lambda: placeholder not in main_window.panels())
    [real] = [p for p in main_window.panels() if p.objectName() == "io_viewer"]
    assert real.config == _ROOT["config"]


def test_the_swap_hands_its_name_over_and_frees_the_temporary_one(qtbot, main_window, placeholder):
    from SciQLop.core import unique_names
    _contribute_kind()
    qtbot.waitUntil(lambda: placeholder not in main_window.panels())
    [real] = [p for p in main_window.panels() if p.objectName() == "io_viewer"]
    temporary = main_window._dock_of(real).objectName()
    assert temporary != "io_viewer"
    assert temporary not in unique_names._all_reserved_names_
    main_window.remove_panel(real)
    assert main_window.open_panel(_KIND, name="io_viewer").objectName() == "io_viewer"


def test_a_placeholder_closed_before_its_lookup_returns(qtbot, monkeypatch, main_window):
    import threading
    from PySide6.QtWidgets import QApplication, QPushButton
    import shiboken6
    from SciQLop.components.plotting.ui import placeholder_panel
    release, delivered = threading.Event(), []
    real_find = placeholder_panel.find_store_entry
    monkeypatch.setattr(install_offer, "fetch_index",
                        lambda *a, **k: release.wait(10) and [{"name": "absent", "versions": [_version("1.0")]}])
    monkeypatch.setattr(placeholder_panel, "find_store_entry",
                        lambda kind, done: real_find(kind, lambda e: (done(e), delivered.append(e))))
    panel = placeholder_panel.open_placeholder(main_window, dict(_ROOT), name="io_early_close")
    main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: not shiboken6.isValid(panel))
    release.set()
    qtbot.waitUntil(lambda: bool(delivered))
    assert delivered[0]["name"] == "absent"
    assert not [b for b in QApplication.allWidgets()
                if isinstance(b, QPushButton) and b.text() == "Install absent"]


def test_a_failing_open_keeps_the_placeholder(qtbot, main_window, placeholder):
    from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind

    def broken(name, config):
        raise RuntimeError("cannot build")

    with owned_by("absent"):
        PANEL_KINDS.contribute(PanelKind(_KIND, "Viewer", create=broken))
    qtbot.waitUntil(lambda: "cannot build" in placeholder.status())
    assert placeholder in main_window.panels()
    assert placeholder.objectName() == "io_viewer"


def test_the_placeholder_keeps_its_own_copy_of_the_tree(qtbot):
    from SciQLop.components.plotting.ui.placeholder_panel import PlaceholderPanel
    root = json.loads(json.dumps(_ROOT))
    panel = PlaceholderPanel(root)
    try:
        root["config"]["zoom"] = 9
        assert panel.root == _ROOT
    finally:
        panel.deleteLater()
