from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt

from ..fixtures import *  # noqa: F401, F403
from SciQLop.components.comparison.backend.model import Comparison, Variant
from SciQLop.components.comparison.ui.panel_kind import COMPARISON_PANEL
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel, TimeRangeModel

BASE_RANGE = (1_000.0, 1_100.0)
T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def opened(main_window, qtbot):
    before = set(main_window.panels())
    yield
    for panel in [p for p in main_window.panels() if p not in before]:
        main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: set(main_window.panels()) <= before)


def _dummy_providers():
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    return [p for p in CatalogRegistry.instance().providers() if isinstance(p, DummyProvider)]


@pytest.fixture(autouse=True)
def _no_leftover_dummy_providers(qapp):
    """_catalog_with registers a DummyProvider per test: leave the registry as it was."""
    before = set(map(id, _dummy_providers()))
    yield
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    for provider in [p for p in _dummy_providers() if id(p) not in before]:
        CatalogRegistry.instance().unregister(provider)
    assert set(map(id, _dummy_providers())) <= before


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def _vp_path(name):
    from SciQLop.user_api.plot._plots import to_product_path
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def sine(start: float, stop: float):
        x = np.linspace(start, stop, 50)
        return x, np.sin(x)

    vp = create_virtual_product(f"test_cmp_wizard/{name}", sine, VirtualProductType.Scalar, labels=["y"])
    return "//".join(to_product_path(vp))


def _template(name="P", *paths):
    return PanelTemplate(name=name, time_range=TimeRangeModel(start=_iso(BASE_RANGE[0]), stop=_iso(BASE_RANGE[1])),
                         plots=[PlotModel(products=[ProductModel(path=p) for p in paths])])


def _base_panel(main_window, qtbot, vp_name):
    panel = _template("P", _vp_path(vp_name)).create_panel(main_window)
    qtbot.waitUntil(lambda: len(panel.plots()) == 1)
    return panel


def _event(uuid, hours_after, length=timedelta(hours=1)):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    start = T0 + timedelta(hours=hours_after)
    return CatalogEvent(uuid=uuid, start=start, stop=start + length)


def _catalog_with(name, *events):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name=name)
    catalog = provider.catalogs()[0]
    for ev in events:
        provider.add_event(catalog, ev)
    return provider, catalog


def _dialog(qtbot, main_window, **kwargs):
    from SciQLop.components.comparison.ui.wizard import CompareDialog
    dialog = CompareDialog(main_window, **kwargs)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def _check_events(picker, catalog, count):
    index = picker.catalog_combo.findText(f"{catalog.provider.name}/", Qt.MatchFlag.MatchStartsWith)
    assert index >= 0
    picker.catalog_combo.setCurrentIndex(index)
    for row in range(count):
        picker.event_list.item(row).setCheckState(Qt.CheckState.Checked)


def test_dialog_builds_time_comparison(main_window, qtbot, opened):
    from SciQLop.components.comparison.ui.panel import ComparisonPanel
    _, catalog = _catalog_with("CmpWizProv", *(_event(f"e{i}", i * 5) for i in range(3)))
    base = _base_panel(main_window, qtbot, "vp_dialog")
    dialog = _dialog(qtbot, main_window, base_panel=base.name)
    dialog.dimension_buttons["time"].click()
    _check_events(dialog.picker, catalog, 2)
    assert dialog.compare_button.isEnabled()
    dialog.compare_button.click()
    panel = dialog.opened
    assert isinstance(panel, ComparisonPanel) and panel in main_window.panels()
    assert panel.comparison.dimension == "time"
    assert [v.label for v in panel.comparison.variants] == ["2020-01-01T00:00:00+00:00", "2020-01-01T05:00:00+00:00"]


def test_time_variants_in_the_same_minute_get_distinct_labels():
    from SciQLop.components.comparison.ui.pickers import time_variant
    events = [_event("a", 0), _event("b", 20 / 3600)]
    assert [time_variant(e).label for e in events] == ["2020-01-01T00:00:00+00:00", "2020-01-01T00:00:20+00:00"]


def test_time_variant_keeps_event_duration(qtbot):
    from SciQLop.components.comparison.ui.pickers import PICKERS
    _, catalog = _catalog_with("CmpWizDuration", _event("long", 0, timedelta(hours=2)))
    picker = PICKERS["time"](_template(), None)
    qtbot.addWidget(picker)
    _check_events(picker, catalog, 1)
    [variant] = picker.variants()
    assert variant.params["stop"] - variant.params["start"] == 7200



