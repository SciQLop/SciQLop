"""A right-click over a catalog event span puts that event's entries at the top of the panel menu
(design: plugins_sciqlop/sciqlop_cocat/SCIQLOP_CHANGES.md, "a menu on each event span")."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from .fixtures import *  # noqa: F401,F403

BASE = datetime(2020, 1, 1, tzinfo=timezone.utc)
EVENT_ENTRIES = ["Show attributes…", "Show in Catalogs", "Zoom to event", "Copy start and stop", "Delete"]


@pytest.fixture
def scene(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel, plot_static_data
    from SciQLop.core import TimeRange

    class Provider(DummyProvider):
        read_only = False

        def capabilities(self, catalog=None):
            return set() if self.read_only else super().capabilities(catalog)

    provider = Provider(num_catalogs=1, events_per_catalog=0, name="SpanMenuProv")
    catalog = provider.catalogs()[0]
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    event = CatalogEvent(uuid="ev-1", start=BASE + timedelta(hours=10), stop=BASE + timedelta(hours=14),
                         meta={"label": "shock", "quality": 3})
    provider.add_event(catalog, event)
    panel = TimeSyncPanel("span-menu-panel",
                          time_range=TimeRange(BASE.timestamp(), (BASE + timedelta(days=1)).timestamp()))
    qtbot.addWidget(panel)
    panel.resize(900, 400)
    panel.show()
    qtbot.waitExposed(panel)
    t = np.linspace(BASE.timestamp(), (BASE + timedelta(days=1)).timestamp(), 200)
    plot_static_data(panel, t, np.sin(t))
    panel.catalog_manager.add_catalog(catalog)
    qtbot.wait(100)
    return panel, provider, catalog, event


def _plot(panel):
    from SciQLopPlots import SciQLopPlot
    return panel.findChildren(SciQLopPlot)[0]


def _canvas(plot):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget
    canvases = [w for w in plot.findChildren(QWidget) if w.testAttribute(Qt.WidgetAttribute.WA_NoMousePropagation)]
    return max(canvases, key=lambda w: w.width(), default=plot)


def _cursor_time(plot):
    k = plot.crosshair_key
    return k() if callable(k) else k


def _global_pos_at(qtbot, plot, t: float):
    """Put the mouse over time *t*: two samples give the pixel <-> time line, so this works whether
    SciQLop hit-tests with the crosshair time or with the span's pixel range."""
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    canvas = _canvas(plot)
    y = canvas.height() // 2

    def time_at(x):
        QTest.mouseMove(canvas, QPoint(x, y))
        qtbot.waitUntil(lambda: _cursor_time(plot) == _cursor_time(plot), timeout=1000)
        qtbot.wait(50)
        return _cursor_time(plot)

    x1, x2 = canvas.width() // 4, 3 * canvas.width() // 4
    t1, t2 = time_at(x1), time_at(x2)
    x = round(x1 + (t - t1) * (x2 - x1) / (t2 - t1))
    time_at(x)
    return canvas, canvas.mapToGlobal(QPoint(x, y))


def _menu_at(qtbot, panel, t):
    canvas, pos = _global_pos_at(qtbot, _plot(panel), t)
    return panel._build_context_menu(canvas, pos)


def _texts(menu):
    return [a.text() for a in menu.actions() if not a.isSeparator()]


def _action(menu, text):
    return next(a for a in menu.actions() if a.text() == text)


def test_a_right_click_on_a_span_puts_the_event_first(qtbot, scene):
    panel, _, _, event = scene
    menu = _menu_at(qtbot, panel, (event.start.timestamp() + event.stop.timestamp()) / 2)
    texts = _texts(menu)
    assert texts[0].startswith("Event: shock")
    assert texts[1:1 + len(EVENT_ENTRIES)] == EVENT_ENTRIES
    assert "Catalogs" in texts[1 + len(EVENT_ENTRIES):]


