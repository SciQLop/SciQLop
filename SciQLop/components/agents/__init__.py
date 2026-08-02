"""Agent-agnostic primitives for LLM chat docks embedded in SciQLop."""
from .backend import (
    AgentBackend,
    BackendContext,
    CarbonFootprint,
    ConfirmCallback,
    ContextCategory,
    Cost,
    Quota,
    SessionEntry,
    StreamBlock,
    TokenCounts,
    UsageReportingBackend,
    UsageSnapshot,
)
from .chat_dock import AgentChatDock, ensure_agent_dock
from .registry import (
    available_backends,
    create_backend,
    register_agent_backend,
    unregister_agent_backend,
)

__all__ = [
    "AgentBackend",
    "AgentChatDock",
    "BackendContext",
    "CarbonFootprint",
    "ConfirmCallback",
    "ContextCategory",
    "Cost",
    "Quota",
    "SessionEntry",
    "StreamBlock",
    "TokenCounts",
    "UsageReportingBackend",
    "UsageSnapshot",
    "available_backends",
    "create_backend",
    "ensure_agent_dock",
    "register_agent_backend",
    "unregister_agent_backend",
]
