"""A product must stay reachable at its own path after being given a label.

This is the regression test for the defect that got all the way to a final
review: `display_name` was implemented by replacing the node's name, but a
node's name is simultaneously its tree label, its plot label AND its lookup
key — `ProductsModel::node(path)` walks the tree matching `objectName()`. So
naming a product "I-LOFAR X pol" did not relabel `radio/I-LOFAR/X`, it moved
it, and every path-based plotting route broke:

    products.node(['radio', 'I-LOFAR', 'X'])  ->  None

Nothing caught it because every test in both repos stopped at a fake
`vp_factory` or a fake panel and never touched the real products model. These
tests register for real and look the product back up.
"""
import pytest

from SciQLop.components.plotting.backend.easy_provider import EasyProvider
from SciQLop.core.enums import ParameterType
from SciQLop.core.models import products


def _callback(start: float, stop: float):
    return None


def _register(path, **kwargs):
    EasyProvider(path, _callback, ParameterType.Spectrogram, metadata={}, **kwargs)
    return products.node(path.split('/'))


def test_product_with_a_display_name_is_reachable_at_its_own_path():
    node = _register("test_reach/labelled/X", display_name="I-LOFAR X pol")
    assert node is not None, (
        "the product must resolve at the path it was registered under; a "
        "display name is presentation and must not move it")
    assert node.name() == "X"


def test_display_name_does_not_create_a_node_at_the_label():
    """The bug's signature: the product appeared at a path spelled with its
    label. Assert that path stays empty."""
    _register("test_reach/no_ghost/Y", display_name="I-LOFAR Y pol")
    assert products.node(["test_reach", "no_ghost", "I-LOFAR Y pol"]) is None


def test_display_name_is_exposed_separately_from_the_name():
    node = _register("test_reach/exposed/Z", display_name="I-LOFAR Z pol")
    assert node.display_name() == "I-LOFAR Z pol"
    assert node.name() == "Z"


def test_display_name_defaults_to_the_node_name():
    """A product that sets no label is completely unchanged."""
    node = _register("test_reach/plain/FLUX")
    assert node.display_name() == "FLUX"
    assert node.name() == "FLUX"


@pytest.mark.parametrize("empty", ["", None])
def test_empty_display_name_falls_back_to_the_node_name(empty):
    """Empty means 'not supplied', not 'label this nothing'."""
    node = _register(f"test_reach/empty_{empty!r}/RAD1", display_name=empty)
    assert node.display_name() == "RAD1"
