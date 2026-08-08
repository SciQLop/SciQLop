"""`AcpAgentBackend` — the AgentBackend protocol for ACP-speaking agent CLIs.

A plugin subclasses this and supplies the agent-specific bits:

- `acp_command()` — how to spawn the agent's ACP server (e.g. ["kimi", "acp"]);
- `cli_label` — display name used in error messages;
- model discovery (`model_choices`) — ACP's config-options cover model
  *selection* (config_id "model"), not enumeration, which differs per agent.

Everything else is shared: subprocess lifecycle, initialize handshake,
in-process MCP tool server, prompt streaming (turn correlation is JSON-RPC
request/response — no per-turn stream sniffing), permission gating, slash
commands, session list/resume/replay.

One known ACP limitation: the protocol has no system-prompt channel, so the
agent runs with its own persona. SciQLop's tool descriptions carry the
operational guidance instead.
"""
from __future__ import annotations

import asyncio
import base64
import shutil
from pathlib import Path
from typing import AsyncIterator, List, Optional

from ..backend import BackendContext, SessionEntry, StreamBlock
from ..chat import ChatMessage
from . import sessions as _acp_sessions
from .client import AcpClientHandler, permission_answer
from .stream import AcpStreamTranslator, raw_input_dict
from .tool_server import SciqlopToolServer

try:
    import acp
    from acp import helpers as acp_helpers
    from acp.schema import (
        AvailableCommandsUpdate,
        ClientCapabilities,
        FileSystemCapabilities,
        HttpMcpServer,
        Implementation,
    )

    _ACP_AVAILABLE = True
    _ACP_IMPORT_ERROR: Optional[str] = None
except Exception as e:  # pragma: no cover
    _ACP_AVAILABLE = False
    _ACP_IMPORT_ERROR = str(e)


def acp_available() -> tuple[bool, Optional[str]]:
    return _ACP_AVAILABLE, _ACP_IMPORT_ERROR


