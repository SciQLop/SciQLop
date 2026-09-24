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
