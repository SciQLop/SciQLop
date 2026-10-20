from datetime import datetime, timezone

import numpy as np
import pytest
from PySide6.QtWidgets import QLabel

from ..fixtures import *  # noqa: F401, F403
from SciQLop.components.comparison.backend.model import Comparison, Variant
from SciQLop.components.comparison.ui.panel_kind import COMPARISON_PANEL
from SciQLop.components.plotting.panel_template import (PanelTemplate, PlotModel, ProductModel, TimeRangeModel,
                                                        panel_tree)
from SciQLop.core.graph_context import graph_name

BASE_RANGE = (1_000.0, 1_100.0)


@pytest.fixture
def opened(main_window, qtbot):
    before = set(main_window.panels())
    yield
    for panel in [p for p in main_window.panels() if p not in before]:
        main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: set(main_window.panels()) <= before)


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def _vp_path(name):
    from SciQLop.user_api.plot._plots import to_product_path
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def sine(start: float, stop: float):
        x = np.linspace(start, stop, 50)
        return x, np.sin(x)

    vp = create_virtual_product(f"test_cmp_panel/{name}", sine, VirtualProductType.Scalar, labels=["y"])
    return "//".join(to_product_path(vp))


def _template(*plots):
    return PanelTemplate(name="P", time_range=TimeRangeModel(start=_iso(BASE_RANGE[0]), stop=_iso(BASE_RANGE[1])),
                         plots=[PlotModel(products=[ProductModel(path=p) for p in paths]) for paths in plots])


def _time_variants(n):
    return [Variant(label=f"event {i}", params={"start": 2_000.0 + 1_000 * i, "stop": 2_100.0 + 1_000 * i})
            for i in range(n)]


def _time_comparison_of_vp(variants=1, name="vp"):
    return Comparison(base=_template([_vp_path(name)]).to_tree(), dimension="time",
                      variants=_time_variants(variants))


def _open(main_window, comparison):
    return main_window.open_panel(COMPARISON_PANEL, **comparison.model_dump(mode="json"))


def _graphs(plot):
    from SciQLop.components.plotting.panel_introspection import plot_graphs
    return plot_graphs(plot)


def _tab_ids(w):
    bar = w.tab_bar
    return [bar.tabData(i) for i in range(bar.count())]


def test_open_and_round_trip(main_window, qtbot, opened):
    c = _time_comparison_of_vp(variants=1)
    w = _open(main_window, c)
    assert Comparison.model_validate(panel_tree(w)["config"]) == c
    assert w.title.text() == "Compare: 2 events"
    assert w.anchor_label.text() == "aligned on event start"


def test_core_kind_is_registered_but_not_in_new_menu(main_window):
    from SciQLop.core.panel_kinds import PANEL_KINDS
    kind = PANEL_KINDS.get(COMPARISON_PANEL)
    assert PANEL_KINDS.owner_of(COMPARISON_PANEL) == "sciqlop"
    assert kind.label == "Comparison" and not kind.in_new_menu


def test_view_switch_keeps_time_range(main_window, qtbot, opened):
    from SciQLop.core import TimeRange
    w = _open(main_window, _time_comparison_of_vp(variants=1, name="vp_switch"))
    w.inner.time_range = TimeRange(1_020.0, 1_080.0)
    qtbot.waitUntil(lambda: w.inner.time_range.start() == pytest.approx(1_020.0))
    old = w.inner
    w.set_view("difference")
    assert w.inner is not old
    assert w.comparison.view == "difference"
    assert w.tab_bar.tabData(w.tab_bar.currentIndex()) == "difference"
    rng = w.inner.time_range
    assert (rng.start(), rng.stop()) == pytest.approx((1_020.0, 1_080.0))


def test_tab_bar_switches_view(main_window, qtbot, opened):
    w = _open(main_window, _time_comparison_of_vp(variants=1, name="vp_tabs"))
    w.tab_bar.setCurrentIndex(_tab_ids(w).index("difference"))
    assert w.comparison.view == "difference"


def test_disabled_tab_for_inapplicable_view(main_window, qtbot, opened):
    w = _open(main_window, _time_comparison_of_vp(variants=2, name="vp_three"))
    i = _tab_ids(w).index("difference")
    assert not w.tab_bar.isTabEnabled(i)
    assert w.tab_bar.tabToolTip(i) == "Difference needs exactly two sides"
    assert w.tab_bar.isTabEnabled(_tab_ids(w).index("overlay"))


