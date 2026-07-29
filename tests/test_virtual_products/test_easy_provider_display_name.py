"""EasyProvider node naming and metadata passthrough.

A virtual product's node name is what SciQLop uses as the *graph* label on both
the in-process path (time_sync_panel.py's `target.plot(..., name=node.name())`)
and the remote path (plot_remote.py's `add_remote_color_map(node.name())`), and
as the label in the product tree. Until `display_name` existed it was forced to
be the last vp_path segment, so a product at `radio/ilofar/X` could only ever be
called "X".
"""
import pytest

import SciQLop.components.plotting.backend.easy_provider as ep
from SciQLop.components.plotting.backend.easy_provider import EasyProvider
from SciQLop.core.enums import ParameterType


def _spectrogram_callback(start: float, stop: float):
    return None


@pytest.fixture
def registered(monkeypatch):
    """Capture the ProductsModelNode a provider registers.

    `easy_provider` calls `products.add_node(path, node)` (module-level
    `products` imported from SciQLop.core.models). Spying on that is more
    direct than reading the node back out of the global model, and keeps each
    test from depending on registration order.
    """
    captured = {}

    def _add_node(path, node):
        captured["path"] = path
        captured["node"] = node

    monkeypatch.setattr(ep.products, "add_node", _add_node)

    def _make(path, **kwargs):
        EasyProvider(path, _spectrogram_callback, ParameterType.Spectrogram,
                     metadata=kwargs.pop("metadata", {}), **kwargs)
        return captured["node"]

    return _make


def test_node_name_defaults_to_the_path_leaf(registered):
    """Unchanged behaviour: a provider that passes no display_name still names
    its node after the last path segment."""
    assert registered("test_display/default_leaf").name() == "default_leaf"


def test_display_name_overrides_the_path_leaf(registered):
    assert registered("test_display/override_leaf",
                      display_name="I-LOFAR X pol").name() == "I-LOFAR X pol"


def test_empty_display_name_falls_back_to_the_leaf(registered):
    """An empty string is 'not supplied', not 'name this product nothing'."""
    assert registered("test_display/empty_display",
                      display_name="").name() == "empty_display"


def test_supplied_description_survives_registration(registered):
    """Regression: the metadata dict used to be built with
    `{**metadata, "description": <generated>}`, so a caller's curated
    description was silently replaced by boilerplate in every tooltip."""
    node = registered("test_display/keeps_description",
                      metadata={"description": "I-LOFAR mode 357 BST dynamic spectrum"})
    assert node.metadata()["description"] == "I-LOFAR mode 357 BST dynamic spectrum"


def test_description_is_generated_when_absent(registered):
    node = registered("test_display/generated_description")
    assert "Virtual Spectrogram product" in node.metadata()["description"]


def test_virtual_spectrogram_forwards_display_name(monkeypatch):
    """dock.py registers its live streams through VirtualSpectrogram, not
    through make_rich_vp, so the name has to survive that path too."""
    import SciQLop.user_api.virtual_products as vp
    captured = {}

    def _add_node(path, node):
        captured["node"] = node

    monkeypatch.setattr(ep.products, "add_node", _add_node)
    vp.VirtualSpectrogram("test_display/via_virtual_spectrogram",
                          _spectrogram_callback,
                          display_name="e-CALLISTO BIR 01")
    assert captured["node"].name() == "e-CALLISTO BIR 01"
