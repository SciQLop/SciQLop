import importlib
import importlib.metadata
import os
import traceback
from typing import TYPE_CHECKING, List, Optional
from types import SimpleNamespace
from SciQLop.components.sciqlop_logging import getLogger

# Re-exported: plugins_folders lives in a Qt-free module so the launcher can
# reach it without importing this one, which pulls in the GUI stack.
from ..folders import plugins_folders  # noqa: F401

if TYPE_CHECKING:
    from ..settings import SciQLopPluginsSettings  # noqa: F401  forward-ref target

loaded_plugins = SimpleNamespace()

log = getLogger(__name__)


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
    mod = load_module(path, name)
    if mod:
        try:
            log.info(f"Loading {name}")
            r = mod.load(main_window)
            if r:
                loaded_plugins.__dict__[name] = r
            return r
        except Exception as e:
            log.error(f"Oups can't load {name} from {mod} , {e}")
            log.error(f"Traceback: {traceback.format_exc()}")
    else:
        log.error(f"Oups can't load {name} , {mod}")


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


def _load_entry_point_plugin(ep: importlib.metadata.EntryPoint, main_window):
    try:
        mod = ep.load()
        log.info(f"Loading entry-point plugin {ep.name}")
        r = mod.load(main_window)
        if r:
            loaded_plugins.__dict__[ep.name] = r
        return r
    except Exception as e:
        log.error(f"Failed to load entry-point plugin {ep.name}: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return None


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


def load_one(folder, name, main_window, ep_plugins=None):
    _attempted.add(name)
    if folder is None:
        ep_plugins = ep_plugins if ep_plugins is not None else _discover_entry_point_plugins()
        return _load_entry_point_plugin(ep_plugins[name], main_window)
    return load_plugin(folder, name, main_window)


def load_all(main_window):
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    ep_plugins = _discover_entry_point_plugins()
    with SciQLopPluginsSettings() as settings:
        plugin_list = _enabled_plugins(settings, ep_plugins)
    return {plugin: load_one(folder, plugin, main_window, ep_plugins) for folder, plugin in plugin_list}


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
