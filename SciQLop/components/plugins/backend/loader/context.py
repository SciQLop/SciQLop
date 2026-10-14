"""What a plugin's activate(ctx) receives, and the state of every plugin SciQLop tried (spec §3.3)."""
from dataclasses import dataclass
from operator import attrgetter

from SciQLop.core import extensions


class UndeclaredDependency(LookupError):
    pass


class PluginUnavailable(LookupError):
    pass


@dataclass
class PluginState:
    status: str              # "active", "failed" or "refused"
    version: str
    reason: str = ""
    api: object = None
    module: object = None
    context: object = None


STATES: dict[str, PluginState] = {}


def active_versions() -> dict[str, str]:
    return {name: s.version for name, s in STATES.items() if s.status == "active"}


def _describe(name: str) -> str:
    state = STATES.get(name)
    if state is None:
        return "not loaded"
    return f"{state.status}: {state.reason}" if state.reason else state.status


class PluginContext:
    def __init__(self, name: str, version: str, main_window, declared: frozenset[str]):
        self.name, self.version, self.main_window = name, version, main_window
        self._declared = declared

    def extension_point(self, id: str, contribution_type: type, doc: str = "", key=attrgetter("id")):
        if not id.startswith(f"{self.name}."):
            raise ValueError(f"extension point {id!r} of plugin {self.name} must start with {self.name + '.'!r}")
        return extensions.declare(extensions.ExtensionPoint(id, contribution_type, key=key, doc=doc,
                                                            owner=self.name))

    def contribute(self, ep_id: str, item, replace: bool = False):
        return extensions.get(ep_id).contribute(item, owner=self.name, replace=replace)

    def plugin(self, name: str):
        if name not in self._declared:
            raise UndeclaredDependency(f"{self.name} uses plugin {name!r} without declaring it in plugin.json "
                                       f"dependencies or optional_dependencies")
        if STATES.get(name) is None or STATES[name].status != "active":
            raise PluginUnavailable(f"{self.name} needs plugin {name!r}, which is {_describe(name)}")
        return STATES[name].api

    def has(self, name: str) -> bool:
        return name in self._declared and STATES.get(name) is not None and STATES[name].status == "active"
