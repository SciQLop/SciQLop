"""list_virtual_products: the single source of truth is `providers`, the same
dict create_virtual_product and the %%vp magic both register into — see the
module docstring in SciQLop/user_api/virtual_products/__init__.py for why
there is no remove_virtual_product (SciQLopPlots' ProductsModel has no public
node-removal API that keeps the Qt model consistent; verified experimentally,
not shipped)."""
from tests.fixtures import *  # noqa: F401,F403


def test_list_virtual_products_reports_full_paths(qapp, main_window):
    from SciQLop.user_api.virtual_products import (
        create_virtual_product, VirtualProductType, list_virtual_products,
    )

    def f(start: float, stop: float):
        return None

    create_virtual_product("test_vp_lifecycle//alpha", f, VirtualProductType.Scalar, labels=["y"])
    create_virtual_product("test_vp_lifecycle//beta", f, VirtualProductType.Scalar, labels=["y"])

    paths = list_virtual_products()
    assert "test_vp_lifecycle//alpha" in paths
    assert "test_vp_lifecycle//beta" in paths


def test_list_virtual_products_redeclare_does_not_duplicate(qapp, main_window):
    from SciQLop.user_api.virtual_products import (
        create_virtual_product, VirtualProductType, list_virtual_products,
    )

    def f(start: float, stop: float):
        return None

    create_virtual_product("test_vp_lifecycle//redeclared", f, VirtualProductType.Scalar, labels=["y"])
    create_virtual_product("test_vp_lifecycle//redeclared", f, VirtualProductType.Scalar, labels=["y"])

    paths = list_virtual_products()
    assert paths.count("test_vp_lifecycle//redeclared") == 1
