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


# Module-level callback for the importable case
def _tested_module_level_vp_callback(start, stop, knobs=None):
    return None


def test_easy_provider_snippet_module_level_callback(qtbot):
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._path = ["root", "my_vp"]
    p._callback = _tested_module_level_vp_callback
    p._knobs_kwarg_name = "knobs"
    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="root/my_vp", provider_name="my_vp-1",
                       callback_qualname=_tested_module_level_vp_callback.__qualname__,
                       callback_module=_tested_module_level_vp_callback.__module__,
                       knobs={"k": 0.5})
    snippet = p.python_snippet(ctx)
    assert snippet is not None
    assert f"from {_tested_module_level_vp_callback.__module__} import" in snippet
    assert _tested_module_level_vp_callback.__qualname__ in snippet
    assert "knobs={'k': 0.5}" in snippet


def test_easy_provider_snippet_lambda_returns_stub(qtbot):
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._path = ["root", "my_vp"]
    p._callback = lambda s, e: None
    p._knobs_kwarg_name = "knobs"
    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="root/my_vp", provider_name="my_vp-1",
                       callback_qualname=p._callback.__qualname__,
                       callback_module=p._callback.__module__)
    snippet = p.python_snippet(ctx)
    assert snippet is not None
    assert "not importable" in snippet
    assert "root/my_vp" in snippet


def test_easy_provider_snippet_kind_mismatch_returns_none(qtbot):
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._callback = _tested_module_level_vp_callback
    p._path = ["x"]
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="Speasy")
    assert p.python_snippet(ctx) is None


def test_easy_provider_extended_metadata_with_model(qtbot):
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    from pydantic import BaseModel

    class Knobs(BaseModel):
        k: float = 0.0

    p = EasyProvider.__new__(EasyProvider)
    p._path = ["root", "x"]
    p._callback = _tested_module_level_vp_callback
    p._knobs_model = Knobs
    p._knob_specs = []

    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="root/x", provider_name="x-1")
    out = p.extended_metadata(ctx)
    assert out["vp_path"] == "root/x"
    assert out["callback"]["qualname"] == _tested_module_level_vp_callback.__qualname__
    assert "k" in out["knobs_schema"]["properties"]
    assert out["knob_specs"] == []


def test_easy_provider_extended_metadata_without_model(qtbot):
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._path = ["root", "y"]
    p._callback = _tested_module_level_vp_callback
    p._knobs_model = None
    p._knob_specs = []

    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="root/y", provider_name="y-1")
    out = p.extended_metadata(ctx)
    assert out["knobs_schema"] is None
