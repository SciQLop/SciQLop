"""Product kinds (spec §4.2): a data shape per product; nodes say theirs, or their parameter type does."""
import pytest

from SciQLop.core.enums import ParameterType
from SciQLop.core.extensions import owned_by
from SciQLop.core.product_kinds import (BOUNDARY, LAYER, MULTICOMPONENT, PRODUCT_KIND_KEY, PRODUCT_KINDS, SCALAR,
                                        SCENE, SPECTROGRAM, VECTOR, ProductKind, product_kind_of)


class _Node:
    def __init__(self, parameter_type=ParameterType.Scalar, **metadata):
        self._pt, self._md = parameter_type, metadata

    def parameter_type(self):
        return self._pt

    def metadata(self, key=None):
        return self._md.get(key) if key else dict(self._md)


@pytest.fixture
def withdraw(qapp):
    yield
    PRODUCT_KINDS.remove_owner("pk_demo")


def test_core_kinds_are_owned_by_sciqlop(qapp):
    for kid in (SCALAR, VECTOR, MULTICOMPONENT, SPECTROGRAM, SCENE, BOUNDARY, LAYER):
        assert PRODUCT_KINDS.owner_of(kid) == "sciqlop"
    assert PRODUCT_KINDS.get(SPECTROGRAM).arity == 3 and PRODUCT_KINDS.get(VECTOR).arity == 2


@pytest.mark.parametrize("pt, kid", [(ParameterType.Scalar, SCALAR), (ParameterType.Vector, VECTOR),
                                     (ParameterType.Multicomponents, MULTICOMPONENT),
                                     (ParameterType.Spectrogram, SPECTROGRAM)])
def test_untagged_nodes_are_read_by_parameter_type(pt, kid):
    assert product_kind_of(_Node(pt)).id == kid


def test_untagged_node_without_a_data_parameter_type_has_no_kind(qapp):
    assert product_kind_of(_Node(ParameterType.NotAParameter)) is None


def test_the_tag_wins_over_the_parameter_type(withdraw):
    with owned_by("pk_demo"):
        PRODUCT_KINDS.contribute(ProductKind("pk_demo.distribution", "VDF", 3, "pk_demo.slice_plot"))
    node = _Node(ParameterType.Scalar, **{PRODUCT_KIND_KEY: "pk_demo.distribution"})
    assert product_kind_of(node).id == "pk_demo.distribution"


def test_a_tag_whose_plugin_is_missing_is_not_read_as_its_parameter_type(qapp):
    assert product_kind_of(_Node(ParameterType.Scalar, **{PRODUCT_KIND_KEY: "pk_gone.distribution"})) is None


def test_scene_and_boundary_nodes_are_tagged(qapp, monkeypatch):
    from SciQLop.components.scenes import tree
    added = []
    monkeypatch.setattr(tree, "add_product_node", lambda *args, **kw: added.append(args))
    tree._add_node(["Scenes", "pk_scene"], "scene", "d")
    tree._add_node(["Models", "Earth", "magnetopause", "pk_mp"], "boundary", "d")
    assert [a[3][PRODUCT_KIND_KEY] for a in added] == [SCENE, BOUNDARY]


def test_virtual_product_nodes_are_tagged(qapp):
    import numpy as np
    from SciQLopPlots import ProductsModel
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def spec(start: float, stop: float):
        t = np.arange(3.0)
        return t, np.arange(4.0), np.ones((3, 4))

    create_virtual_product("pk_tests/spec", spec, VirtualProductType.Spectrogram)
    node = ProductsModel.node(["pk_tests", "spec"])
    assert node is not None and node.metadata()[PRODUCT_KIND_KEY] == SPECTROGRAM