def test_anchor_change_rebuilds_and_is_saved(main_window, qtbot, opened):
    w = _open(main_window, _time_comparison_of_vp(variants=1, name="vp_anchor"))
    old = w.inner
    w.anchor_combo.setCurrentIndex(w.anchor_combo.findData("center"))
    assert w.comparison.anchor == "center"
    assert w.anchor_label.text() == "aligned on event centre"
    assert w.inner is not old
    assert panel_tree(w)["config"]["anchor"] == "center"


def test_alignment_only_for_time(main_window, qtbot, opened):
    path = _vp_path("vp_product")
    c = Comparison(base=_template([path]).to_tree(), dimension="product",
                   variants=[Variant(label="other", params={"target": [0, 0], "path": _vp_path("vp_product_b")})])
    w = _open(main_window, c)
    assert w.anchor_combo.isHidden() and w.anchor_label.isHidden()
    assert w.title.text() == "Compare: 2 products"


@pytest.fixture
def panel_template_log():
    """SciQLop loggers are not stdlib loggers, so caplog never sees them: listen to the lines they push."""
    from SciQLop.components.sciqlop_logging import getLogger
    signal = getLogger("SciQLop.components.plotting.panel_template").push_log
    lines = []
    signal.connect(lines.append)
    yield lines
    signal.disconnect(lines.append)


def test_reopen_with_missing_product_keeps_other_ghosts_in_place(main_window, qtbot, panel_template_log, opened):
    path = _vp_path("vp_missing")
    c = Comparison(base=_template(["nope//missing"], [path]).to_tree(), dimension="time",
                   variants=_time_variants(1))
    w = _open(main_window, c)
    assert any("WARNING" in line and "nope//missing" in line for line in panel_template_log)
    plots = w.inner.plots()
    assert len(plots) == 1
    qtbot.waitUntil(lambda: len(_graphs(plots[0])) == 2)
    base, ghost = _graphs(plots[0])
    assert graph_name(ghost) == f"{graph_name(base)} — event 0"


def test_source_panel_closed_after_creation(main_window, qtbot, opened):
    source = _template([_vp_path("vp_source")]).create_panel(main_window)
    qtbot.waitUntil(lambda: len(_graphs(source.plots()[0])) == 1)
    c = Comparison(base=PanelTemplate.from_panel(source).to_tree(), dimension="time", variants=_time_variants(1))
    main_window.remove_panel(source)
    qtbot.waitUntil(lambda: source not in main_window.panels())
    w = _open(main_window, c)
    qtbot.waitUntil(lambda: len(_graphs(w.inner.plots()[0])) == 2)


def test_template_round_trip(main_window, tmp_path, qtbot, opened):
    from SciQLop.components.comparison.ui.panel import ComparisonPanel
    c = _time_comparison_of_vp(variants=1, name="vp_template")
    w = _open(main_window, c)
    PanelTemplate.from_panel(w).to_file(str(tmp_path / "c.json"))
    reopened = PanelTemplate.from_file(str(tmp_path / "c.json")).create_panel(main_window)
    assert isinstance(reopened, ComparisonPanel)
    assert reopened.comparison == c


def test_save_as_template_writes_file_and_preview(main_window, tmp_path, qtbot, opened, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    import SciQLop.components.plotting.panel_template as panel_template
    monkeypatch.setattr(panel_template, "templates_dir", lambda: tmp_path)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("mine", True)))
    c = _time_comparison_of_vp(variants=1, name="vp_save")
    w = _open(main_window, c)
    w.save_as_template()
    assert Comparison.model_validate(
        PanelTemplate.from_file(str(tmp_path / "mine.json"))._foreign_root["config"]) == c
    assert (tmp_path / "mine.png").exists()


def test_edit_action_emits_edit_requested(main_window, qtbot, opened):
    w = _open(main_window, _time_comparison_of_vp(variants=1, name="vp_edit"))
    with qtbot.waitSignal(w.edit_requested, timeout=1000):
        next(a for a in w.menu_button.menu().actions() if a.text().startswith("Edit comparison")).trigger()


