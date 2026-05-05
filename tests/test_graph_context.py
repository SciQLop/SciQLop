import pytest
from pydantic import ValidationError

from SciQLop.core.graph_context import GraphContext, GraphRichRefs, _is_importable


def test_speasy_context_minimal():
    ctx = GraphContext(
        kind="speasy", graph_id="g1", panel_name="P", plot_index=0,
        graph_type="Line", speasy_id="amda/imf", provider_name="Speasy",
    )
    assert ctx.kind == "speasy"
    assert ctx.knobs == {}
    assert ctx.vp_path is None


def test_vp_context_with_knobs():
    ctx = GraphContext(
        kind="vp", graph_id="g2", panel_name="P", plot_index=1,
        graph_type="Line", vp_path="my/vp", provider_name="vp_callback-1",
        callback_qualname="my_callback", callback_module="my_module",
        knobs={"k": 0.5, "name": "x"},
    )
    assert ctx.knobs == {"k": 0.5, "name": "x"}


def test_extra_field_rejected_at_write():
    with pytest.raises(ValidationError):
        GraphContext(
            kind="speasy", graph_id="g", panel_name="P", plot_index=0,
            graph_type="Line", typo_field="oops",
        )


def test_to_meta_data_drops_none_fields():
    ctx = GraphContext(
        kind="speasy", graph_id="g", panel_name="P", plot_index=0,
        graph_type="Line", speasy_id="amda/imf", provider_name="Speasy",
    )
    md = ctx.to_meta_data()
    assert md["kind"] == "speasy"
    assert md["speasy_id"] == "amda/imf"
    assert "vp_path" not in md


def test_to_meta_data_round_trip():
    ctx = GraphContext(
        kind="vp", graph_id="g", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="my/vp", provider_name="my_vp-1",
        callback_qualname="cb", callback_module="m",
        knobs={"a": 1},
    )
    assert GraphContext.model_validate(ctx.to_meta_data()) == ctx


def test_graph_rich_refs_defaults_none():
    refs = GraphRichRefs()
    assert refs.callback is None
    assert refs.knobs_model is None


def _module_level_function():
    return 42


def test_is_importable_module_level_true():
    assert _is_importable(_module_level_function.__module__,
                          _module_level_function.__qualname__,
                          _module_level_function) is True


def test_is_importable_lambda_false():
    f = lambda: 0
    assert _is_importable(f.__module__, f.__qualname__, f) is False


def test_is_importable_closure_false():
    def outer():
        def inner(): return 0
        return inner
    f = outer()
    assert "<locals>" in f.__qualname__
    assert _is_importable(f.__module__, f.__qualname__, f) is False


def test_is_importable_aliased_false():
    other = lambda: 1
    assert _is_importable(_module_level_function.__module__,
                          _module_level_function.__qualname__,
                          other) is False


def test_is_importable_unknown_module_false():
    assert _is_importable("definitely_not_a_module", "x", lambda: 0) is False
