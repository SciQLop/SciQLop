import importlib
import importlib.metadata
import os
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional
from types import SimpleNamespace
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import owned_by
from .context import STATES, PluginContext, PluginState, active_versions

# Re-exported: plugins_folders lives in a Qt-free module so the launcher can
# reach it without importing this one, which pulls in the GUI stack.
from ..folders import plugins_folders  # noqa: F401

if TYPE_CHECKING:
    from ..settings import SciQLopPluginsSettings  # noqa: F401  forward-ref target

loaded_plugins = SimpleNamespace()

log = getLogger(__name__)


class _KernelPluginsView:
    """`plugins` in the kernel namespace: the loaded plugins, read live.

    Cells run on the kernel thread, so plugin objects are handed out proxied
    there. The namespace itself stays a plain object so `dir()` and tab
    completion keep listing the plugin names.
    """

    def __getattr__(self, name):
        from SciQLop.user_api.threading import main_thread_safe
        return main_thread_safe(getattr(loaded_plugins, name))

    def __dir__(self):
        return sorted(vars(loaded_plugins))


def kernel_plugins_view() -> _KernelPluginsView:
    return _KernelPluginsView()


def import_from_path(module_name, file_path):
    import sys
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _bundled_plugins_dir() -> str:
    from SciQLop import plugins
    return os.path.dirname(os.path.realpath(plugins.__file__))


def load_module(path, name):
    try:
        if os.path.realpath(path) == _bundled_plugins_dir():
            # Bundled plugins must live under ONE module identity. Spec-loading
            # them as top-level `<name>` creates a second module object when
            # anything later imports `SciQLop.plugins.<name>` (tests, notebooks)
            # — re-running ConfigEntry registrations (duplicate-entry error)
            # and breaking isinstance across the duplicated class sets.
            return importlib.import_module(f"SciQLop.plugins.{name}")
        return import_from_path(name, os.path.join(path, name, "__init__.py"))
    except Exception as e:
        log.error(f"Oups can't load {name} , {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return None


def load_plugin(path, name, main_window):
    return load_one(path, name, main_window)


def list_plugins_as_modules(plugin_path):
    if not os.path.isdir(plugin_path):
        return []
    return [f[:-3] for f in os.listdir(plugin_path) if f[-3:] == '.py' and f != '__init__.py']


def list_plugins_as_packages(plugin_path):
    if not os.path.isdir(plugin_path):
        return []
    return [f for f in os.listdir(plugin_path) if os.path.isdir(f"{plugin_path}/{f}") and not f.startswith(('_', '.'))]


def list_plugins(plugin_path):
    return list_plugins_as_modules(plugin_path) + list_plugins_as_packages(plugin_path)


ENTRY_POINT_GROUP = "sciqlop.plugins"


def _discover_entry_point_plugins() -> dict[str, importlib.metadata.EntryPoint]:
    return {ep.name: ep for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)}


def plugin_host_compatible(folder: str, plugin: str) -> bool:
    """Backstop gate: refuse to load a folder plugin whose declared SciQLop
    requirement the running host doesn't satisfy.

    The app store already gates install/update, but a plugin can be sideloaded
    or the host can change under an installed plugin — without this gate an
    incompatible plugin's ``load()`` would still run against the wrong host API.
    Missing plugin.json or no SciQLop requirement means no claim → compatible.
    """
    from .plugin_desc import PluginDesc
    from SciQLop.components.plugins.compat import (
        plugin_is_compatible, sciqlop_specifier, host_version,
    )
    path = os.path.join(folder, plugin, "plugin.json")
    if not os.path.isfile(path):
        return True
    try:
        desc = PluginDesc.from_json(path)
    except Exception:
        return True  # malformed desc is reported on the registration path
    if plugin_is_compatible(desc.python_dependencies):
        return True
    log.warning(
        "Skipping plugin %r: requires SciQLop %s but host is %s",
        plugin, sciqlop_specifier(desc.python_dependencies) or "(any)", host_version())
    return False