def test_a_right_click_beside_the_spans_has_no_event_section(qtbot, scene):
    panel, *_ = scene
    menu = _menu_at(qtbot, panel, (BASE + timedelta(hours=20)).timestamp())
    assert not any(t.startswith("Event:") for t in _texts(menu))


def test_zoom_to_event_pads_ten_percent_each_side(qtbot, scene):
    panel, _, _, event = scene
    _action(_menu_at(qtbot, panel, event.start.timestamp() + 60), "Zoom to event").trigger()
    start, stop, pad = event.start.timestamp(), event.stop.timestamp(), 0.1 * 4 * 3600
    assert panel.time_range.start() == pytest.approx(start - pad, abs=1)
    assert panel.time_range.stop() == pytest.approx(stop + pad, abs=1)


def test_copy_puts_start_and_stop_in_two_cells(qtbot, scene):
    from PySide6.QtGui import QGuiApplication
    panel, _, _, event = scene
    _action(_menu_at(qtbot, panel, event.start.timestamp() + 60), "Copy start and stop").trigger()
    assert QGuiApplication.clipboard().text() == "2020-01-01T10:00:00Z\t2020-01-01T14:00:00Z"


def test_delete_needs_edit_mode_then_removes_the_event(qtbot, scene):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    panel, provider, catalog, event = scene
    middle = event.start.timestamp() + 60
    assert not _action(_menu_at(qtbot, panel, middle), "Delete").isEnabled()  # view mode: spans are read-only
    panel.catalog_manager.mode = InteractionMode.EDIT
    _action(_menu_at(qtbot, panel, middle), "Delete").trigger()
    assert provider.events(catalog) == []


def test_delete_is_disabled_without_the_right(qtbot, scene):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    panel, provider, _, event = scene
    panel.catalog_manager.mode = InteractionMode.EDIT
    provider.read_only = True
    assert not _action(_menu_at(qtbot, panel, event.start.timestamp() + 60), "Delete").isEnabled()


def test_show_in_catalog_browser_reveals_the_event(qtbot, scene):
    panel, _, catalog, event = scene
    got = []
    panel.catalog_manager.catalog_event_clicked.connect(lambda c, e: got.append((c, e)))
    _action(_menu_at(qtbot, panel, event.start.timestamp() + 60), "Show in Catalogs").trigger()
    assert got == [(catalog, event)]


def test_catalog_event_menu_entries_show_with_the_event_as_context(qtbot, scene):
    from SciQLop.components.command_palette.backend.registry import COMMANDS, PaletteCommand
    from SciQLop.core.extensions import owned_by
    from SciQLop.core.menus import CATALOG_EVENTS, MENUS, MenuEntry
    panel, provider, catalog, event = scene
    contexts, ran = [], []
    with owned_by("span_menu_test"):
        COMMANDS.contribute(PaletteCommand(id="test.event_history", name="History of this event",
                                           description="", callback=lambda: ran.append(True)))
        MENUS.contribute(MenuEntry("test.event_history.menu", CATALOG_EVENTS, "test.event_history",
                                   when=lambda ctx: contexts.append(ctx) or True))
    try:
        _action(_menu_at(qtbot, panel, event.start.timestamp() + 60), "History of this event").trigger()
    finally:
        COMMANDS.remove_owner("span_menu_test")
        MENUS.remove_owner("span_menu_test")
    assert ran and contexts[-1]["events"] == event.uuid and contexts[-1]["provider"] == provider.name


def _popup(scene):
    from SciQLop.components.catalogs.ui.event_menu import EventAttributesPopup
    panel, provider, catalog, event = scene
    return EventAttributesPopup(catalog, event, parent=panel)


def _row_of(view, name):
    from PySide6.QtCore import Qt
    model = view.model()
    return next(r for r in range(model.rowCount())
                if model.headerData(r, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole) == name)


