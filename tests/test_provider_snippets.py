from unittest.mock import MagicMock, patch

from SciQLop.components.plotting.backend.data_provider import DataProvider, DataOrder
from SciQLop.core.graph_context import GraphContext


def test_data_provider_default_snippet_returns_none():
    p = DataProvider("test", DataOrder.X_FIRST)
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="test")
    assert p.python_snippet(ctx) is None


def test_data_provider_default_extended_metadata_empty():
    p = DataProvider("test", DataOrder.X_FIRST)
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="test")
    assert p.extended_metadata(ctx) == {}


def test_speasy_python_snippet_basic():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)  # bypass __init__ (heavy)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="amda/imf", provider_name="Speasy")
    snippet = p.python_snippet(ctx)
    assert snippet is not None
    assert "import speasy as spz" in snippet
    assert "amda/imf" in snippet
    assert "spz.get_data" in snippet
    assert "product_inputs" not in snippet


def test_speasy_python_snippet_with_knobs():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="cda/mms", provider_name="Speasy",
                       knobs={"resolution": "high"})
    snippet = p.python_snippet(ctx)
    assert "product_inputs={'resolution': 'high'}" in snippet


def test_speasy_python_snippet_returns_none_for_non_speasy_kind():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="x", provider_name="vp-1")
    assert p.python_snippet(ctx) is None


def test_speasy_extended_metadata_unknown_id():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="bogus/id", provider_name="Speasy")
    with patch.object(p, "_resolve_index", return_value=None):
        assert p.extended_metadata(ctx) == {}


def test_speasy_extended_metadata_known_id():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="amda/imf", provider_name="Speasy")
    fake_index = MagicMock()
    fake_index.parameter_type = "Vector"
    with patch.object(p, "_resolve_index", return_value=fake_index):
        out = p.extended_metadata(ctx)
    assert out["speasy_id"] == "amda/imf"
    assert out["parameter_type"] == "Vector"
    assert "inventory" in out
