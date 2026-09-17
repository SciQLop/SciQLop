"""Agent tools that inspect and rearrange the plots inside a panel."""
import asyncio
import json

import numpy as np

from .fixtures import *


def _tool(main_window, tool_name):
    from SciQLop.components.agents.tools._builder import build_sciqlop_tools
    return next(t for t in build_sciqlop_tools(main_window) if t["name"] == tool_name)


def _call(main_window, tool_name, **payload):
    result = _tool(main_window, tool_name)["handler"](payload)
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    return result["content"][0]["text"]


def _layout(main_window, panel_name):
    return json.loads(_call(main_window, "sciqlop_describe_panel", name=panel_name))


def _panel_with_two_plots(qtbot):
    from SciQLop.user_api.plot import create_plot_panel
    panel = create_plot_panel()
    x = np.arange(10, dtype=float)
    panel.plot_data(x, x, name="first")
    panel.plot_data(x, 2 * x, name="second")
    panel.plot_data(x, 3 * x, plot_index=1, name="third")
    qtbot.waitUntil(lambda: len(panel.plots) == 2, timeout=2000)
    return panel


def test_describe_panel_reports_each_plot_and_its_graphs(main_window, qtbot):
    panel = _panel_with_two_plots(qtbot)
    try:
        layout = _layout(main_window, panel.name)
        assert layout["name"] == panel.name
        assert [p["index"] for p in layout["plots"]] == [0, 1]
        assert [g["name"] for g in layout["plots"][0]["graphs"]] == ["first"]
        assert [g["name"] for g in layout["plots"][1]["graphs"]] == ["second", "third"]
        assert layout["plots"][0]["type"] == "TimeSeries"
    finally:
        panel.close()


def test_describe_panel_unknown_name_is_an_error(main_window):
    assert "panel not found" in _call(main_window, "sciqlop_describe_panel", name="nope")


def test_move_plot_reorders_and_returns_new_layout(main_window, qtbot):
    panel = _panel_with_two_plots(qtbot)
    try:
        out = json.loads(_call(main_window, "sciqlop_move_plot", name=panel.name,
                               from_index=1, to_index=0))
        assert [g["name"] for g in out["plots"][0]["graphs"]] == ["second", "third"]
        assert [g["name"] for g in out["plots"][1]["graphs"]] == ["first"]
    finally:
        panel.close()


def test_remove_graph_drops_only_that_graph(main_window, qtbot):
    panel = _panel_with_two_plots(qtbot)
    try:
        out = json.loads(_call(main_window, "sciqlop_remove_graph", name=panel.name,
                               plot_index=1, graph_index=0))
        assert [g["name"] for g in out["plots"][1]["graphs"]] == ["third"]
        assert len(out["plots"]) == 2
    finally:
        panel.close()


def test_remove_plot_drops_the_subplot(main_window, qtbot):
    panel = _panel_with_two_plots(qtbot)
    try:
        out = json.loads(_call(main_window, "sciqlop_remove_plot", name=panel.name, plot_index=0))
        qtbot.waitUntil(lambda: len(panel.plots) == 1, timeout=2000)
        assert [g["name"] for g in out["plots"][0]["graphs"]] == ["second", "third"]
    finally:
        panel.close()


def test_plot_product_tool_is_gated_and_reports_unknown_product(main_window, qtbot):
    from SciQLop.user_api.plot import create_plot_panel
    panel = create_plot_panel()
    try:
        assert _tool(main_window, "sciqlop_plot_product")["gated"] is True
        out = _call(main_window, "sciqlop_plot_product", name=panel.name, product="no//such//thing")
        assert "no//such//thing" in out
        assert len(_layout(main_window, panel.name)["plots"]) == 0
    finally:
        panel.close()


def test_mutating_panel_tools_are_gated(main_window):
    for name in ("sciqlop_move_plot", "sciqlop_remove_graph", "sciqlop_remove_plot"):
        assert _tool(main_window, name)["gated"] is True, name


def test_user_api_move_plot_and_graphs(main_window, qtbot):
    panel = _panel_with_two_plots(qtbot)
    try:
        assert [g.name for g in panel.plots[1].graphs] == ["second", "third"]
        panel.move_plot(0, 1)
        assert [g.name for g in panel.plots[0].graphs] == ["second", "third"]
    finally:
        panel.close()


