"""In-process MCP server exposing the SciQLop tools to ACP agents.

The agent runs as a separate process, so tools can't be plain in-process
objects. ACP's session/new accepts HTTP MCP servers, so we serve the SciQLop
tool surface over streamable HTTP on a loopback port, from a uvicorn task
sharing SciQLop's qasync event loop — handlers keep their Qt main-thread
affinity and no subprocess IPC is needed.

Write-gating lives in `_call_tool` and is authoritative: it holds even if the
agent never asks ACP permission for MCP tools.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

import mcp.types as mt
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager


class SciqlopToolServer:
    """The SciQLop tool surface as a loopback streamable-HTTP MCP server."""

    def __init__(
        self,
        tools: List[Dict[str, Any]],
        gated_names: set,
        is_write_allowed: Callable[[], bool],
        confirm_cb,
        server_name: str = "sciqlop",
    ):
        self._tools = tools
        self._handlers = {t["name"]: t["handler"] for t in tools}
        self._gated_names = gated_names
        self._is_write_allowed = is_write_allowed
        self._confirm_cb = confirm_cb
        self.url: Optional[str] = None
        self._manager: Optional[StreamableHTTPSessionManager] = None
        self._manager_cm = None
        self._uvicorn = None
        self._uvicorn_task: Optional[asyncio.Task] = None

        self._server: Server = Server(server_name)

        @self._server.list_tools()
        async def _list_tools():
            return [
                mt.Tool(
                    name=t["name"],
                    description=t["description"],
                    inputSchema=t["input_schema"],
                )
                for t in self._tools
            ]

        @self._server.call_tool()
        async def _call_tool(name: str, arguments: dict):
            return await self._dispatch(name, arguments or {})

    async def _dispatch(self, name: str, args: dict) -> list:
        if name in self._gated_names:
            if not self._is_write_allowed():
                return [_text(
                    "write actions are disabled — toggle 'Allow write actions' "
                    "in the SciQLop chat dock"
                )]
            if self._confirm_cb is not None:
                try:
                    allowed = await self._confirm_cb(name, args)
                except Exception as e:
                    return [_text(f"approval callback failed: {e}")]
                if not allowed:
                    return [_text("user denied the tool call")]
        handler = self._handlers.get(name)
        if handler is None:
            return [_text(f"unknown tool: {name}")]
        try:
            result = handler(args)
            if asyncio.iscoroutine(result):
                result = await result
        except Exception as e:
            return [_text(f"{type(e).__name__}: {e}")]
        return _to_content(result)

    async def start(self) -> str:
        """Serve on a random loopback port; returns the MCP endpoint URL."""
        import logging
        import uvicorn

        self._manager = StreamableHTTPSessionManager(
            app=self._server, json_response=True, stateless=True,
        )
        self._manager_cm = self._manager.run()
        await self._manager_cm.__aenter__()

        manager = self._manager

        async def _asgi(scope, receive, send):
            if scope["type"] == "http":
                await manager.handle_request(scope, receive, send)
            # lifespan is disabled in the uvicorn config; nothing else to do

        config = uvicorn.Config(
            _asgi, host="127.0.0.1", port=0, log_level="error", lifespan="off",
            log_config=None,  # don't let uvicorn reconfigure/reset logging
        )
        self._uvicorn = uvicorn.Server(config)
        self._uvicorn_task = asyncio.create_task(self._uvicorn.serve())
        for _ in range(100):
            if self._uvicorn.started:
                break
            await asyncio.sleep(0.05)
        # The stateless session manager logs a spurious ClosedResourceError
        # traceback from its message router whenever a request stream closes —
        # expected noise in this embedding, not a failure. Set after startup
        # because uvicorn's own logging setup would reset it otherwise.
        logging.getLogger("mcp.server.streamable_http").setLevel(logging.CRITICAL + 1)
        if not self._uvicorn.started:
            raise RuntimeError("MCP HTTP server failed to start")
        port = self._uvicorn.servers[0].sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}/mcp"
        return self.url

    async def stop(self) -> None:
        if self._uvicorn is not None:
            self._uvicorn.should_exit = True
        if self._uvicorn_task is not None:
            try:
                await asyncio.wait_for(self._uvicorn_task, timeout=5)
            except Exception:
                self._uvicorn_task.cancel()
        if self._manager_cm is not None:
            try:
                await self._manager_cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._uvicorn = None
        self._uvicorn_task = None
        self._manager_cm = None
        self._manager = None


def _text(text: str) -> mt.TextContent:
    return mt.TextContent(type="text", text=text)


def _to_content(result: Any) -> list:
    """Convert a SciQLop tool result into MCP content blocks.

    Handlers return MCP-style dicts: {"content": [{"type": "text", ...},
    {"type": "image", "data": <b64>, "mimeType": ...}]}. Images become
    ImageContent so the model actually sees the screenshots.
    """
    if isinstance(result, dict) and "content" in result:
        parts: list = []
        for item in result["content"]:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                parts.append(_text(item.get("text", "")))
            elif item.get("type") == "image":
                data = item.get("data")
                if data:
                    parts.append(mt.ImageContent(
                        type="image",
                        data=data,
                        mimeType=item.get("mimeType", "image/png"),
                    ))
        if parts:
            return parts
        return [_text("OK")]
    return [_text(result if isinstance(result, str) else str(result))]
