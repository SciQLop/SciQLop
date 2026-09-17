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


def test_snapshot_tools_return_json(main_window, qtbot):
    from SciQLop.user_api.plot import create_plot_panel
    panel = create_plot_panel()
    try:
        for tool_name in ("sciqlop_active_panel", "sciqlop_list_panels", "sciqlop_window_state"):
            parsed = json.loads(_call(main_window, tool_name))
            assert panel.name in json.dumps(parsed), tool_name
    finally:
        panel.close()
