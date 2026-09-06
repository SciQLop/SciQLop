"""'Add Event' must target the focused panel, not the first-ever-connected
one (2026-09-06 review): with several panels open, self._panels[0] is
whichever panel connected first -- not necessarily the one the user is
looking at.
"""
from .fixtures import *


def test_add_event_targets_the_focused_panel(qtbot, qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.core import TimeRange

    # add_event marks the provider dirty; win.close() now warns about
    # unsaved catalogs (see test_mainwindow_close.py) and would otherwise
    # block on a real modal dialog here.
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="FocusAddProv")
    cat = provider.catalogs()[0]

    win = SciQLopMainWindow()
    try:
        panel1 = win.new_plot_panel()
        panel2 = win.new_plot_panel()
        panel1.time_range = TimeRange(1_000_000.0, 1_000_100.0)
        panel2.time_range = TimeRange(2_000_000.0, 2_000_100.0)

        browser = win.catalogs_browser
        # connected in order 1, then 2 -- self._panels[0] would be panel1
        browser.connect_to_panel(panel1)
        browser.connect_to_panel(panel2)
        browser._current_provider = provider
        browser._current_catalog = cat
        browser._event_model.set_context(provider, cat)
        browser._event_model.set_events(provider.events(cat))

        dock2 = win.dock_manager.findDockWidget(panel2.name)
        assert dock2 is not None
        win.dock_manager.setDockWidgetFocused(dock2)

        assert browser._focused_panel() is panel2

        browser._on_add_event()

        events = provider.events(cat)
        assert len(events) == 1
        midpoint = events[0].start.timestamp()
        assert 2_000_000.0 < midpoint < 2_000_100.0, \
            "new event must be centered on the focused panel (2), not panel 1"
    finally:
        win.close()


def test_add_event_falls_back_to_first_panel_when_none_focused(qtbot, qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.core import TimeRange

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="NoFocusAddProv")
    cat = provider.catalogs()[0]

    win = SciQLopMainWindow()
    try:
        panel1 = win.new_plot_panel()
        panel1.time_range = TimeRange(3_000_000.0, 3_000_100.0)

        browser = win.catalogs_browser
        browser.connect_to_panel(panel1)
        browser._current_provider = provider
        browser._current_catalog = cat
        browser._event_model.set_context(provider, cat)
        browser._event_model.set_events(provider.events(cat))

        assert browser._focused_panel() is None  # no dock explicitly focused

        browser._on_add_event()

        events = provider.events(cat)
        assert len(events) == 1
        midpoint = events[0].start.timestamp()
        assert 3_000_000.0 < midpoint < 3_000_100.0
    finally:
        win.close()
