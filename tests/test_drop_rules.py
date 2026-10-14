"""Drop rules (spec §4.3): what a drop does is chosen by MIME type, product kind and target plot kind."""
import pytest

from SciQLop.core.drop_rules import DROP_RULES, DropRule, rule_for
from SciQLop.core.extensions import owned_by
from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
from SciQLop.core.plot_kinds import PROJECTION, TIMESERIES
from SciQLop.core.product_kinds import BOUNDARY, LAYER, SCALAR, SCENE

_THING = "application/x.drop-rules-test.thing"


@pytest.fixture(autouse=True)
def core_extension_points(qapp):
    from SciQLop.components.extension_points import prepare_extension_points
    prepare_extension_points()


@pytest.fixture
def withdraw(qapp):
    yield
    DROP_RULES.remove_owner("dr_demo")


@pytest.mark.parametrize("product_kind, target, rule_id", [
    (SCENE, PROJECTION, "sciqlop.scenes.plot_scene"), (SCENE, TIMESERIES, "sciqlop.scenes.plot_scene"),
    (SCENE, None, "sciqlop.scenes.plot_scene"),
    (BOUNDARY, PROJECTION, "sciqlop.scenes.set_boundary"), (BOUNDARY, TIMESERIES, "sciqlop.scenes.refuse_boundary"),
    (SCALAR, PROJECTION, "sciqlop.scenes.add_trajectory"), (SCALAR, TIMESERIES, "sciqlop.plot_product"),
    (None, TIMESERIES, "sciqlop.plot_product"), (None, PROJECTION, "sciqlop.scenes.add_trajectory"),
    (LAYER, PROJECTION, "sciqlop.layers.attach"), (LAYER, TIMESERIES, "sciqlop.layers.attach"),
])
def test_core_product_rules_reproduce_the_old_drop_table(qapp, product_kind, target, rule_id):
    assert rule_for(PRODUCT_LIST_MIME_TYPE, product_kind, target).id == rule_id


def test_core_rules_for_time_ranges_and_catalogs(qapp):
    assert rule_for(TIME_RANGE_MIME_TYPE, None, TIMESERIES).id == "sciqlop.time_range"
    assert rule_for(CATALOG_LIST_MIME_TYPE, None, TIMESERIES).id == "sciqlop.catalogs.overlay"
    assert all(DROP_RULES.owner_of(r.id) == "sciqlop" for r in DROP_RULES.list() if r.id.startswith("sciqlop."))


def test_the_product_kind_outweighs_the_target(withdraw):
    with owned_by("dr_demo"):
        for rid, pk, target in (("dr_demo.any", None, None), ("dr_demo.kind", "dr_demo.k", None),
                                ("dr_demo.target", None, "dr_demo.t"), ("dr_demo.both", "dr_demo.k", "dr_demo.t")):
            DROP_RULES.contribute(DropRule(rid, _THING, lambda *a: None, product_kind=pk, target=target))
    assert rule_for(_THING, "dr_demo.k", "dr_demo.t").id == "dr_demo.both"
    assert rule_for(_THING, "dr_demo.k", "other").id == "dr_demo.kind"
    assert rule_for(_THING, "other", "dr_demo.t").id == "dr_demo.target"
    assert rule_for(_THING, "other", "other").id == "dr_demo.any"
    assert rule_for("application/x.nobody", None, None) is None


def test_open_panels_accept_a_mime_type_added_later(qtbot, withdraw):
    from PySide6.QtCore import QMimeData
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core.mime import MIME_TYPES, MimeType
    panel = TimeSyncPanel("dr_panel", show_search_overlay=False)
    qtbot.addWidget(panel)
    panel.create_plot(0, PlotType.TimeSeries)
    dropped = []
    with owned_by("dr_demo"):
        MIME_TYPES.contribute(MimeType(_THING, lambda md: bytes(md.data(_THING)).decode()))
        DROP_RULES.contribute(DropRule("dr_demo.thing", _THING, lambda plot, payload, p: dropped.append(payload)))
    try:
        assert _THING in panel._drop_callbacks
        md = QMimeData()
        md.setData(_THING, b"hello")
        panel._drop_callbacks[_THING].call(panel.plots()[0], md)
        assert dropped == ["hello"]
    finally:
        MIME_TYPES.remove_owner("dr_demo")
