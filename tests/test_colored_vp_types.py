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
