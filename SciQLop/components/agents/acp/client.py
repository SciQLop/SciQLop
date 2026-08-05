"""The client face an ACP agent talks to, and the permission policy.

The policy is fixed by the SciQLop embedding, not per agent: SciQLop's own
MCP tools auto-approve unless gated; gated ones go through the dock's
confirm dialog when writes are enabled; the agent's built-in tools (shell,
file edits, …) are always rejected — the embedded chat acts on SciQLop,
never on the user's filesystem. The same gate also runs inside the MCP tool
dispatch (see tool_server.py), which is authoritative.
"""
from __future__ import annotations

from typing import Any, List

try:
    import acp
    from acp.schema import AllowedOutcome, DeniedOutcome, RequestPermissionResponse
    _ACP_AVAILABLE = True
except Exception:  # pragma: no cover
    _ACP_AVAILABLE = False


def permission_answer(options, allow: bool) -> "RequestPermissionResponse":
    """Pick the best-matching option id (once over always) for an allow/deny."""
    wanted = ("allow_once", "allow_always") if allow else ("reject_once", "reject_always")
    ids = {getattr(o, "kind", None): getattr(o, "option_id", None) for o in options or []}
    for kind in wanted:
        if ids.get(kind):
            return RequestPermissionResponse(
                outcome=AllowedOutcome(outcome="selected", option_id=ids[kind]))
    if ids:
        return RequestPermissionResponse(
            outcome=AllowedOutcome(
                outcome="selected", option_id=next(iter(ids.values()))))
    # No options to pick from: cancel the request (agent treats it as denied).
    return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))


class AcpClientHandler:
    """Duck-types acp.Client. Only session_update and request_permission are
    meaningful here: backends advertise no fs/terminal capabilities, so the
    agent has no reason to call those — the stubs below exist purely to
    answer cleanly if it ever does."""

    def __init__(self, backend):
        self._backend = backend

    async def session_update(self, session_id: str, update, **kwargs) -> None:
        self._backend._on_update(update)

    async def request_permission(self, options, session_id: str, tool_call, **kwargs):
        return await self._backend._decide_permission(options, tool_call)

    def on_connect(self, conn) -> None:
        pass

    async def read_text_file(self, **kwargs):
        raise acp.RequestError.method_not_found("fs/read_text_file")

    async def write_text_file(self, **kwargs):
        raise acp.RequestError.method_not_found("fs/write_text_file")

    async def create_terminal(self, **kwargs):
        raise acp.RequestError.method_not_found("terminal/create")

    async def terminal_output(self, **kwargs):
        raise acp.RequestError.method_not_found("terminal/output")

    async def release_terminal(self, **kwargs):
        raise acp.RequestError.method_not_found("terminal/release")

    async def wait_for_terminal_exit(self, **kwargs):
        raise acp.RequestError.method_not_found("terminal/wait_for_exit")

    async def kill_terminal(self, **kwargs):
        raise acp.RequestError.method_not_found("terminal/kill")