def test_the_popup_has_one_row_per_attribute(qtbot, scene):
    from PySide6.QtCore import Qt
    popup = _popup(scene)
    qtbot.addWidget(popup)
    model = popup.view.model()
    names = [model.headerData(r, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole) for r in range(model.rowCount())]
    assert names[:2] == ["Start (UTC)", "Stop (UTC)"] and set(names[2:]) == {"label", "quality"}
    assert model.columnCount() == 1


def test_the_popup_writes_through_the_provider(qtbot, scene):
    from PySide6.QtCore import Qt
    panel, provider, catalog, event = scene
    popup = _popup(scene)
    qtbot.addWidget(popup)
    model = popup.view.model()
    index = model.index(_row_of(popup.view, "label"), 0)
    assert model.flags(index) & Qt.ItemFlag.ItemIsEditable
    assert model.setData(index, "bow shock", Qt.ItemDataRole.EditRole)
    assert provider.events(catalog)[0].meta["label"] == "bow shock"


def test_the_popup_is_read_only_without_edit_rights(qtbot, scene):
    from PySide6.QtCore import Qt
    panel, provider, catalog, event = scene
    provider.read_only = True
    popup = _popup(scene)
    qtbot.addWidget(popup)
    model = popup.view.model()
    assert not model.flags(model.index(_row_of(popup.view, "label"), 0)) & Qt.ItemFlag.ItemIsEditable


def test_closing_the_popup_lets_go_of_the_event(qtbot, scene):
    popup = _popup(scene)
    qtbot.addWidget(popup)
    popup.show()
    popup.close()
    assert popup.source_model.rowCount() == 0   # disconnected from the event's signals


@pytest.mark.parametrize("mode, entry, can_edit", [
    ("VIEW", "Show attributes…", False), ("JUMP", "Show attributes…", False), ("EDIT", "Edit attributes…", True)])
def test_attributes_are_edited_in_edit_mode_and_only_shown_otherwise(qtbot, scene, mode, entry, can_edit):
    from PySide6.QtWidgets import QAbstractItemView
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    from SciQLop.components.catalogs.ui.event_menu import EventAttributesPopup
    panel, _, _, event = scene
    panel.catalog_manager.mode = getattr(InteractionMode, mode)
    _action(_menu_at(qtbot, panel, event.start.timestamp() + 60), entry).trigger()
    popups = [w for w in panel.findChildren(EventAttributesPopup) if w.isVisible()]
    assert len(popups) == 1
    no_editing = popups[0].view.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert no_editing is not can_edit
    popups[0].close()


def test_zoom_to_a_zero_length_event_shows_an_hour_each_side():
    from types import SimpleNamespace
    from SciQLop.components.catalogs.ui.event_menu import _zoom
    when = BASE + timedelta(hours=3)
    panel = SimpleNamespace(time_range=None)
    _zoom(panel, SimpleNamespace(start=when, stop=when))
    assert panel.time_range.start() == pytest.approx(when.timestamp() - 3600)
    assert panel.time_range.stop() == pytest.approx(when.timestamp() + 3600)


@pytest.mark.parametrize("when, expected", [
    (datetime(2020, 1, 1, 12, 0, 5, tzinfo=timezone.utc), "2020-01-01 12:00:05"),
    (datetime(2020, 1, 1, 12, 0, 5, 250000, tzinfo=timezone.utc), "2020-01-01 12:00:05.250"),
    (datetime(2020, 1, 1, 12, 0, 5, 400, tzinfo=timezone.utc), "2020-01-01 12:00:05"),
])
def test_event_times_show_milliseconds_only_when_they_have_some(when, expected):
    from SciQLop.components.catalogs.ui.event_table import format_event_time
    assert format_event_time(when) == expected


def test_an_unlabelled_event_is_titled_by_its_time_in_utc():
    from types import SimpleNamespace
    from SciQLop.components.catalogs.ui.event_menu import _title
    event = SimpleNamespace(meta={}, start=datetime(2020, 1, 1, 12, 0, 5, tzinfo=timezone.utc))
    assert _title(event) == "2020-01-01 12:00:05 UTC"
