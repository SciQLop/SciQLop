"""Agent backends: contributions to the `sciqlop.agent_backends` extension point."""
from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter
from typing import Callable, List, Type, Union

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import ExtensionPoint, NotRegistered, contribute_taking_over, current_owner, declare
from SciQLop.user_api.threading import on_main_thread

from .backend import AgentBackend, BackendContext

log = getLogger(__name__)

BackendFactory = Callable[[BackendContext], AgentBackend]


@dataclass(frozen=True)
class AgentBackendEntry:
    name: str
    factory: BackendFactory

    def __post_init__(self):
        if not self.name:
            raise ValueError("an agent backend needs a non-empty name")


AGENT_BACKENDS = declare(ExtensionPoint(
    "sciqlop.agent_backends", AgentBackendEntry, what="agent backend", key=attrgetter("name"),
    doc="Agent chat backends by display name."))


def register_agent_backend(
    factory_or_name: Union[BackendFactory, Type[AgentBackend], str],
    factory: BackendFactory = None,
) -> None:
    """Register a backend. Preferred form: `register_agent_backend(ClaudeBackend)`
    — the name is read from `factory.display_name`. Legacy two-arg form is
    kept for callers that want an explicit name."""
    if factory is None:
        name = getattr(factory_or_name, "display_name", None)
        if not isinstance(name, str):
            raise TypeError(
                "register_agent_backend(factory) requires factory.display_name"
            )
        entry = AgentBackendEntry(name, factory_or_name)
    else:
        entry = AgentBackendEntry(str(factory_or_name), factory)
    _contribute_backend(entry, current_owner())


@on_main_thread
def _contribute_backend(entry: AgentBackendEntry, owner: str) -> None:
    contribute_taking_over(AGENT_BACKENDS, entry, log, owner=owner)


@on_main_thread
def unregister_agent_backend(name: str) -> None:
    if name in AGENT_BACKENDS:
        AGENT_BACKENDS.remove(name)


def available_backends() -> List[str]:
    return sorted(AGENT_BACKENDS.keys())


def create_backend(name: str, ctx: BackendContext) -> AgentBackend:
    try:
        entry = AGENT_BACKENDS.get(name)
    except NotRegistered:
        raise KeyError(f"no agent backend registered: {name!r}") from None
    return entry.factory(ctx)
