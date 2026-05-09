from unittest.mock import MagicMock, patch

from SciQLop.components.plotting.backend.data_provider import DataProvider, DataOrder
from SciQLop.core.graph_context import GraphContext


def test_data_provider_default_snippets_empty():
    p = DataProvider("test", DataOrder.X_FIRST)
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="test")
    assert p.python_snippets(ctx) == {}


def test_data_provider_default_extended_metadata_empty():
    p = DataProvider("test", DataOrder.X_FIRST)
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="test")
    assert p.extended_metadata(ctx) == {}


def test_speasy_python_snippets_has_two_variants():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="amda/imf", provider_name="Speasy")
    snippets = p.python_snippets(ctx)
    assert set(snippets.keys()) == {"Reproduce in SciQLop", "Notebook (matplotlib)"}


def test_speasy_sciqlop_snippet_uses_create_plot_panel():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="amda/imf", provider_name="Speasy",
                       product_path=["speasy", "amda", "imf"])
    s = p.python_snippets(ctx)["Reproduce in SciQLop"]
    assert "from SciQLop.user_api.plot import create_plot_panel" in s
    assert "create_plot_panel()" in s
    assert "panel.time_range = TimeRange" in s
    assert "panel.plot_product" in s
    # Either the speasy_id or the tree path appears
    assert "amda" in s


def test_speasy_matplotlib_snippet_imports_pyplot_and_plots():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="amda/imf", provider_name="Speasy")
    s = p.python_snippets(ctx)["Notebook (matplotlib)"]
    assert "import speasy as spz" in s
    assert "import matplotlib.pyplot as plt" in s
    assert "spz.get_data" in s
    assert "v.plot(ax=ax)" in s
    assert "plt.show()" in s


def test_speasy_sciqlop_snippet_includes_knobs_when_set():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="cda/mms", provider_name="Speasy",
                       knobs={"resolution": "high"})
    s = p.python_snippets(ctx)["Reproduce in SciQLop"]
    assert "product_inputs={'resolution': 'high'}" in s


def test_speasy_snippets_uses_iso_now_minus_1d_to_now_when_no_graph():
    """Without a live graph, the snippet should include ISO timestamps for
    roughly the last 24h, not a hardcoded 2020 placeholder."""
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    from datetime import datetime, timezone
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="amda/imf", provider_name="Speasy")
    s = p.python_snippets(ctx)["Notebook (matplotlib)"]
    this_year = str(datetime.now(timezone.utc).year)
    assert this_year in s, f"snippet should reflect the current year ({this_year}); got: {s[:200]}"


def test_speasy_snippets_empty_for_non_speasy_kind():
    from SciQLop.plugins.speasy_provider.speasy_provider import SpeasyPlugin
    p = SpeasyPlugin.__new__(SpeasyPlugin)
    p._name = "Speasy"
    ctx = GraphContext(kind="vp", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       vp_path="x", provider_name="vp-1")
    assert p.python_snippets(ctx) == {}


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


def test_easy_provider_snippets_module_level_callback(qtbot):
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
                       product_path=["root", "my_vp"],
                       knobs={"k": 0.5})
    out = p.python_snippets(ctx)
    assert "Reproduce in SciQLop" in out
    s = out["Reproduce in SciQLop"]
    assert "from SciQLop.user_api.plot import create_plot_panel" in s
    assert f"from {_tested_module_level_vp_callback.__module__} import" in s
    assert _tested_module_level_vp_callback.__qualname__ in s
    assert "knobs={'k': 0.5}" in s


def test_easy_provider_snippets_lambda_returns_stub(qtbot):
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
    out = p.python_snippets(ctx)
    s = out["Reproduce in SciQLop"]
    assert "not importable" in s
    assert "root/my_vp" in s


def test_easy_provider_snippets_empty_for_non_vp_kind(qtbot):
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    p = EasyProvider.__new__(EasyProvider)
    p._callback = _tested_module_level_vp_callback
    p._path = ["x"]
    p._knobs_kwarg_name = "knobs"
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P",
                       plot_index=0, graph_type="Line",
                       speasy_id="x/y", provider_name="Speasy")
    assert p.python_snippets(ctx) == {}


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

def test_speasy_notebook_uses_string_path_no_root_via_template(qtbot):
    """The matplotlib notebook snippet must use the slash-joined product
    path (no list literal, no ``root`` prefix). Regression: emitting
    ``ctx.product_path`` via ``repr`` produced ['root', 'speasy', ...].
    """
    from SciQLop.core.graph_context import build_speasy_ctx
    from SciQLop.plugins.speasy_provider.speasy_provider import (
        _speasy_matplotlib_snippet,
    )
    from PySide6.QtCore import QObject

    class _G(QObject):
        def __init__(self): super().__init__(); self.setObjectName("g")

    ctx = build_speasy_ctx(
        _G(), panel_name="P", plot_index=0,
        speasy_id="amda/ACE/b_gsm", graph_type="Line",
        product_path=["root", "speasy", "amda", "ACE", "b_gsm"],
    )
    out = _speasy_matplotlib_snippet(ctx, graph=None)
    assert "[\x27root\x27" not in out, "list-literal product path leaked"
    assert "\x22amda/ACE/b_gsm\x22" in out, f"expected slash form; got: {out!r}"


def test_speasy_sciqlop_reproducer_emits_slash_path_no_root():
    from SciQLop.core.graph_context import build_speasy_ctx
    from SciQLop.plugins.speasy_provider.speasy_provider import (
        _speasy_sciqlop_snippet,
    )
    from PySide6.QtCore import QObject

    class _G(QObject):
        def __init__(self): super().__init__(); self.setObjectName("g")

    ctx = build_speasy_ctx(
        _G(), panel_name="P", plot_index=0,
        speasy_id="amda/ACE/b_gsm", graph_type="Line",
        product_path=["root", "speasy", "amda", "ACE", "b_gsm"],
    )
    out = _speasy_sciqlop_snippet(ctx, graph=None)
    assert "[\x27root\x27" not in out
    assert 'panel.plot_product("speasy/amda/ACE/b_gsm")' in out

