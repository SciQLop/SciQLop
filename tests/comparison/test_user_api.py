from datetime import datetime, timezone

import numpy as np
import pytest

from ..fixtures import *  # noqa: F401, F403
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel, TimeRangeModel

t0, t1 = 1_000.0, 1_100.0


@pytest.fixture
def opened(main_window, qtbot):
    before = set(main_window.panels())
    yield
    for panel in [p for p in main_window.panels() if p not in before]:
        main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: set(main_window.panels()) <= before)


def _iso(t):
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def _vp(name):
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def sine(start: float, stop: float, gain: float = 1.0):
        x = np.linspace(start, stop, 50)
        return x, gain * np.sin(x)

    return create_virtual_product(f"test_cmp_user_api/{name}", sine, VirtualProductType.Scalar, labels=["y"])


def _vp_path(vp):
    from SciQLop.user_api.plot._plots import to_product_path
    return "//".join(to_product_path(vp))


@pytest.fixture
def plot_panel_with_vp(main_window, qtbot, opened):
    from SciQLop.user_api.plot import PlotPanel
    template = PanelTemplate(name="P", time_range=TimeRangeModel(start=_iso(t0), stop=_iso(t1)),
                             plots=[PlotModel(products=[ProductModel(path=_vp_path(_vp("base")))])])
    impl = template.create_panel(main_window)
    impl = getattr(impl, "_impl", impl)
    qtbot.waitUntil(lambda: len(impl.plots()) == 1)
    return PlotPanel(impl)


def _compare(*args, **kwargs):
    from SciQLop.user_api.comparison import compare
    return compare(*args, **kwargs)


def test_compare_over_time_from_tuples(plot_panel_with_vp, qtbot):
    h = _compare(plot_panel_with_vp, over="time", variants=[(t0 + 86400, t1 + 86400)])
    assert h.view == "overlay" and len(h.variants) == 1
    h.view = "difference"
    assert h.view == "difference"


def test_compare_accepts_a_panel_name_and_labels(plot_panel_with_vp, main_window):
    before = set(main_window.panels())
    h = _compare(plot_panel_with_vp.name, over="time", variants=[(t0 + 10, t1 + 10)], labels=["later"])
    assert h.variants == ["later"]
    assert [p.objectName() for p in set(main_window.panels()) - before] == [h.name]


def test_compare_rejects_unknown_dimension(plot_panel_with_vp):
    with pytest.raises(ValueError, match="time"):
        _compare(plot_panel_with_vp, over="nope", variants=[])


def test_compare_rejects_no_variants(plot_panel_with_vp):
    with pytest.raises(ValueError, match="at least one"):
        _compare(plot_panel_with_vp, over="time", variants=[])


def test_compare_rejects_mismatched_labels(plot_panel_with_vp):
    with pytest.raises(ValueError, match="labels"):
        _compare(plot_panel_with_vp, over="time", variants=[(t0 + 10, t1 + 10)], labels=["a", "b"])


def test_inapplicable_view_raises_with_reason(plot_panel_with_vp):
    h = _compare(plot_panel_with_vp, over="time", variants=[(t0 + 10, t1 + 10), (t0 + 20, t1 + 20)])
    with pytest.raises(ValueError, match="exactly two sides"):
        h.view = "difference"
    assert h.view == "overlay"


def test_unknown_view_raises(plot_panel_with_vp):
    h = _compare(plot_panel_with_vp, over="time", variants=[(t0 + 10, t1 + 10)])
    with pytest.raises(ValueError, match="overlay"):
        h.view = "nope"


def test_view_options(plot_panel_with_vp):
    h = _compare(plot_panel_with_vp, over="time", variants=[(t0 + 10, t1 + 10)], view="difference")
    assert h.options()["operation"] == "difference"
    h.set_options("difference", operation="ratio")
    assert h.options("difference")["operation"] == "ratio"
    with pytest.raises(ValueError, match="log_ratio"):
        h.set_options("difference", operation="bogus")


def test_compare_over_product_from_virtual_product(plot_panel_with_vp):
    other = _vp("other")
    h = _compare(plot_panel_with_vp, over="product", variants=[other])
    [variant] = h._get_impl_or_raise().comparison.variants
    assert variant.params["path"] == _vp_path(other) and tuple(variant.params["target"]) == (0, 0)


def test_compare_over_product_rejects_unknown_path_and_target(plot_panel_with_vp):
    with pytest.raises(ValueError, match="products tree"):
        _compare(plot_panel_with_vp, over="product", variants=["no//such//product"])
    with pytest.raises(ValueError, match="target"):
        _compare(plot_panel_with_vp, over="product", variants=[_vp("other2")], target=(3, 0))


def test_compare_over_settings_from_knob_dicts(plot_panel_with_vp):
    h = _compare(plot_panel_with_vp, over="settings", variants=[{"gain": 2}])
    [variant] = h._get_impl_or_raise().comparison.variants
    assert variant.params == {"target": [0, 0], "knobs": {"gain": 2}} and h.variants == ["gain=2"]


def _catalog_event():
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    return CatalogEvent(uuid="e", start=datetime.fromtimestamp(t0, timezone.utc),
                        stop=datetime.fromtimestamp(t1, timezone.utc))