def test_time_picker_shows_events_that_arrive_after_the_catalog_is_picked(qtbot):
    """Remote catalogs (AMDA, CDAWeb) return no events at first and load them in the background."""
    from SciQLop.components.comparison.ui.pickers import PICKERS
    provider, catalog = _catalog_with("CmpWizLate", _event("early", 0))
    picker = PICKERS["time"](_template(), None)
    qtbot.addWidget(picker)
    _check_events(picker, catalog, 1)

    provider.add_event(catalog, _event("late", 5))

    assert picker.event_list.count() == 2
    assert len(picker.variants()) == 1, "the event ticked before the refresh stays ticked"


def test_time_picker_says_events_are_loading(qtbot, monkeypatch):
    from SciQLop.components.comparison.ui.pickers import PICKERS
    provider, catalog = _catalog_with("CmpWizLoading")
    monkeypatch.setattr(provider, "is_loading", lambda _catalog: True)
    picker = PICKERS["time"](_template(), None)
    qtbot.addWidget(picker)
    _check_events(picker, catalog, 0)
    assert [picker.event_list.item(r).text() for r in range(picker.event_list.count())] == ["loading events…"]
    assert picker.variants() == []

def test_menu_entries_are_registered(qapp):
    from SciQLop.components.command_palette.backend.registry import CommandRegistry
    from SciQLop.components.comparison.ui.commands import register_comparison_commands
    from SciQLop.core.menus import CATALOG_EVENTS, MAIN_TOOLS, MENUS, PANEL
    register_comparison_commands(CommandRegistry())
    placed = {(e.location, e.command, e.label) for e in MENUS.list()}
    assert {(MAIN_TOOLS, "sciqlop.compare", "Compare…"), (PANEL, "sciqlop.compare", "Compare with…"),
            (CATALOG_EVENTS, "sciqlop.compare_events", "Compare")} <= placed


def test_compare_events_needs_two_events(qapp):
    from SciQLop.components.command_palette.backend.registry import CommandRegistry
    from SciQLop.components.comparison.ui.commands import register_comparison_commands
    from SciQLop.core.menus import CATALOG_EVENTS, MENUS
    register_comparison_commands(CommandRegistry())
    [entry] = [e for e in MENUS.list(location=CATALOG_EVENTS) if e.command == "sciqlop.compare_events"]
    assert not entry.when({"events": "a"})
    assert not entry.when({})
    assert entry.when({"events": "a,b"})


def test_events_arg_lists_catalog_events(qapp):
    from SciQLop.components.command_palette.arg_types import EventsArg, catalog_arg_value
    provider, catalog = _catalog_with("CmpWizArg", _event("x1", 0), _event("x2", 3))
    arg = EventsArg()
    assert arg.name == "events"
    completions = arg.completions({"catalog": catalog_arg_value(provider.name, catalog.uuid)})
    assert [c.value for c in completions] == ["x1", "x2"]
    assert completions[1].display.startswith("2020-01-01T03:00")
    assert arg.completions({}) == []


def _select_catalog(browser, catalog):
    model = browser._tree_model
    for row in range(model.rowCount(QModelIndex())):
        prov_idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(prov_idx).provider is catalog.provider:
            for crow in range(model.rowCount(prov_idx)):
                cat_idx = model.index(crow, 0, prov_idx)
                if model.node_from_index(cat_idx).catalog is catalog:
                    browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(cat_idx))
                    return
    raise AssertionError("catalog node not found")


def _select_event_rows(browser, rows):
    sm = browser._event_table.selectionModel()
    for row in rows:
        sm.select(browser._sort_proxy.index(row, 0),
                  QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)


def test_catalog_events_menu_offers_compare(main_window, qtbot):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    _, catalog = _catalog_with("CmpWizMenu", _event("m1", 0), _event("m2", 2), _event("m3", 4))
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    _select_catalog(browser, catalog)
    qtbot.waitUntil(lambda: browser._sort_proxy.rowCount() == 3)
    _select_event_rows(browser, [0])
    assert "Compare" not in [a.text() for a in browser._build_event_context_menu().actions()]
    _select_event_rows(browser, [1])
    context = browser._event_menu_context()
    assert sorted(context["events"].split(",")) == ["m1", "m2"]
    assert "Compare" in [a.text() for a in browser._build_event_context_menu().actions()]