def entry_point_host_compatible(ep: importlib.metadata.EntryPoint) -> bool:
    """Backstop gate: refuse to load an entry-point plugin whose declared
    SciQLop requirement the running host doesn't satisfy.

    Mirrors plugin_host_compatible for folder plugins, but reads the
    requirement from the installed distribution's metadata (Requires-Dist)
    instead of a plugin.json. Missing dist or no SciQLop requirement means no
    claim → compatible.
    """
    from SciQLop.components.plugins.compat import (
        plugin_is_compatible, sciqlop_specifier, host_version,
    )
    requires = ep.dist.requires if ep.dist else None
    if plugin_is_compatible(requires or []):
        return True
    log.warning(
        "Skipping plugin %r: requires SciQLop %s but host is %s",
        ep.name, sciqlop_specifier(requires or []) or "(any)", host_version())
    return False


# Names load_all() or live loading already tried: a plugin is loaded at most once
# per process, whether its load() returned something or not.
_attempted: set = set()


def _enabled_plugins(settings, ep_plugins) -> list:
    """(folder, name) of every enabled, host-compatible plugin; folder is None
    for an entry-point plugin. Registers newly found plugins in *settings*."""
    from .plugin_desc import PluginDesc
    from SciQLop.components.plugins.backend.settings import PluginConfig
    plugin_list = []
    for folder in plugins_folders(settings):
        plugins = list_plugins(folder)
        log.info(f"Plugins found: {plugins}")
        for plugin in plugins:
            if plugin not in settings.plugins:
                try:
                    desc = PluginDesc.from_json(os.path.join(folder, plugin, "plugin.json"))
                except Exception as e:
                    log.warning(f"Skipping plugin {plugin}: {e}")
                    continue
                settings.plugins[plugin] = PluginConfig()
                if desc.disabled:
                    log.info(f"Plugin {plugin} is disabled by default")
                    settings.plugins[plugin].enabled = False
                    continue
            if settings.plugins[plugin].enabled and plugin_host_compatible(folder, plugin):
                plugin_list.append((folder, plugin))

    for name, ep in ep_plugins.items():
        if name not in settings.plugins:
            settings.plugins[name] = PluginConfig()
        if not settings.plugins[name].enabled:
            log.info(f"Entry-point plugin {name} is disabled")
            continue
        if entry_point_host_compatible(ep):
            plugin_list.append((None, name))
    return plugin_list


@dataclass(frozen=True)
class _Entry:
    folder: Optional[str]
    name: str
    desc: object  # PluginDesc or None

    @property
    def candidate(self):
        from .resolver import Candidate
        if self.desc is None:
            return Candidate(self.name, "0")
        return Candidate(self.name, self.desc.version, tuple(self.desc.dependencies),
                         tuple(self.desc.optional_dependencies))


def _read_desc(path) -> object:
    from .plugin_desc import PluginDesc
    if path is None or not os.path.isfile(path):
        return None
    try:
        return PluginDesc.from_json(str(path))
    except Exception as e:
        log.warning(f"Ignoring {path}: {e}")
        return None


def _entry_point_desc_path(ep) -> Optional[Path]:
    """plugin.json shipped next to the entry point's module, found in the distribution's file list.

    simplify: editable installs often list no package files, so their plugin.json is not found and the
    plugin loads without dependencies. Upgrade path: fall back to importlib.util.find_spec(ep.module)."""
    files = getattr(getattr(ep, "dist", None), "files", None)
    module = getattr(ep, "module", "")
    if not files or not module:
        return None
    parts = module.split(".")
    wanted = {"/".join(parts + ["plugin.json"]), "/".join(parts[:-1] + ["plugin.json"])}
    found = next((f for f in files if f.as_posix() in wanted), None)
    return Path(ep.dist.locate_file(found)) if found is not None else None


def _desc(folder, name, ep_plugins):
    if folder is None:
        return _read_desc(_entry_point_desc_path(ep_plugins[name]))
    return _read_desc(os.path.join(folder, name, "plugin.json"))


def _import(entry: _Entry, ep_plugins):
    mod = ep_plugins[entry.name].load() if entry.folder is None else load_module(entry.folder, entry.name)
    if mod is None:
        raise ImportError(f"could not import plugin {entry.name} (see the log)")
    return mod


def _call_entry_function(mod, ctx, main_window):
    if hasattr(mod, "activate"):
        with owned_by(ctx.name):
            return mod.activate(ctx)
    with owned_by(f"legacy:{ctx.name}"):
        return mod.load(main_window)


