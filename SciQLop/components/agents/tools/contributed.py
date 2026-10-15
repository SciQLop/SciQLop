"""Agent tools: contributions to the `sciqlop.agent_tools` extension point."""
from __future__ import annotations

import re
from dataclasses import dataclass
from operator import attrgetter
from typing import Any, Callable, Dict, List, Set

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import ExtensionPoint, NotRegistered, declare

log = getLogger(__name__)

_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_WITHDRAWN = "this tool was withdrawn (its plugin was unloaded)"


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    input_schema: dict
    call: Callable[[dict], Any]
    gated: bool = False
    thread: bool = False

    def __post_init__(self):
        if not _NAME.match(self.name):
            raise ValueError(f"agent tool name {self.name!r} must match {_NAME.pattern}")
        if not self.description:
            raise ValueError(f"agent tool {self.name!r} needs a description")


AGENT_TOOLS = declare(ExtensionPoint(
    "sciqlop.agent_tools", AgentTool, what="agent tool", key=attrgetter("name"),
    doc="Tools offered to agent sessions, beyond SciQLop's own."))


def _is_installed(tool: AgentTool) -> bool:
    try:
        return AGENT_TOOLS.get(tool.name) is tool
    except NotRegistered:
        return False


def _guarded(tool: AgentTool) -> Callable[[dict], Any]:
    """Runs in the I/O pool for `thread=True` tools, so it only does plain dict reads on the
    extension point (`get`), never `contribute`/`remove`, which are main-thread only."""
    def _call(payload: dict) -> Any:
        return tool.call(payload) if _is_installed(tool) else _WITHDRAWN
    return _call


def _build(tool: AgentTool) -> Dict[str, Any]:
    from ._builder import _text_tool
    return _text_tool(tool.name, tool.description, tool.input_schema, _guarded(tool),
                      gated=tool.gated, thread=tool.thread)


def contributed_tool_dicts(taken: Set[str]) -> List[Dict[str, Any]]:
    """Tool dicts for every contribution whose name is free; `taken` holds the core names."""
    taken, built = set(taken), []
    for name in AGENT_TOOLS.keys():
        if name in taken:
            owner = AGENT_TOOLS.owner_of(name)
            log.error(f"agent tool {name!r} from {owner} ignored: the name is already taken")
            continue
        taken.add(name)
        built.append(_build(AGENT_TOOLS.get(name)))
    return built
