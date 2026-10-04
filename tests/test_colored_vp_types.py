import numpy as np
import pytest

from SciQLop.user_api.data_types import (
    Colored, Scalar, Vector, MultiComponent, Spectrogram, VPTypeInfo, extract_vp_type_info,
)


def test_colored_vector_annotation_keeps_labels_and_is_colored():
    info = extract_vp_type_info(Colored[Vector["X", "Y", "Z"]])
    assert info == VPTypeInfo(product_type="vector", labels=["X", "Y", "Z"], colored=True)


def test_colored_bare_type_annotation():
    assert extract_vp_type_info(Colored[Scalar]) == VPTypeInfo("scalar", None, colored=True)
    assert extract_vp_type_info(Colored[MultiComponent]).colored is True


def test_plain_annotation_is_not_colored():
    assert extract_vp_type_info(Vector).colored is False


def test_colored_spectrogram_is_rejected():
    with pytest.raises(TypeError, match="Spectrogram"):
        Colored[Spectrogram]


def test_colored_holds_data_and_color():
    t = np.arange(3.0)
    c = Colored((t, t), color=t)
    assert c.data[0] is t and c.color is t


@pytest.fixture
def _no_product_tree(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def test_create_virtual_product_declares_a_colour_axis(_no_product_tree):
    from SciQLopPlots import ColorGradient
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product("t/colored", lambda start, stop: None, VirtualProductType.Vector,
                                labels=["X", "Y", "Z"], colored=True,
                                color_label="|B| (nT)", color_gradient="thermal")
    axis = vp._impl.color_axis(None)
    assert axis.label == "|B| (nT)" and axis.gradient == ColorGradient.Thermal


def test_default_colour_gradient_is_jet(_no_product_tree):
    from SciQLopPlots import ColorGradient
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product("t/jet", lambda start, stop: None, VirtualProductType.Scalar,
                                labels=["a"], colored=True)
    assert vp._impl.color_axis(None).gradient == ColorGradient.Jet


def test_uncoloured_by_default(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product("t/plain", lambda start, stop: None, VirtualProductType.Scalar, labels=["a"])
    assert vp._impl.color_axis(None) is None


def test_colored_spectrogram_is_refused(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    with pytest.raises(ValueError, match="Spectrogram"):
        create_virtual_product("t/spec", lambda start, stop: None, VirtualProductType.Spectrogram,
                               colored=True)


def test_unknown_gradient_is_refused_early(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    with pytest.raises(ValueError, match="gradient"):
        create_virtual_product("t/bad", lambda start, stop: None, VirtualProductType.Scalar,
                               labels=["a"], colored=True, color_gradient="nope")


def test_scalar_label_comes_from_the_return_annotation(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.virtual_products.types import Scalar

    B2 = Scalar["|B|^2"]  # an alias: flake8 reads a string inside an annotation as code

    def bt2(start: float, stop: float) -> B2:
        return None

    vp = create_virtual_product("t/bt2", bt2, VirtualProductType.Scalar)
    assert vp._impl._columns == ["|B|^2"]


def test_vector_labels_come_from_the_return_annotation(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.virtual_products.types import Vector

    B = Vector["bx", "by", "bz"]

    def b(start: float, stop: float) -> B:
        return None

    vp = create_virtual_product("t/b", b, VirtualProductType.Vector)
    assert vp._impl._columns == ["bx", "by", "bz"]


def test_explicit_labels_win_over_the_annotation(_no_product_tree):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.virtual_products.types import Scalar

    B2 = Scalar["|B|^2"]

    def bt2(start: float, stop: float) -> B2:
        return None

    vp = create_virtual_product("t/bt2x", bt2, VirtualProductType.Scalar, labels=["B2"])
    assert vp._impl._columns == ["B2"]


@pytest.mark.parametrize("product_type, labels", [
    ("Scalar", ["a"]), ("Vector", ["x", "y", "z"]), ("MultiComponent", ["a", "b"]), ("Spectrogram", None)])
def test_display_name_reaches_every_product_type(qapp, monkeypatch, product_type, labels):
    from SciQLop.core.models import products
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    nodes = []
    monkeypatch.setattr(products, "add_node", lambda path, node: nodes.append(node))
    create_virtual_product(f"t/dn_{product_type}", lambda start, stop: None,
                           VirtualProductType[product_type], labels=labels, display_name="Pretty")
    assert nodes[-1].display_name() == "Pretty"
