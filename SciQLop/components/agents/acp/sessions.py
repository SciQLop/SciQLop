"""Session listing and transcript replay for ACP agents.

Both operations are async and need a live agent process, while the
`AgentBackend` protocol is sync and called on the GUI thread — so each spawns
a short-lived agent in a worker thread with its own event loop.

Replay translation turns the session/load update stream back into
ChatMessages: user/agent chunks open or extend the message of their role,
tool calls attach to the current assistant message.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from ..backend import SessionEntry
from ..chat import (
    ChatMessage,
    ImageBlock,
    TextBlock,
    ThinkingBlock,
    ToolActivityBlock,
    write_b64_image,
)
from ..workspace import current_workspace_dir
from .stream import raw_input_dict, tool_output

__all__ = [
    "acp_config_options",
    "acp_list_sessions",
    "acp_load_session_messages",
    "async_acp_load_session_messages",
    "current_workspace_dir",
    "replay_to_messages",
]


def _run_async(coro_factory, timeout: float = 20.0):
    """Run a coroutine from sync code while qasync's loop is already running."""
    def _blocking():
        return asyncio.run(asyncio.wait_for(coro_factory(), timeout=timeout))

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_blocking).result(timeout=timeout + 2.0)


async def _spawn_agent(command: List[str]):
    """A fresh agent process with an initialized ACP connection."""
    import acp
    from acp.schema import (
        ClientCapabilities,
        FileSystemCapabilities,
        Implementation,
    )

    proc = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    class _Client:
        async def session_update(self, session_id, update, **kwargs):
            pass

        def on_connect(self, conn):
            pass

    conn = acp.connect_to_agent(_Client(), proc.stdin, proc.stdout)
    await conn.initialize(
        protocol_version=acp.PROTOCOL_VERSION,
        client_capabilities=ClientCapabilities(
            fs=FileSystemCapabilities(read_text_file=False, write_text_file=False),
            terminal=False,
        ),
        client_info=Implementation(name="sciqlop", title="SciQLop", version="1.0"),
    )
    return proc, conn


async def _kill(proc, conn) -> None:
    try:
        await conn.close()
    except Exception:
        pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(proc.wait(), timeout=5)
    except Exception:
        pass