def test_every_panel_tool_reports_a_missing_panel_the_same_way(main_window):
    for tool_name, extra in (("sciqlop_screenshot_panel", {}), ("sciqlop_screenshot_plot", {"plot_index": 0}),
                             ("sciqlop_set_time_range", {"start": 0.0, "stop": 1.0}),
                             ("sciqlop_wait_for_plot_data", {}), ("sciqlop_describe_panel", {}),
                             ("sciqlop_move_plot", {"from_index": 0, "to_index": 1}),
                             ("sciqlop_remove_plot", {"plot_index": 0}),
                             ("sciqlop_remove_graph", {"plot_index": 0, "graph_index": 0}),
                             ("sciqlop_plot_product", {"product": "x"})):
        assert _call(main_window, tool_name, name="nope", **extra) == "panel not found: 'nope'", tool_name


def test_every_tool_handler_is_a_coroutine_with_a_gated_flag(main_window):
    from SciQLop.components.agents.tools._builder import build_sciqlop_tools
    for tool in build_sciqlop_tools(main_window):
        assert "gated" in tool, tool["name"]
        result = tool["handler"]({"name": "nope", "plot_index": 0})
        assert asyncio.iscoroutine(result), tool["name"]
        result.close()


def test_create_panel_uses_the_panels_own_name_not_a_list_diff(main_window, monkeypatch):
    from SciQLop.components.agents.tools import context

    def _boom():
        raise AssertionError("sciqlop_create_panel must not diff panel name lists")

    monkeypatch.setattr(context, "_panel_names", _boom)
    text = _call(main_window, "sciqlop_create_panel")
    from SciQLop.user_api.plot import plot_panel
    assert "created panel" in text
    name = text.split("`")[1]
    panel = plot_panel(name)
    try:
        assert panel is not None
        assert panel.name == name
    finally:
        panel.close()


def _unfocus_dock_manager(main_window, monkeypatch):
    # Headless tests never click a dock (the chat dock is usually what's
    # actually focused in a live session anyway); force the no-focus case.
    monkeypatch.setattr(main_window.dock_manager, "focusedDockWidget", lambda: None)


def test_no_name_and_no_focused_panel_with_several_panels_is_an_ambiguous_error(main_window, qtbot, monkeypatch):
    from SciQLop.user_api.plot import create_plot_panel
    p1 = create_plot_panel()
    p2 = create_plot_panel()
    try:
        _unfocus_dock_manager(main_window, monkeypatch)
        for tool_name, extra in (("sciqlop_describe_panel", {}), ("sciqlop_wait_for_plot_data", {})):
            out = _call(main_window, tool_name, **extra)
            assert "no unambiguous active panel" in out, tool_name
            assert p1.name in out and p2.name in out, tool_name
    finally:
        p1.close()
        p2.close()


def test_no_name_and_no_focused_panel_with_a_single_panel_still_resolves(main_window, qtbot, monkeypatch):
    from SciQLop.user_api.plot import create_plot_panel
    p = create_plot_panel()
    try:
        _unfocus_dock_manager(main_window, monkeypatch)
        layout = json.loads(_call(main_window, "sciqlop_describe_panel"))
        assert layout["name"] == p.name
    finally:
        p.close()


def test_describe_panel_reports_last_error_for_a_failing_vp(main_window, qtbot):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.plot import create_plot_panel

    def bad_vp(start: float, stop: float):
        raise RuntimeError("boom")

    vp = create_virtual_product("test_describe_panel_agent/bad", bad_vp,
                                VirtualProductType.Scalar, labels=["y"])
    panel = create_plot_panel()
    try:
        panel.plot_product(vp)
        qtbot.waitUntil(lambda: not panel.is_busy(), timeout=5000)
        graph = _layout(main_window, panel.name)["plots"][0]["graphs"][0]
        assert graph["last_error"] is not None
        assert "boom" in graph["last_error"]
    finally:
        panel.close()