class AcpAgentBackend:
    """Base class for ACP backends. Subclasses MUST set `display_name`,
    `model_choices` and `supports_sessions` per the AgentBackend protocol,
    and implement `acp_command()`."""

    cli_label: str = "agent"

    def __init__(self, ctx: BackendContext):
        if not _ACP_AVAILABLE:
            raise RuntimeError(
                f"agent-client-protocol not importable: {_ACP_IMPORT_ERROR}")
        self.check_prerequisites()
        self._main_window = ctx.main_window
        self._tools = list(ctx.tools)
        self._tool_names = {t["name"] for t in ctx.tools}
        self._gated_names = {t["name"] for t in ctx.tools if t.get("gated")}
        self._tempdir = Path(ctx.tempdir)
        self._tempdir.mkdir(parents=True, exist_ok=True)
        self._confirm_cb = ctx.confirm_cb
        self._allow_writes = ctx.allow_writes
        self._model: Optional[str] = None
        self._resume: Optional[str] = None
        self._lock = asyncio.Lock()
        self._mcp = SciqlopToolServer(
            self._tools, self._gated_names,
            is_write_allowed=lambda: self._allow_writes,
            confirm_cb=self._confirm_cb,
        )
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._conn = None
        self._session_id: Optional[str] = None
        self._updates: Optional[asyncio.Queue] = None
        self._slash_commands: List[str] = []

    # -------------------------------------------------------- subclass hooks

    def acp_command(self) -> List[str]:
        """The argv that starts the agent's ACP server on stdio."""
        raise NotImplementedError

    def check_prerequisites(self) -> None:
        """Fail fast with an actionable message when the agent is missing."""
        if shutil.which(self.acp_command()[0]) is None:
            raise RuntimeError(
                f"{self.acp_command()[0]} CLI not found on PATH — install "
                f"{self.cli_label} first."
            )

    # ------------------------------------------------------------------ ACP

    async def _ensure_connection(self):
        if self._conn is not None:
            return
        mcp_url = await self._mcp.start()
        self._mcp_servers = [HttpMcpServer(
            name="sciqlop", url=mcp_url, type="http", headers=[],
        )]
        self._proc = await asyncio.create_subprocess_exec(
            *self.acp_command(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._conn = acp.connect_to_agent(
            AcpClientHandler(self), self._proc.stdin, self._proc.stdout,
        )
        await self._conn.initialize(
            protocol_version=acp.PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities(
                fs=FileSystemCapabilities(read_text_file=False, write_text_file=False),
                terminal=False,
            ),
            client_info=Implementation(name="sciqlop", title="SciQLop", version="1.0"),
        )

    async def _apply_model(self) -> None:
        if (self._model and self._conn is not None
                and self._session_id is not None):
            await self._conn.set_config_option(
                session_id=self._session_id, config_id="model", value=self._model,
            )

    async def _ensure_session(self):
        if self._session_id is not None:
            return
        await self._ensure_connection()
        if self._resume:
            await self._conn.resume_session(
                cwd=str(_acp_sessions.current_workspace_dir()),
                session_id=self._resume,
                mcp_servers=self._mcp_servers,
            )
            self._session_id = self._resume
            self._resume = None
        else:
            resp = await self._conn.new_session(
                cwd=str(_acp_sessions.current_workspace_dir()),
                mcp_servers=self._mcp_servers,
            )
            self._session_id = resp.session_id
        await self._apply_model()

    def _on_update(self, update) -> None:
        if isinstance(update, AvailableCommandsUpdate):
            self._slash_commands = [
                "/" + c.name.lstrip("/") for c in update.available_commands
            ]
            return
        queue = self._updates
        if queue is not None:
            queue.put_nowait(update)

    async def _decide_permission(self, options, tool_call):
        """Answer the agent's permission prompts (see client.py for the policy)."""
        short = str(getattr(tool_call, "title", "") or "").split("__")[-1]
        if short in self._tool_names:
            if short not in self._gated_names:
                return permission_answer(options, allow=True)
            if not self._allow_writes or self._confirm_cb is None:
                return permission_answer(options, allow=False)
            try:
                allowed = await self._confirm_cb(
                    short, raw_input_dict(getattr(tool_call, "raw_input", None)))
            except Exception:
                allowed = False
            return permission_answer(options, allow=allowed)
        return permission_answer(options, allow=False)

    # ------------------------------------------------------------- protocol

    async def ask(
        self, prompt: str, image_paths: Optional[List[str]] = None
    ) -> AsyncIterator[StreamBlock]:
        async with self._lock:
            await self._ensure_session()
            queue: asyncio.Queue = asyncio.Queue()
            self._updates = queue
            blocks = [acp_helpers.text_block(prompt or "")]
            for path in image_paths or []:
                try:
                    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
                except OSError:
                    continue
                blocks.append(acp_helpers.image_block(data, _mime_for(path)))
            prompt_task = asyncio.create_task(self._conn.prompt(
                session_id=self._session_id, prompt=blocks,
            ))
            prompt_task.add_done_callback(lambda _t: queue.put_nowait(None))
            stream = AcpStreamTranslator(self._tempdir)
            try:
                while True:
                    update = await queue.get()
                    if update is None:  # prompt response arrived; turn is over
                        break
                    for block in stream.feed(update):
                        if block is not None:
                            yield block
                for block in stream.flush():
                    if block is not None:
                        yield block
                # propagate a protocol-level failure as an exception the dock
                # renders as an error message
                await prompt_task
            finally:
                self._updates = None

    async def reset(self) -> None:
        async with self._lock:
            if self._conn is not None:
                resp = await self._conn.new_session(
                    cwd=str(_acp_sessions.current_workspace_dir()),
                    mcp_servers=self._mcp_servers,
                )
                self._session_id = resp.session_id
            self._resume = None

    async def cancel(self) -> None:
        # session/cancel is a notification; the in-flight prompt request then
        # resolves with stopReason 'cancelled', ending ask()'s stream.
        conn = self._conn
        if conn is not None and self._session_id is not None:
            await conn.cancel(session_id=self._session_id)

    async def resume(self, session_id: str) -> None:
        async with self._lock:
            self._session_id = None
            self._resume = session_id

    async def set_model(self, model: Optional[str]) -> None:
        async with self._lock:
            self._model = model
            await self._apply_model()

    def set_allow_writes(self, allow: bool) -> None:
        self._allow_writes = allow

    async def list_slash_commands(self) -> List[str]:
        return list(self._slash_commands)

    def list_sessions(self) -> List[SessionEntry]:
        return _acp_sessions.acp_list_sessions(self.acp_command())

    async def async_load_session(self, session_id: str, image_tempdir: Path) -> List[ChatMessage]:
        """Non-blocking replay of a saved session; preferred by the chat dock."""
        return await _acp_sessions.async_acp_load_session_messages(
            self.acp_command(), session_id, image_tempdir,
        )

    def load_session(self, session_id: str, image_tempdir: Path) -> List[ChatMessage]:
        """Synchronous fallback for callers that are not on the async event loop."""
        return _acp_sessions.acp_load_session_messages(
            self.acp_command(), session_id, image_tempdir,
        )

    def current_session_id(self) -> Optional[str]:
        return self._session_id

    # -------------------------------------------------------------- teardown

    async def _disconnect(self) -> None:
        if self._conn is not None:
            try:
                await self._conn.close()
            except Exception:
                pass
            self._conn = None
        self._session_id = None
        if self._proc is not None:
            try:
                self._proc.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except Exception:
                pass
            self._proc = None
        await self._mcp.stop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self._disconnect()


def _mime_for(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
