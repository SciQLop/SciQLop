"""What a plugin's activate(ctx) receives, and the state of every plugin SciQLop tried (spec §3.3)."""
from dataclasses import dataclass
from operator import attrgetter

from packaging.utils import canonicalize_name

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

    def _declared_id(self, name: str) -> str:
        wanted = canonicalize_name(name)
        return next((d for d in self._declared if canonicalize_name(d) == wanted), name)

    def plugin(self, name: str):
        plugin_id = self._declared_id(name)
        if plugin_id not in self._declared:
            raise UndeclaredDependency(f"{self.name} uses plugin {name!r} without declaring it in plugin.json "
                                       f"dependencies or optional_dependencies")
        if STATES.get(plugin_id) is None or STATES[plugin_id].status != "active":
            raise PluginUnavailable(f"{self.name} needs plugin {name!r}, which is {_describe(plugin_id)}")
        return STATES[plugin_id].api

    def has(self, name: str) -> bool:
        plugin_id = self._declared_id(name)
        return plugin_id in self._declared and STATES.get(plugin_id) is not None \
            and STATES[plugin_id].status == "active"