def test_open_compare_events_presets_the_dialog(main_window, qtbot, opened):
    from SciQLop.components.command_palette.arg_types import catalog_arg_value
    from SciQLop.components.comparison.ui.commands import open_compare_events
    provider, catalog = _catalog_with("CmpWizEvents", _event("o1", 0), _event("o2", 3), _event("o3", 6))
    base = _base_panel(main_window, qtbot, "vp_events")
    base.catalog_manager.add_catalog(catalog)
    dialog = open_compare_events(catalog_arg_value(provider.name, catalog.uuid), "o1,o3,o2")
    qtbot.addWidget(dialog)
    assert dialog.base_combo.currentText() == base.name
    assert dialog.dimension_buttons["time"].isChecked()
    assert [v.label for v in dialog.picker.variants()] == ["2020-01-01T03:00:00+00:00", "2020-01-01T06:00:00+00:00"]
    dialog.compare_button.click()
    rng = dialog.opened.comparison.template().time_range
    assert datetime.fromisoformat(rng.start) == T0 and datetime.fromisoformat(rng.stop) == T0 + timedelta(hours=1)


def test_panels_showing_finds_panels_with_the_catalog(main_window, qtbot, opened):
    from SciQLop.components.catalogs.backend.panel_manager import panels_showing
    provider, catalog = _catalog_with("CmpWizShowing", _event("s1", 0))
    base = _base_panel(main_window, qtbot, "vp_showing")
    assert panels_showing(main_window, provider.name, catalog.uuid) == []
    base.catalog_manager.add_catalog(catalog)
    assert panels_showing(main_window, provider.name, catalog.uuid) == [base]


def _time_comparison(name):
    return Comparison(base=_template("P", _vp_path(name)).to_tree(), dimension="time",
                      variants=[Variant(label="a", params={"start": 2_000.0, "stop": 2_100.0})])


def test_edit_mode_updates_existing_panel(main_window, qtbot, opened):
    from SciQLop.components.comparison.ui.wizard import CompareDialog
    _, catalog = _catalog_with("CmpWizEdit", _event("d1", 0), _event("d2", 1))
    original = _time_comparison("vp_edit")
    panel = main_window.open_panel(COMPARISON_PANEL, **original.model_dump(mode="json"))
    panel.edit_requested.emit()
    dialog = panel.findChild(CompareDialog)
    assert dialog is not None and dialog.isVisible()
    assert [v.label for v in dialog.picker.variants()] == ["a"]
    _check_events(dialog.picker, catalog, 2)
    dialog.compare_button.click()
    assert [v.label for v in panel.comparison.variants] == ["2020-01-01T00:00:00+00:00", "2020-01-01T01:00:00+00:00"]
    assert panel.comparison.base == original.base
    assert dialog.opened is None


def test_dialog_accepts_user_api_panel(main_window, qtbot, opened):
    from SciQLop.user_api.plot._panel import PlotPanel
    base = _base_panel(main_window, qtbot, "vp_wrapper")
    dialog = _dialog(qtbot, main_window, base_panel=PlotPanel(base))
    assert dialog.base_combo.currentText() == base.name
    dialog.dimension_buttons["settings"].click()
    assert dialog.picker is not None


def test_product_picker_refuses_unknown_path(main_window, qtbot):
    from SciQLop.components.comparison.ui.pickers import PICKERS
    picker = PICKERS["product"](_template("P", _vp_path("vp_product")), None)
    qtbot.addWidget(picker)
    picker.path_edit.setText("nope//missing")
    assert picker.problem()
    other = _vp_path("vp_product_other")
    picker.path_edit.setText(other)
    assert picker.problem() is None
    [variant] = picker.variants()
    assert variant.label == "vp_product_other"
    assert variant.params == {"target": [0, 0], "path": other, "is_colormap": False}


def test_unknown_dimension_gets_a_message(qtbot):
    from PySide6.QtWidgets import QLabel
    from SciQLop.components.comparison.ui.pickers import picker_for
    picker = picker_for("plugin.dim", _template(), None)
    qtbot.addWidget(picker)
    assert "no picker for this kind of comparison" in picker.findChild(QLabel).text()


def test_settings_picker_snapshots_changed_knobs(main_window, qtbot):
    from SciQLop.components.comparison.ui.pickers import PICKERS
    from SciQLop.user_api.plot._plots import to_product_path
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def scaled(start: float, stop: float, gain: int = 1):
        x = np.linspace(start, stop, 50)
        return x, gain * np.sin(x)

    vp = create_virtual_product("test_cmp_wizard/vp_knobs", scaled, VirtualProductType.Scalar, labels=["y"])
    picker = PICKERS["settings"](_template("P", _vp_path("vp_plain"), "//".join(to_product_path(vp))), None)
    qtbot.addWidget(picker)
    assert picker.target_combo.count() == 1
    picker.delegates["gain"].set_value(3)
    picker.add_variant()
    [variant] = picker.variants()
    assert variant.label == "gain=3"
    assert variant.params == {"target": [0, 1], "knobs": {"gain": 3}}