def _activate_one(entry: _Entry, main_window, declared, ep_plugins) -> PluginState:
    version = entry.candidate.version
    ctx = PluginContext(entry.name, version, main_window, declared)
    try:
        mod = _import(entry, ep_plugins)
        log.info(f"Loading {entry.name}")
        api = _call_entry_function(mod, ctx, main_window)
    except Exception as e:
        log.error(f"Plugin {entry.name} failed to load: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return PluginState("failed", version, reason=f"{type(e).__name__}: {e}")
    if api is not None:
        loaded_plugins.__dict__[entry.name] = api
    return PluginState("active", version, api=api, module=mod, context=ctx)


def _ready(name: str) -> None:
    state = STATES[name]
    ready = getattr(state.module, "ready", None)
    if state.status != "active" or ready is None or not hasattr(state.module, "activate"):
        return
    try:
        with owned_by(name):
            ready(state.context)
    except Exception as e:
        log.error(f"Plugin {name}: ready() failed, its activate() contributions stay: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")


def _refuse(name: str, version: str, reason: str) -> None:
    STATES[name] = PluginState("refused", version, reason=reason)
    log.warning(f"Plugin {name} not loaded: {reason}")


def _blocked_by(required) -> Optional[str]:
    failed = sorted(d for d in required if d in STATES and STATES[d].status != "active")
    if not failed:
        return None
    state = STATES[failed[0]]
    return f"needs plugin {failed[0]!r}, which {state.status}: {state.reason}"


def _warn_on_provides_drift(entries, order) -> None:
    from .provides import provides_drift
    for name in order:
        state = STATES[name]
        if state.status == "active" and hasattr(state.module, "activate") and entries[name].desc is not None:
            for problem in provides_drift(name, entries[name].desc.provides):
                log.warning(f"Plugin {name}: {problem}")


def activate_all(plugin_list, main_window, ep_plugins=None) -> dict:
    """Activate *plugin_list* [(folder or None, name)] in dependency order, then run their ready() hooks."""
    from .resolver import resolve
    ep_plugins = ep_plugins if ep_plugins is not None else _discover_entry_point_plugins()
    entries = {name: _Entry(folder, name, _desc(folder, name, ep_plugins)) for folder, name in plugin_list}
    _attempted.update(entries)
    resolution = resolve({n: e.candidate for n, e in entries.items()}, active_versions())
    for name, reason in resolution.refused.items():
        _refuse(name, entries[name].candidate.version, reason)
    for name in resolution.order:
        blocked = _blocked_by(resolution.required[name])
        if blocked:
            _refuse(name, entries[name].candidate.version, blocked)
        else:
            STATES[name] = _activate_one(entries[name], main_window, resolution.declared[name], ep_plugins)
    for name in resolution.order:
        _ready(name)
    _warn_on_provides_drift(entries, resolution.order)
    return {name: STATES[name].api for name in entries}


def load_one(folder, name, main_window, ep_plugins=None):
    return activate_all([(folder, name)], main_window, ep_plugins).get(name)


def load_all(main_window):
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    ep_plugins = _discover_entry_point_plugins()
    with SciQLopPluginsSettings() as settings:
        plugin_list = _enabled_plugins(settings, ep_plugins)
    return activate_all(plugin_list, main_window, ep_plugins)


def new_enabled_plugins() -> list:
    """Enabled, compatible plugins that were never loaded in this process."""
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    with SciQLopPluginsSettings() as settings:
        plugins = _enabled_plugins(settings, _discover_entry_point_plugins())
    return [(folder, name) for folder, name in plugins if name not in _attempted]


def plugin_requirements(folder, name) -> list:
    """A folder plugin's declared python dependencies (entry points have none to add)."""
    from .plugin_desc import PluginDesc
    path = os.path.join(folder, name, "plugin.json") if folder else ""
    if not path or not os.path.isfile(path):
        return []
    try:
        return list(PluginDesc.from_json(path).python_dependencies)
    except Exception:
        return []


def missing_requirements(requirements) -> list:
    """The requirements the running environment does not satisfy (SciQLop excluded)."""
    from packaging.requirements import InvalidRequirement, Requirement
    from SciQLop.components.workspaces.backend.workspace_project import strip_host_provided
    missing = []
    for spec in strip_host_provided(list(requirements)):
        try:
            req = Requirement(spec)
        except InvalidRequirement:
            missing.append(spec)
            continue
        if req.marker is not None and not req.marker.evaluate():
            continue
        try:
            installed = importlib.metadata.version(req.name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(spec)
            continue
        if not req.specifier.contains(installed, prereleases=True):
            missing.append(spec)
    return missing
