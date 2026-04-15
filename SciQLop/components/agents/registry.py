"""Agent backend registry."""
from __future__ import annotations

from typing import Callable, Dict, List, Type, Union

from .backend import AgentBackend, BackendContext

BackendFactory = Callable[[BackendContext], AgentBackend]

_BACKENDS: Dict[str, BackendFactory] = {}


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
        _BACKENDS[name] = factory_or_name
    else:
        _BACKENDS[str(factory_or_name)] = factory


def unregister_agent_backend(name: str) -> None:
    _BACKENDS.pop(name, None)


def available_backends() -> List[str]:
    return sorted(_BACKENDS.keys())


def create_backend(name: str, ctx: BackendContext) -> AgentBackend:
    factory = _BACKENDS.get(name)
    if factory is None:
        raise KeyError(f"no agent backend registered: {name!r}")
    return factory(ctx)