def test_describe_panel_reports_no_error_and_point_count_for_a_working_vp(main_window, qtbot):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.plot import create_plot_panel

    def good_vp(start: float, stop: float):
        import numpy as np
        n = 5
        return np.linspace(start, stop, n), np.arange(n, dtype=float)

    vp = create_virtual_product("test_describe_panel_agent/good", good_vp,
                                VirtualProductType.Scalar, labels=["y"])
    panel = create_plot_panel()
    try:
        panel.plot_product(vp)
        qtbot.waitUntil(lambda: not panel.is_busy(), timeout=5000)
        graph = _layout(main_window, panel.name)["plots"][0]["graphs"][0]
        assert graph["last_error"] is None
        assert graph["busy"] is False
        assert graph["n_points"] > 0
    finally:
        panel.close()


def test_describe_panel_reports_axis_state(main_window, qtbot):
    panel = _panel_with_two_plots(qtbot)
    try:
        layout = _layout(main_window, panel.name)
        y_axis = layout["plots"][0]["y_axis"]
        assert "log" in y_axis and "range" in y_axis
    finally:
        panel.close()


def _vp_path_for_build_panel_test(suffix):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    def f(start: float, stop: float):
        return None

    path = f"test_build_panel_agent//{suffix}"
    create_virtual_product(path, f, VirtualProductType.Scalar, labels=["y"])
    return path


def test_build_panel_creates_a_multi_subplot_panel(main_window, qtbot):
    p1 = _vp_path_for_build_panel_test("p1")
    p2 = _vp_path_for_build_panel_test("p2")

    before = len(json.loads(_call(main_window, "sciqlop_list_panels")))
    out = json.loads(_call(main_window, "sciqlop_build_panel", plots=[
        {"products": [p1]},
        {"products": [p2], "y_log": True},
    ]))
    try:
        after = len(json.loads(_call(main_window, "sciqlop_list_panels")))
        assert after == before + 1
        assert [p["index"] for p in out["plots"]] == [0, 1]
        assert out["plots"][0]["graphs"][0]["product"] == p1
        assert out["plots"][1]["graphs"][0]["product"] == p2
        assert out["plots"][1]["y_axis"]["log"] is True
        assert out["plots"][0]["y_axis"]["log"] is False
    finally:
        from SciQLop.user_api.plot import plot_panel
        panel = plot_panel(out["name"])
        if panel is not None:
            panel.close()


def test_build_panel_unknown_product_creates_nothing(main_window):
    before = len(json.loads(_call(main_window, "sciqlop_list_panels")))
    out = _call(main_window, "sciqlop_build_panel", plots=[{"products": ["no//such//product"]}])
    assert "no//such//product" in out
    after = len(json.loads(_call(main_window, "sciqlop_list_panels")))
    assert after == before


def test_build_panel_tool_is_gated(main_window):
    assert _tool(main_window, "sciqlop_build_panel")["gated"] is True


def test_build_panel_applies_the_requested_time_range(main_window):
    p1 = _vp_path_for_build_panel_test("time_range")
    out = json.loads(_call(main_window, "sciqlop_build_panel",
                           time_range={"start": "2020-01-01T00:00:00Z", "stop": "2020-01-02T00:00:00Z"},
                           plots=[{"products": [p1]}]))
    try:
        import datetime
        expected_start = datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc).timestamp()
        expected_stop = datetime.datetime(2020, 1, 2, tzinfo=datetime.timezone.utc).timestamp()
        assert out["time_range"]["start"] == expected_start
        assert out["time_range"]["stop"] == expected_stop
    finally:
        from SciQLop.user_api.plot import plot_panel
        panel = plot_panel(out["name"])
        if panel is not None:
            panel.close()


def test_build_panel_rejects_an_empty_plots_list(main_window):
    out = _call(main_window, "sciqlop_build_panel", plots=[])
    assert "invalid panel spec" in out


def test_snapshot_tools_return_json(main_window, qtbot):
    from SciQLop.user_api.plot import create_plot_panel
    panel = create_plot_panel()
    try:
        for tool_name in ("sciqlop_active_panel", "sciqlop_list_panels", "sciqlop_window_state"):
            parsed = json.loads(_call(main_window, tool_name))
            assert panel.name in json.dumps(parsed), tool_name
    finally:
        panel.close()
