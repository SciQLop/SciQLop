"""list_virtual_products: the single source of truth is the
sciqlop.virtual_products extension point, which create_virtual_product and the
%%vp magic both contribute to. remove_virtual_product (and a plugin's
withdrawal) takes a path out of it, with its tree node and provider: see
tests/test_virtual_product_contributions.py."""
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