def _parse_mtime(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return 0.0


def acp_list_sessions(command: List[str], cwd: Optional[Path] = None) -> List[SessionEntry]:
    """All sessions the agent reports for `cwd` (paginates to completion)."""
    work_dir = str(cwd or current_workspace_dir())

    async def _list():
        proc, conn = await _spawn_agent(command)
        try:
            entries = []
            cursor = None
            while True:
                resp = await conn.list_sessions(cwd=work_dir, cursor=cursor)
                for s in resp.sessions:
                    entries.append(SessionEntry(
                        id=s.session_id,
                        label=s.title or s.session_id,
                        mtime=_parse_mtime(s.updated_at),
                    ))
                if not resp.next_cursor:
                    return entries
                cursor = resp.next_cursor
        finally:
            await _kill(proc, conn)

    try:
        return _run_async(_list)
    except Exception:
        return []


def acp_config_options(
    command: List[str], cwd: Optional[Path] = None
) -> dict[str, list[tuple[str, str]]]:
    """`{config_id: [(label, value), …]}` for the agent's session config options.

    ACP only reports these on a live session, but the model dropdown is built at
    plugin load — so this opens a throwaway session purely to read them. Costs
    one short-lived agent process; the payoff is a model list that inherits the
    agent's own provider filtering instead of a plugin re-deriving it from
    config files that drift.
    """
    work_dir = str(cwd or current_workspace_dir())

    async def _read():
        proc, conn = await _spawn_agent(command)
        try:
            resp = await conn.new_session(cwd=work_dir, mcp_servers=[])
            options: dict[str, list[tuple[str, str]]] = {}
            for opt in getattr(resp, "config_options", None) or []:
                choices = [
                    (str(getattr(o, "name", "") or getattr(o, "value", "")),
                     str(getattr(o, "value", "")))
                    for o in getattr(opt, "options", None) or []
                ]
                if choices:
                    options[str(getattr(opt, "id", ""))] = choices
            return options
        finally:
            await _kill(proc, conn)

    try:
        return _run_async(_read, timeout=30.0)
    except Exception:
        return {}


async def async_acp_load_session_messages(
    command: List[str],
    session_id: str,
    image_tempdir: Path,
    cwd: Optional[Path] = None,
) -> List[ChatMessage]:
    """Replay a session's history into ChatMessages via session/load.

    This is the coroutine variant; it must run on the qasync event loop so the
    GUI stays responsive while the short-lived replay agent starts up.
    """
    import acp
    from acp.schema import (
        ClientCapabilities,
        FileSystemCapabilities,
        Implementation,
    )

    collected: list = []

    proc = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    class _Client:
        async def session_update(self, session_id, update, **kwargs):
            collected.append(update)

        def on_connect(self, conn):
            pass

    conn = acp.connect_to_agent(_Client(), proc.stdin, proc.stdout)
    try:
        await conn.initialize(
            protocol_version=acp.PROTOCOL_VERSION,
            client_capabilities=ClientCapabilities(
                fs=FileSystemCapabilities(read_text_file=False, write_text_file=False),
                terminal=False,
            ),
            client_info=Implementation(name="sciqlop", title="SciQLop", version="1.0"),
        )
        await conn.load_session(
            cwd=str(cwd or current_workspace_dir()),
            session_id=session_id,
            mcp_servers=[],
        )
    finally:
        await _kill(proc, conn)

    return replay_to_messages(collected, Path(image_tempdir))


def acp_load_session_messages(
    command: List[str],
    session_id: str,
    image_tempdir: Path,
    cwd: Optional[Path] = None,
) -> List[ChatMessage]:
    """Replay a session's history into ChatMessages via session/load."""
    try:
        return _run_async(
            lambda: async_acp_load_session_messages(
                command, session_id, image_tempdir, cwd
            )
        )
    except Exception:
        return []


def replay_to_messages(updates: list, image_tempdir: Path) -> List[ChatMessage]:
    """Turn a session/load update stream into ChatMessages."""
    from acp.schema import (
        AgentMessageChunk,
        AgentThoughtChunk,
        ToolCallProgress,
        ToolCallStart,
        UserMessageChunk,
    )

    messages: List[ChatMessage] = []
    current: Optional[ChatMessage] = None

    def open_message(role: str) -> ChatMessage:
        nonlocal current
        if current is None or current.role != role:
            current = ChatMessage(role=role, blocks=[], done=True)
            messages.append(current)
        return current

    def assistant() -> ChatMessage:
        return open_message("assistant")

    def append_text(cls, text: str) -> None:
        msg = assistant()
        last = msg.blocks[-1] if msg.blocks else None
        if type(last) is cls:
            last.text += text
        else:
            msg.blocks.append(cls(text=text, complete=True))

    for update in updates:
        if isinstance(update, UserMessageChunk):
            text = getattr(update.content, "text", "")
            if not text:
                continue
            msg = open_message("user")
            last = msg.blocks[-1] if msg.blocks else None
            if isinstance(last, TextBlock):
                last.text += text
            else:
                msg.blocks.append(TextBlock(text=text, complete=True))
        elif isinstance(update, AgentMessageChunk):
            text = getattr(update.content, "text", "")
            if text:
                append_text(TextBlock, text)
        elif isinstance(update, AgentThoughtChunk):
            text = getattr(update.content, "text", "")
            if text:
                append_text(ThinkingBlock, text)
        elif isinstance(update, ToolCallStart):
            assistant().blocks.append(ToolActivityBlock(
                tool_name=str(update.title or "").split("__")[-1],
                tool_input=raw_input_dict(update.raw_input),
                tool_use_id=update.tool_call_id or "",
            ))
        elif isinstance(update, ToolCallProgress):
            text, images = tool_output(update)
            for msg in reversed(messages):
                match = next(
                    (b for b in msg.blocks
                     if isinstance(b, ToolActivityBlock)
                     and b.tool_use_id == (update.tool_call_id or "")),
                    None,
                )
                if match is not None:
                    if text:
                        match.result = text
                    break
            for data, mime in images:
                path = write_b64_image(data, mime, image_tempdir, prefix="replay")
                if path:
                    assistant().blocks.append(ImageBlock(path=path))
    return [m for m in messages if m.blocks]
