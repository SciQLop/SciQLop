"""Guard the `mcp` version floor against the claude-agent-sdk return shape.

`claude_agent_sdk.create_sdk_mcp_server` registers a `@server.call_tool()`
handler that returns a fully-formed `mcp.types.CallToolResult`. mcp < 1.19.0
has no branch for that shape: `CallToolResult` is a pydantic model, so it
satisfies `hasattr(results, "__iter__")` and the low-level server does
`content=list(results)` — which yields the model's `(field, value)` tuples.
Every tool result then fails client-side validation with
"Input should be a valid dictionary or instance of TextContent
 [input_value=('meta', None)]", i.e. the whole SciQLop tool surface is dead.

mcp >= 1.19.0 returns such a result untouched. This test fails on 1.16.x.
"""
import asyncio

import mcp.types as mt
from mcp.server.lowlevel import Server


def _dispatch(server: Server, name: str) -> mt.CallToolResult:
    handler = server.request_handlers[mt.CallToolRequest]
    request = mt.CallToolRequest(
        method="tools/call",
        params=mt.CallToolRequestParams(name=name, arguments={}),
    )
    return asyncio.run(handler(request)).root


def test_handler_returning_calltoolresult_is_passed_through():
    server = Server("test")

    @server.list_tools()
    async def _list_tools():
        return [mt.Tool(name="probe", description="", inputSchema={"type": "object"})]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        return mt.CallToolResult(
            content=[mt.TextContent(type="text", text="hello")],
            isError=False,
        )

    result = _dispatch(server, "probe")

    assert result.isError is False
    assert result.content == [mt.TextContent(type="text", text="hello")]
