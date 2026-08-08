"""ACP permission policy and MCP-layer gating.

The permission layer answers the agent's session/request_permission: SciQLop
MCP tools auto-approve unless gated; gated ones go through the dock's confirm
dialog when writes are enabled; the agent's built-in tools (shell, file
edits) are always rejected. The tool server re-checks the same gate inside
the tool call, so a tool the agent never asks permission for is still blocked.
"""
import asyncio
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    pytest.importorskip("acp") is None, reason="agent-client-protocol not installed"
)

from SciQLop.components.agents.acp.backend import AcpAgentBackend
from SciQLop.components.agents.acp.client import permission_answer


def _options():
    from acp.schema import PermissionOption
    return [
        PermissionOption(kind="allow_once", name="Allow once", option_id="allow-once"),
        PermissionOption(kind="allow_always", name="Always allow", option_id="allow-always"),
        PermissionOption(kind="reject_once", name="Reject once", option_id="reject-once"),
        PermissionOption(kind="reject_always", name="Always reject", option_id="reject-always"),
    ]


def _tool_call(title, raw_input=None):
    return SimpleNamespace(title=title, raw_input=raw_input or {})


def _backend(tools, write_mode="none", confirm_cb=None):
    backend = AcpAgentBackend.__new__(AcpAgentBackend)
    backend._tools = tools
    backend._tool_names = {t["name"] for t in tools}
    backend._gated_names = {t["name"] for t in tools if t.get("gated")}
    backend._confirm_cb = confirm_cb
    backend._write_mode = write_mode
    return backend


def _tool(name="sciqlop_dummy", gated=False):
    return {"name": name, "description": "d",
            "input_schema": {"type": "object", "properties": {}}, "gated": gated,
            "handler": lambda args: "ok"}


def _selected_option_id(response):
    return getattr(response.outcome, "option_id", None)


def test_read_tool_auto_approves():
    backend = _backend([_tool()])
    resp = asyncio.run(backend._decide_permission(_options(), _tool_call("sciqlop_dummy")))
    assert _selected_option_id(resp) == "allow-once"


def test_gated_tool_rejected_in_none_mode():
    backend = _backend([_tool(gated=True)], write_mode="none")
    resp = asyncio.run(backend._decide_permission(_options(), _tool_call("sciqlop_dummy")))
    assert _selected_option_id(resp) == "reject-once"


def test_gated_tool_auto_approved_in_yolo_mode():
    backend = _backend([_tool(gated=True)], write_mode="yolo")
    resp = asyncio.run(backend._decide_permission(_options(), _tool_call("sciqlop_dummy")))
    assert _selected_option_id(resp) == "allow-once"


def test_gated_tool_asks_user_in_confirm_mode():
    seen = {}

    async def confirm(name, args):
        seen.update(name=name, args=args)
        return True

    backend = _backend([_tool(gated=True)], write_mode="confirm", confirm_cb=confirm)
    resp = asyncio.run(backend._decide_permission(
        _options(), _tool_call("mcp__sciqlop__sciqlop_dummy", {"code": "1+1"})))
    assert _selected_option_id(resp) == "allow-once"
    assert seen["name"] == "sciqlop_dummy"
    assert seen["args"] == {"code": "1+1"}


def test_gated_tool_denied_by_user_in_confirm_mode():
    async def confirm(name, args):
        return False

    backend = _backend([_tool(gated=True)], write_mode="confirm", confirm_cb=confirm)
    resp = asyncio.run(backend._decide_permission(_options(), _tool_call("sciqlop_dummy")))
    assert _selected_option_id(resp) == "reject-once"


def test_builtin_tools_are_rejected():
    backend = _backend([_tool()], write_mode="yolo")
    for title in ("Shell", "WriteFile", "StrReplaceFile"):
        resp = asyncio.run(backend._decide_permission(_options(), _tool_call(title)))
        assert _selected_option_id(resp) == "reject-once", title


def test_permission_answer_falls_back_to_cancel_without_options():
    resp = permission_answer([], allow=True)
    assert getattr(resp.outcome, "outcome", None) == "cancelled"


# ------------------------------------------------------------- MCP layer ---

mcp = pytest.importorskip("mcp")

from SciQLop.components.agents.acp.tool_server import SciqlopToolServer


def _server(tools, write_mode="none", confirm_cb=None):
    return SciqlopToolServer(
        tools,
        {t["name"] for t in tools if t.get("gated")},
        write_mode=lambda: write_mode,
        confirm_cb=confirm_cb,
    )


def _texts(content):
    return [getattr(c, "text", "") for c in content]


def test_dispatch_runs_handler_and_wraps_text():
    server = _server([{**_tool(), "handler": lambda args: "plain result"}])
    out = asyncio.run(server._dispatch("sciqlop_dummy", {}))
    assert _texts(out) == ["plain result"]


def test_dispatch_converts_images():
    def handler(args):
        return {"content": [
            {"type": "text", "text": "shot"},
            {"type": "image", "data": "QUJD", "mimeType": "image/png"},
        ]}

    server = _server([{**_tool(), "handler": handler}])
    out = asyncio.run(server._dispatch("sciqlop_dummy", {}))
    assert _texts(out)[0] == "shot"
    images = [c for c in out if getattr(c, "data", None)]
    assert images and images[0].data == "QUJD" and images[0].mimeType == "image/png"


def test_dispatch_blocks_gated_tool_in_none_mode():
    called = []
    tool = {**_tool(gated=True), "handler": lambda args: called.append(args) or "ok"}
    server = _server([tool], write_mode="none")
    out = asyncio.run(server._dispatch("sciqlop_dummy", {}))
    assert "disabled" in _texts(out)[0]
    assert called == []


def test_dispatch_gated_tool_runs_in_yolo_mode():
    tool = {**_tool(gated=True), "handler": lambda args: "ran"}
    server = _server([tool], write_mode="yolo")
    out = asyncio.run(server._dispatch("sciqlop_dummy", {}))
    assert _texts(out) == ["ran"]


def test_dispatch_gated_tool_needs_confirmation_in_confirm_mode():
    async def confirm(name, args):
        return True

    tool = {**_tool(gated=True), "handler": lambda args: "ran"}
    server = _server([tool], write_mode="confirm", confirm_cb=confirm)
    out = asyncio.run(server._dispatch("sciqlop_dummy", {}))
    assert _texts(out) == ["ran"]


def test_dispatch_handler_exception_becomes_error_text():
    def boom(args):
        raise ValueError("bad path")

    server = _server([{**_tool(), "handler": boom}])
    out = asyncio.run(server._dispatch("sciqlop_dummy", {}))
    assert "ValueError" in _texts(out)[0] and "bad path" in _texts(out)[0]
