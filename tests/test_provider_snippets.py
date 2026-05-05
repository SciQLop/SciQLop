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
