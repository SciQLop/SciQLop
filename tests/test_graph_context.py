import pytest
from pydantic import ValidationError
from PySide6.QtCore import QObject

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


class _FakeGraph(QObject):
    """Minimal stand-in for SciQLopPlots.SciQLopGraphInterface for tests."""
    def __init__(self, name="fakegraph"):
        super().__init__()
        self._md = {}
        self.setObjectName(name)

    def meta_data(self):
        return dict(self._md)

    def set_meta_data(self, d):
        self._md = dict(d)


def test_attach_context_writes_meta_data(qtbot):
    from SciQLop.core.graph_context import attach_context
    g = _FakeGraph("g1")
    ctx = GraphContext(
        kind="speasy", graph_id="g1", panel_name="P", plot_index=0,
        graph_type="Line", speasy_id="amda/imf", provider_name="Speasy",
    )
    attach_context(g, ctx)
    assert g.meta_data()["kind"] == "speasy"
    assert g.meta_data()["speasy_id"] == "amda/imf"


def test_context_of_round_trip(qtbot):
    from SciQLop.core.graph_context import attach_context, context_of
    g = _FakeGraph("g2")
    ctx = GraphContext(
        kind="vp", graph_id="g2", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="my/vp", provider_name="my_vp-1",
        callback_qualname="cb", callback_module="m",
    )
    attach_context(g, ctx)
    out = context_of(g)
    assert out is not None
    assert out.kind == "vp"
    assert out.vp_path == "my/vp"


def test_context_of_empty_returns_none(qtbot):
    from SciQLop.core.graph_context import context_of
    g = _FakeGraph("g3")
    assert context_of(g) is None


def test_context_of_garbage_returns_none(qtbot):
    from SciQLop.core.graph_context import context_of
    g = _FakeGraph("g4")
    g.set_meta_data({"kind": "speasy", "graph_id": "x",
                      "panel_name": "P", "plot_index": "not-an-int",
                      "graph_type": "Line"})
    assert context_of(g) is None


def test_context_of_filters_unknown_fields_for_forward_compat(qtbot):
    from SciQLop.core.graph_context import context_of
    g = _FakeGraph("g5")
    g.set_meta_data({
        "kind": "speasy", "graph_id": "g5", "panel_name": "P",
        "plot_index": 0, "graph_type": "Line", "speasy_id": "x/y",
        "future_field_we_dont_know": "value",
    })
    out = context_of(g)
    assert out is not None
    assert out.speasy_id == "x/y"


def test_rich_of_returns_refs(qtbot):
    from SciQLop.core.graph_context import attach_context, rich_of
    g = _FakeGraph("g6")
    ctx = GraphContext(
        kind="vp", graph_id="g6", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="x", provider_name="vp-1",
    )
    cb = lambda s, e: None
    refs = GraphRichRefs(callback=cb)
    attach_context(g, ctx, refs)
    out = rich_of("g6")
    assert out is refs


def test_destroy_evicts_rich_refs(qtbot):
    from SciQLop.core.graph_context import attach_context, rich_of
    g = _FakeGraph("g7")
    ctx = GraphContext(
        kind="vp", graph_id="g7", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="x", provider_name="vp-1",
    )
    attach_context(g, ctx, GraphRichRefs(callback=lambda s, e: None))
    assert rich_of("g7") is not None
    g.deleteLater()
    qtbot.wait(50)
    assert rich_of("g7") is None


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


def test_build_speasy_ctx():
    from SciQLop.core.graph_context import build_speasy_ctx
    g = _FakeGraph("g_speasy")
    ctx = build_speasy_ctx(g, panel_name="P", plot_index=2,
                           speasy_id="amda/imf", graph_type="Line",
                           knobs={"k": 1})
    assert ctx.kind == "speasy"
    assert ctx.graph_id == "g_speasy"
    assert ctx.panel_name == "P"
    assert ctx.plot_index == 2
    assert ctx.speasy_id == "amda/imf"
    assert ctx.provider_name == "Speasy"
    assert ctx.knobs == {"k": 1}


def test_build_vp_ctx():
    from SciQLop.core.graph_context import build_vp_ctx
    g = _FakeGraph("g_vp")

    def my_cb(start, stop): return None

    ctx = build_vp_ctx(g, panel_name="P", plot_index=0,
                       vp_path=["root", "x"], provider_name="my_vp-1",
                       callback=my_cb, graph_type="Line", knobs={})
    assert ctx.kind == "vp"
    assert ctx.vp_path == "root/x"
    assert ctx.callback_qualname == my_cb.__qualname__
    assert ctx.callback_module == my_cb.__module__
    assert ctx.provider_name == "my_vp-1"


def test_build_function_ctx():
    from SciQLop.core.graph_context import build_function_ctx
    g = _FakeGraph("g_fn")

    def fn(start, stop): return None

    ctx = build_function_ctx(g, panel_name="P", plot_index=1,
                             callback=fn, graph_type="Line")
    assert ctx.kind == "function"
    assert ctx.provider_name is None
    assert ctx.callback_qualname == fn.__qualname__


def test_build_static_ctx():
    from SciQLop.core.graph_context import build_static_ctx
    g = _FakeGraph("g_static")
    ctx = build_static_ctx(g, panel_name="P", plot_index=0,
                           graph_type="Line")
    assert ctx.kind == "static"
    assert ctx.provider_name is None
    assert ctx.speasy_id is None


def test_update_knobs_refreshes_meta_data(qtbot):
    from SciQLop.core.graph_context import attach_context, context_of, update_knobs
    g = _FakeGraph("g_knob")
    ctx = GraphContext(
        kind="vp", graph_id="g_knob", panel_name="P", plot_index=0,
        graph_type="Line", vp_path="x", provider_name="vp-1",
        knobs={"a": 1},
    )
    attach_context(g, ctx, GraphRichRefs(callback=lambda s, e: None))

    update_knobs(g, {"a": 99, "b": "x"})

    refreshed = context_of(g)
    assert refreshed.knobs == {"a": 99, "b": "x"}


def test_update_knobs_no_op_when_no_context(qtbot):
    from SciQLop.core.graph_context import update_knobs
    g = _FakeGraph("g_no_ctx")
    update_knobs(g, {"a": 1})
    assert g.meta_data() == {}