def test_unknown_view_shows_message_and_keeps_config(main_window, qtbot, opened):
    c = _time_comparison_of_vp(variants=1, name="vp_unknown").model_copy(update={"view": "nope.view"})
    w = _open(main_window, c)
    assert isinstance(w.inner, QLabel) and "nope.view" in w.inner.text()
    assert Comparison.model_validate(panel_tree(w)["config"]) == c


def test_unknown_dimension_shows_message_and_keeps_config(main_window, qtbot, opened):
    c = _time_comparison_of_vp(variants=1, name="vp_unknown_dim").model_copy(update={"dimension": "nope.dim"})
    w = _open(main_window, c)
    assert isinstance(w.inner, QLabel) and "nope.dim" in w.inner.text()
    assert Comparison.model_validate(panel_tree(w)["config"]) == c


def test_base_without_time_range_shows_message(main_window, qtbot, opened):
    template = PanelTemplate(name="P", plots=[PlotModel(products=[ProductModel(path=_vp_path("vp_norange"))])])
    c = Comparison(base=template.to_tree(), dimension="time", variants=_time_variants(1))
    w = _open(main_window, c)
    assert isinstance(w.inner, QLabel) and "no visible time range" in w.inner.text()


def _all_graph_names(panel):
    return [graph_name(g) for plot in panel.plots() for g in _graphs(plot)]


def test_difference_options_rebuild_and_persist(main_window, qtbot, opened):
    from SciQLop.core import TimeRange
    w = _open(main_window, _time_comparison_of_vp(variants=1, name="vp_options").model_copy(
        update={"view": "difference"}))
    assert set(w.option_combos) == {"operation", "method"}
    assert w.option_combos["operation"].currentText() == "difference"
    w.inner.time_range = TimeRange(1_020.0, 1_080.0)
    qtbot.waitUntil(lambda: w.inner.time_range.start() == pytest.approx(1_020.0))
    old = w.inner
    w.option_combos["operation"].setCurrentText("ratio")
    assert w.inner is not old
    assert (w.inner.time_range.start(), w.inner.time_range.stop()) == pytest.approx((1_020.0, 1_080.0))
    qtbot.waitUntil(lambda: any(n.endswith(": A / B") for n in _all_graph_names(w.inner)))
    assert panel_tree(w)["config"]["view_options"] == {"difference": {"operation": "ratio"}}


def test_overlay_shows_no_option_combos(main_window, qtbot, opened):
    w = _open(main_window, _time_comparison_of_vp(variants=1, name="vp_no_options"))
    assert w.option_combos == {}
    w.set_view("difference")
    assert set(w.option_combos) == {"operation", "method"}
    w.set_view("overlay")
    assert w.option_combos == {}


def test_clicking_a_tab_leaves_an_unknown_view(main_window, qtbot, opened):
    from PySide6.QtCore import Qt
    c = _time_comparison_of_vp(variants=1, name="vp_unknown_click").model_copy(update={"view": "nope.view"})
    w = _open(main_window, c)
    qtbot.waitUntil(w.tab_bar.isVisible)
    i = _tab_ids(w).index("overlay")
    qtbot.mouseClick(w.tab_bar, Qt.MouseButton.LeftButton, pos=w.tab_bar.tabRect(i).center())
    assert w.comparison.view == "overlay"
    assert not isinstance(w.inner, QLabel)


def test_switching_views_keeps_the_tabs(main_window, qtbot, opened):
    w = _open(main_window, _time_comparison_of_vp(variants=1, name="vp_keep_tabs"))
    w.tab_bar.setCurrentIndex(_tab_ids(w).index("difference"))
    assert _tab_ids(w) == ["overlay", "difference"]
    assert w.tab_bar.tabData(w.tab_bar.currentIndex()) == "difference"


def test_panel_built_outside_open_panel_saves_as_comparison(main_window, qtbot):
    from SciQLop.components.comparison.ui.panel import ComparisonPanel
    c = _time_comparison_of_vp(variants=1, name="vp_bare")
    w = ComparisonPanel("bare", c)
    qtbot.addWidget(w)
    template = PanelTemplate.from_panel(w)
    assert template.panel_kind == COMPARISON_PANEL
    assert Comparison.model_validate(template.to_tree()["panel"]["config"]) == c