def test_panel_menu_opens_the_dialog_on_that_panel(main_window, qtbot, opened):
    from SciQLop.components.comparison.ui.wizard import CompareDialog
    base = _base_panel(main_window, qtbot, "vp_panel_menu")
    menu = base._build_context_menu()
    [action] = [a for a in menu.actions() if a.text() == "Compare with…"]
    action.trigger()
    [dialog] = [d for d in main_window.findChildren(CompareDialog) if d.isVisible()]
    qtbot.addWidget(dialog)
    assert dialog.base_combo.currentText() == base.name


def _product_mime(path):
    from SciQLopPlots import ProductsModel
    model, parent = ProductsModel.instance(), QModelIndex()
    for name in path.split("//"):
        rows = (model.index(r, 0, parent) for r in range(model.rowCount(parent)))
        parent = next(i for i in rows if i.data(Qt.ItemDataRole.DisplayRole) == name)
    return model.mimeData([parent])


def _send_drag(widget, mime):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
    from PySide6.QtWidgets import QApplication
    pos, action = widget.rect().center(), Qt.DropAction.CopyAction
    buttons, mods = Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    events = [QDragEnterEvent(pos, action, mime, buttons, mods), QDragMoveEvent(pos, action, mime, buttons, mods)]
    for event in events:
        QApplication.sendEvent(widget, event)
    accepted = [e.isAccepted() for e in events]
    drop = QDropEvent(QPointF(pos), action, mime, buttons, mods)
    QApplication.sendEvent(widget, drop)
    return accepted


def test_product_drop_fills_the_path(main_window, qtbot):
    from SciQLop.components.comparison.ui.pickers import PICKERS
    from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
    picker = PICKERS["product"](_template("P", _vp_path("vp_drop_base")), None)
    qtbot.addWidget(picker)
    path = _vp_path("vp_dropped")
    mime = _product_mime(path)
    assert mime.hasFormat(PRODUCT_LIST_MIME_TYPE)
    mime.removeFormat("text/plain")
    assert _send_drag(picker.path_edit, mime) == [True, True]
    assert picker.path_edit.text() == path


def test_compare_disabled_once_the_base_panel_is_closed(main_window, qtbot, opened):
    _, catalog = _catalog_with("CmpWizClosed", _event("c1", 0))
    base = _base_panel(main_window, qtbot, "vp_closed")
    dialog = _dialog(qtbot, main_window, base_panel=base.name)
    _check_events(dialog.picker, catalog, 1)
    assert dialog.compare_button.isEnabled()
    main_window.remove_panel(base)
    qtbot.waitUntil(lambda: base not in main_window.panels())
    dialog.picker.changed.emit()
    assert not dialog.compare_button.isEnabled()
    assert dialog.compare_button.toolTip() == "the base panel is no longer open"


def test_edit_requests_reuse_the_open_dialog(main_window, qtbot, opened):
    from SciQLop.components.comparison.ui.wizard import CompareDialog
    panel = main_window.open_panel(COMPARISON_PANEL, **_time_comparison("vp_edit_twice").model_dump(mode="json"))
    panel.edit_requested.emit()
    panel.edit_requested.emit()
    assert len([d for d in panel.findChildren(CompareDialog) if d.isVisible()]) == 1


def test_panel_entry_without_main_window_is_hidden(monkeypatch):
    from SciQLop.components.comparison.ui import commands
    monkeypatch.setattr(commands, "_main_window", lambda: None)
    assert commands._open_time_panel({"panel": "P"}) is False


def test_compare_events_with_one_event_warns(main_window, qtbot, monkeypatch):
    from SciQLop.components.command_palette.arg_types import catalog_arg_value
    from SciQLop.components.comparison.ui import commands
    provider, catalog = _catalog_with("CmpWizOne", _event("w1", 0))
    warnings = []
    monkeypatch.setattr(commands.log, "warning", warnings.append)
    assert commands.open_compare_events(catalog_arg_value(provider.name, catalog.uuid), "w1") is None
    assert warnings == ["select at least two events to compare"]


def test_knobs_of_logs_a_failing_provider(main_window, monkeypatch):
    from SciQLop.components.comparison.ui import pickers
    from SciQLop.components.plotting.backend.data_provider import providers
    path = _vp_path("vp_bad_knobs")
    provider = providers.get(pickers.product_node(path).provider())
    warnings = []
    monkeypatch.setattr(provider, "get_knobs", lambda node: 1 / 0)
    monkeypatch.setattr(pickers.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    assert pickers.knobs_of(path) == []
    assert len(warnings) == 1 and "vp_bad_knobs" in warnings[0]
