"""Plot kinds (spec §4.3, §5): a product plots through its kind's default plot kind."""
import pytest

from SciQLop.core.extensions import owned_by
from SciQLop.core.plot_kinds import (PLOT_KINDS, PROJECTION, TIMESERIES, PlotKind, plot_kind_for_product,
                                     plot_kind_of, plugin_of)
from SciQLop.core.product_kinds import PRODUCT_KIND_KEY, PRODUCT_KINDS, ProductKind


@pytest.fixture(autouse=True)
def core_extension_points(qapp):
    from SciQLop.components.extension_points import prepare_extension_points
    prepare_extension_points()


@pytest.fixture
def plugin_kinds(qapp):
    """A plugin product kind plotted by a plugin plot kind, and one product node of that kind."""
    from SciQLop.core.enums import ParameterType
    from SciQLop.core.models import ProductsModelNodeType, add_product_node
    calls = []
    with owned_by("pk1c"):
        PRODUCT_KINDS.contribute(ProductKind("pk1c.distribution", "VDF", 3, "pk1c.slice_plot"))
        PRODUCT_KINDS.contribute(ProductKind("pk1c.orphan", "Orphan", 3, "pk1c.gone_plot"))
        PLOT_KINDS.contribute(PlotKind("pk1c.slice_plot", "Slice",
                                       plot_product=lambda target, product, kw: calls.append((target, product, kw))
                                       or ("plot", "graph")))
    add_product_node(["pk1c"], "dist", "pk1c", {PRODUCT_KIND_KEY: "pk1c.distribution"},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
    add_product_node(["pk1c"], "orphan", "pk1c", {PRODUCT_KIND_KEY: "pk1c.orphan"},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)
    yield calls
    PLOT_KINDS.remove_owner("pk1c")
    PRODUCT_KINDS.remove_owner("pk1c")


def test_core_plot_kinds_are_owned_by_sciqlop(qapp):
    for kid in (TIMESERIES, PROJECTION):
        assert PLOT_KINDS.owner_of(kid) == "sciqlop"


def test_a_product_plots_through_its_kinds_default_plot_kind(plugin_kinds):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    target = object()
    assert plot_kind_for_product(["pk1c", "dist"]).id == "pk1c.slice_plot"
    assert plot_product(target, ["pk1c", "dist"], plot_type="x") == ("plot", "graph")
    assert plugin_kinds == [(target, ["pk1c", "dist"], {"plot_type": "x"})]


def test_a_missing_plot_kind_plots_nothing(plugin_kinds):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    assert plot_kind_for_product(["pk1c", "orphan"]) is None
    assert plot_product(object(), ["pk1c", "orphan"]) is None


def test_unknown_products_have_no_plot_kind(qapp):
    assert plot_kind_for_product(["pk1c_nowhere", "x"]) is None
    assert plot_kind_for_product("not a list") is None


def test_plot_kind_of_defaults_to_time_series(qapp):
    assert plot_kind_of(None) is None
    assert plot_kind_of(object()).id == TIMESERIES


def test_plugin_of_is_the_id_prefix():
    assert plugin_of("vdf.slice_plot") == "vdf"