def _speasy_event():
    from speasy.products.catalog import Event
    return Event(datetime.fromtimestamp(t0, timezone.utc), datetime.fromtimestamp(t1, timezone.utc))


def _time_range():
    from SciQLop.user_api import TimeRange
    return TimeRange(t0, t1)


@pytest.mark.parametrize("make", [
    lambda: (t0, t1),
    lambda: (datetime.fromtimestamp(t0, timezone.utc), datetime.fromtimestamp(t1, timezone.utc)),
    _catalog_event, _speasy_event, _time_range,
], ids=["floats", "datetimes", "catalog_event", "speasy_event", "time_range"])
def test_time_variant_coercion(qapp, make):
    from SciQLop.user_api.comparison import _time_variant
    assert _time_variant(make()).params == {"start": t0, "stop": t1}


def _tool(name):
    from SciQLop.components.agents.tools.contributed import AGENT_TOOLS
    return AGENT_TOOLS.get(name)


def test_agent_tool_creates_comparison(plot_panel_with_vp, main_window):
    before = set(main_window.panels())
    text = _tool("sciqlop_compare").call({
        "panel": plot_panel_with_vp.name, "over": "time",
        "variants": [[_iso(t0 + 10), _iso(t1 + 10)], [_iso(t0 + 20), _iso(t1 + 20)]]})
    [name] = [p.objectName() for p in set(main_window.panels()) - before]
    assert name in text and "3 sides" in text and "exactly two sides" in text
    text = _tool("sciqlop_set_comparison_view").call({"name": name, "view": "overlay"})
    assert name in text and "overlay" in text


def test_agent_tool_set_view_reports_refusal(plot_panel_with_vp, main_window):
    from SciQLop.user_api.comparison import compare
    h = compare(plot_panel_with_vp, over="time", variants=[(t0 + 10, t1 + 10)])
    text = _tool("sciqlop_set_comparison_view").call(
        {"name": h.name, "view": "difference", "options": {"operation": "ratio"}})
    assert h.view == "difference" and h.options()["operation"] == "ratio" and h.name in text
    with pytest.raises(ValueError, match="no comparison panel"):
        _tool("sciqlop_set_comparison_view").call({"name": "nope", "view": "overlay"})


@pytest.fixture
def invoker():
    """The main-thread invoker KernelManager installs at runtime."""
    from jupyqt.qt.proxy import MainThreadInvoker
    from SciQLop.user_api import threading as sqp_threading
    previous = sqp_threading._invoker
    sqp_threading.init_invoker(MainThreadInvoker())
    yield
    sqp_threading.init_invoker(previous)


def _in_worker(qtbot, fn):
    import threading
    box = {}

    def run():
        try:
            box["result"] = fn()
        except BaseException as e:  # noqa: BLE001 — reported to the test
            box["error"] = e

    t = threading.Thread(target=run, name="fake-kernel-thread")
    t.start()
    qtbot.waitUntil(lambda: not t.is_alive(), timeout=5000)
    assert "error" not in box, box.get("error")
    return box["result"]


def test_panel_off_the_gui_thread_is_a_proxy(plot_panel_with_vp, qtbot, invoker):
    from SciQLop.user_api.threading import MainThreadProxy
    h = _compare(plot_panel_with_vp, over="time", variants=[(t0 + 10, t1 + 10)])
    assert not isinstance(h.panel, MainThreadProxy)
    panel = _in_worker(qtbot, lambda: h.panel)
    assert isinstance(panel, MainThreadProxy)
    assert _in_worker(qtbot, lambda: panel.objectName()) == h.name


@pytest.mark.parametrize("bad", ["2020-01-01", ("garbage", "more garbage"), 42])
def test_invalid_time_variant_raises_value_error(plot_panel_with_vp, bad):
    with pytest.raises(ValueError):
        _compare(plot_panel_with_vp, over="time", variants=[bad])


def test_set_view_tool_checks_options_before_switching(plot_panel_with_vp):
    h = _compare(plot_panel_with_vp, over="time", variants=[(t0 + 10, t1 + 10)])
    with pytest.raises(ValueError, match="log_ratio"):
        _tool("sciqlop_set_comparison_view").call(
            {"name": h.name, "view": "difference", "options": {"operation": "bogus"}})
    assert h.view == "overlay"


@pytest.mark.parametrize("tool, payload, missing", [
    ("sciqlop_compare", {"over": "time", "variants": []}, "panel"),
    ("sciqlop_compare", {"panel": "P", "variants": []}, "over"),
    ("sciqlop_set_comparison_view", {"name": "x"}, "view"),
])
def test_agent_tools_name_a_missing_key(qapp, tool, payload, missing):
    with pytest.raises(ValueError, match=f"missing '{missing}'"):
        _tool(tool).call(payload)


def test_show_changes_nothing_when_the_view_does_not_apply(plot_panel_with_vp):
    h = _compare(plot_panel_with_vp, over="time", variants=[(t0 + 10, t1 + 10), (t0 + 20, t1 + 20)])
    with pytest.raises(ValueError, match="exactly two sides"):
        h.show("difference", operation="ratio")
    assert h.view == "overlay" and h.options("difference")["operation"] == "difference"
