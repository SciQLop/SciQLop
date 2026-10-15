"""Virtual products are contributions to sciqlop.virtual_products, keyed by '//'-joined product path."""
import numpy as np
import pytest

from tests.fixtures import *  # noqa: F401,F403

from SciQLop.components.plotting.backend import easy_provider
from SciQLop.components.plotting.backend.data_provider import providers
from SciQLop.components.plotting.backend.easy_provider import VIRTUAL_PRODUCTS, follow_virtual_products
from SciQLop.components.plotting.backend.remote.registry import remote_registry
from SciQLop.core.extensions import owned_by
from SciQLop.user_api.virtual_products import (
    VirtualProductType, create_virtual_product, list_virtual_products, remove_virtual_product,
)

T0 = 1_700_000_000.0


def f(start: float, stop: float):
    t = np.linspace(start, stop, 16)
    return t, np.sin(t)


def _remote_cb(start: float, stop: float):
    t = np.linspace(start, stop, 4)
    return t, np.zeros(4)


@pytest.fixture
def vps(qapp, main_window):
    follow_virtual_products()
    yield
    for key in VIRTUAL_PRODUCTS.keys():
        if key.startswith("vpc//"):
            VIRTUAL_PRODUCTS.remove(key)


def _create(path="vpc//a", **kwargs):
    return create_virtual_product(path, f, VirtualProductType.Scalar, labels=["y"], **kwargs)


def _node(path):
    from SciQLopPlots import ProductsModel
    return ProductsModel.instance().node(path)


def test_a_virtual_product_is_a_contribution(vps):
    _create()
    assert "vpc//a" in VIRTUAL_PRODUCTS
    assert VIRTUAL_PRODUCTS.owner_of("vpc//a") == "user"


def test_a_plugin_virtual_product_is_owned_by_the_plugin(vps):
    with owned_by("vp_demo"):
        _create()
    assert VIRTUAL_PRODUCTS.owner_of("vpc//a") == "vp_demo"


def test_withdrawal_removes_node_and_provider(vps):
    with owned_by("vp_demo"):
        _create()
    p = VIRTUAL_PRODUCTS.get("vpc//a")
    VIRTUAL_PRODUCTS.remove_owner("vp_demo")
    assert _node(["vpc", "a"]) is None
    assert p.name not in providers
    assert "vpc//a" not in list_virtual_products()


def test_remove_virtual_product(vps):
    _create()
    p = VIRTUAL_PRODUCTS.get("vpc//a")
    remove_virtual_product("vpc/a")
    assert _node(["vpc", "a"]) is None
    assert p.name not in providers
    assert "vpc//a" not in list_virtual_products()
    with pytest.raises(LookupError):
        remove_virtual_product("vpc/nowhere")


def test_redeclare_keeps_the_old_provider_registered(vps):
    _create()
    first = VIRTUAL_PRODUCTS.get("vpc//a")
    _create()
    second = VIRTUAL_PRODUCTS.get("vpc//a")
    assert first is not second
    assert first.name in providers and second.name in providers
    assert list_virtual_products().count("vpc//a") == 1


def test_takeover_from_another_owner_is_logged(vps, monkeypatch):
    warnings = []
    monkeypatch.setattr(easy_provider.log, "warning", warnings.append)
    with owned_by("a"):
        _create()
    with owned_by("b"):
        _create()
    takeovers = [w for w in warnings if "vpc//a" in w]
    assert len(takeovers) == 1 and "of a" in takeovers[0] and "from b" in takeovers[0]
    assert VIRTUAL_PRODUCTS.owner_of("vpc//a") == "b"


def test_wrong_type_is_refused(vps):
    with pytest.raises(TypeError):
        VIRTUAL_PRODUCTS.contribute(object())


def test_removing_an_out_of_process_product_unregisters_it(vps):
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    EasyScalar(path="vpc//remote", get_data_callback=_remote_cb, component_name="dens", metadata={},
               out_of_process=True)
    assert remote_registry().is_remote(["vpc", "remote"])
    remove_virtual_product("vpc//remote")
    assert not remote_registry().is_remote(["vpc", "remote"])


def test_withdrawn_while_plotted_does_not_crash(vps, qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLop.user_api.plot import create_plot_panel
    with owned_by("vp_demo"):
        _create()
    panel = create_plot_panel()
    panel.time_range = (T0, T0 + 100.0)
    plot, graph = plot_product(panel._impl, ["vpc", "a"])
    qtbot.wait(200)
    VIRTUAL_PRODUCTS.remove_owner("vp_demo")
    panel.time_range = (T0 + 50.0, T0 + 150.0)
    qtbot.wait(200)
    assert graph in plot.plottables()


VP_CELL = """
def vpc_cell(start: float, stop: float) -> Scalar["y"]:
    import numpy as np
    t = np.linspace(start, stop, 16)
    return t, np.sin(t)
"""


def test_vp_cell_rerun_after_removal_registers_again(vps):
    from SciQLop.user_api.virtual_products.magic import _vp_magic_impl
    _vp_magic_impl("--path vpc/cell", VP_CELL)
    assert "vpc//cell" in VIRTUAL_PRODUCTS
    remove_virtual_product("vpc/cell")
    assert _node(["vpc", "cell"]) is None
    _vp_magic_impl("--path vpc/cell", VP_CELL)
    assert "vpc//cell" in VIRTUAL_PRODUCTS
    assert _node(["vpc", "cell"]) is not None
