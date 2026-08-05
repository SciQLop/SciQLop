"""Shared ACP (Agent Client Protocol) layer for agent backends.

Any agent CLI that speaks ACP over stdio (`kimi acp`, `opencode acp`, …) can
be driven through this package: connection lifecycle, an in-process MCP
streamable-HTTP server exposing the SciQLop tools, session/update →
StreamBlock translation, permission gating and session listing/replay.

A backend plugin subclasses `AcpAgentBackend` and supplies only what is
genuinely agent-specific: the command line, display name, model discovery
and any stream/session quirks the capability handshake cannot paper over.

Dependencies (`agent-client-protocol`, `mcp`, `uvicorn`) are optional for
SciQLop itself: they are declared by the plugins that use this layer, and
import failure is reported through `acp_available()` instead of breaking
`import SciQLop`.
"""
from .backend import AcpAgentBackend, acp_available
from .sessions import current_workspace_dir

__all__ = [
    "AcpAgentBackend",
    "acp_available",
    "current_workspace_dir",
]
