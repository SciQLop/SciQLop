"""Source kinds (spec §4.2): legacy values load, core kinds drive tooltips, a plugin kind is used like a core one."""
import pytest

from SciQLop.core.extensions import owned_by
from SciQLop.core.graph_context import GraphContext, graph_tooltip
from SciQLop.core.source_kinds import (FUNCTION, PROVIDER, SOURCE_KINDS, SPEASY, STATIC, VP, SourceKind,
                                       source_kind)


def _ctx(**kw):
    return GraphContext(**{"graph_id": "g", "panel_name": "P", "plot_index": 0, "graph_type": "Line", **kw})


class _Graph:
    """Just enough of a SciQLopPlots graph for context_of/graph_tooltip."""

    def __init__(self, ctx):
        self._md = ctx.to_meta_data()

    def meta_data(self):
        return self._md

    def objectName(self):
        return "g"

    name = "B"


@pytest.fixture
def withdraw(qapp):
    yield
    SOURCE_KINDS.remove_owner("sk_demo")


@pytest.mark.parametrize("legacy, canonical", [("speasy", SPEASY), ("vp", VP), ("function", FUNCTION),
                                               ("static", STATIC)])
def test_legacy_values_load_as_canonical_ids(legacy, canonical):
    from SciQLop.components.plotting.panel_template import ProductModel
    assert _ctx(kind=legacy).kind == canonical
    assert ProductModel(path="a//b", kind=legacy).kind == canonical
    assert ProductModel(path="a//b").kind is None


def test_core_kinds_are_owned_by_sciqlop(qapp):
    for kid in (SPEASY, VP, FUNCTION, STATIC, PROVIDER):
        assert SOURCE_KINDS.owner_of(kid) == "sciqlop"


def test_core_tooltips_are_unchanged(qapp):
    assert graph_tooltip(_Graph(_ctx(kind="speasy", speasy_id="amda/imf"))).splitlines()[0] == "B: amda/imf — Speasy"
    assert graph_tooltip(_Graph(_ctx(kind="vp", vp_path="a/b"))).splitlines()[0] == "B: a/b — Virtual"
    assert graph_tooltip(_Graph(_ctx(kind="static"))).splitlines()[0] == "B: static data"
    fn = _ctx(kind="function", callback_module="m", callback_qualname="f")
    assert graph_tooltip(_Graph(fn)).splitlines()[0] == "B: function m.f"


def test_a_plugin_source_kind_drives_tooltip_inspector_and_template(withdraw):
    from SciQLop.components.plotting.panel_template import context_product_path
    from SciQLop.components.plotting.ui.graph_context_inspector.section import _source_line
    with owned_by("sk_demo"):
        SOURCE_KINDS.contribute(SourceKind("sk_demo.cdf", tooltip=lambda c: f"{c.provider_name} file",
                                           inspector_line=lambda c: "CDF file",
                                           product_path=lambda c: "cdf//x"))
    ctx = _ctx(kind="sk_demo.cdf", provider_name="CDF")
    assert graph_tooltip(_Graph(ctx)).splitlines()[0] == "B: CDF file"
    assert _source_line(ctx) == "CDF file"
    assert context_product_path(ctx) == "cdf//x"


def test_a_kind_whose_plugin_is_missing_gets_a_stand_in(qapp):
    from SciQLop.components.plotting.panel_template import context_product_path
    ctx = _ctx(kind="sk_gone.cdf")
    assert ctx.kind == "sk_gone.cdf"
    assert "sk_gone.cdf" in source_kind(ctx.kind).inspector_line(ctx)
    assert "B: sk_gone.cdf" in graph_tooltip(_Graph(ctx))
    assert context_product_path(ctx) == ""


def test_saved_speasy_products_are_still_shared(qapp):
    from SciQLop.components.plotting.panel_template import PlotModel, ProductModel
    from SciQLop.components.plotting.ui.proxy_share import _plot_config
    plot = PlotModel(products=[ProductModel(path="speasy//amda//imf", kind="speasy", speasy_id="amda/imf")])
    assert _plot_config(plot) is not None
    plot = PlotModel(products=[ProductModel(path="vp//x", kind="vp", speasy_id="amda/imf")])
    assert _plot_config(plot) is None
