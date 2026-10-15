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
    AGENT_BACKENDS,
    AgentBackendEntry,
    available_backends,
    create_backend,
    register_agent_backend,
    unregister_agent_backend,
)
from .skills import AGENT_SKILLS, AgentSkill
from .tools import AGENT_TOOLS, AgentTool

__all__ = [
    "AGENT_BACKENDS",
    "AGENT_SKILLS",
    "AgentSkill",
    "AGENT_TOOLS",
    "AgentBackend",
    "AgentBackendEntry",
    "AgentChatDock",
    "AgentTool",
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
