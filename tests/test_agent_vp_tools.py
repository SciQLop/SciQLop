"""Agent tools for the virtual-product lifecycle (list; see docstring in
SciQLop/user_api/virtual_products/__init__.py for why removal isn't shipped).

Importing anything under SciQLop.components.agents.tools needs a QApplication,
so each test takes qtbot/main_window and imports inside the function, matching
tests/test_agent_panel_tools.py.
"""
import asyncio
import json

from tests.fixtures import *  # noqa: F401,F403


def _tool(main_window, tool_name):
    from SciQLop.components.agents.tools._builder import build_sciqlop_tools
    return next(t for t in build_sciqlop_tools(main_window) if t["name"] == tool_name)


def _call(main_window, tool_name, **payload):
    result = _tool(main_window, tool_name)["handler"](payload)
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)
    return result["content"][0]["text"]


def test_list_virtual_products_tool_is_read_only(main_window):
    assert _tool(main_window, "sciqlop_list_virtual_products")["gated"] is False


def test_list_virtual_products_reports_created_vps(main_window):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    def f(start: float, stop: float):
        return None

    create_virtual_product("test_agent_vp_tools//one", f, VirtualProductType.Scalar, labels=["y"])
    create_virtual_product("test_agent_vp_tools//two", f, VirtualProductType.Scalar, labels=["y"])

    paths = json.loads(_call(main_window, "sciqlop_list_virtual_products"))
    assert "test_agent_vp_tools//one" in paths
    assert "test_agent_vp_tools//two" in paths


def test_list_virtual_products_excludes_non_vp_providers(main_window):
    paths = json.loads(_call(main_window, "sciqlop_list_virtual_products"))
    assert "speasy" not in paths
    assert all(isinstance(p, str) for p in paths)
