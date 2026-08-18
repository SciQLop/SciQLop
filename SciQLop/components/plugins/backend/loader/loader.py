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


def load_all(main_window):
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings, PluginConfig
    from .plugin_desc import PluginDesc
    plugin_list = []
    ep_plugins = _discover_entry_point_plugins()
    with SciQLopPluginsSettings() as settings:
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
            plugin_list.append((None, name))

    results = {}
    for folder, plugin in plugin_list:
        if folder is None:
            results[plugin] = _load_entry_point_plugin(ep_plugins[plugin], main_window)
        else:
            results[plugin] = load_plugin(folder, plugin, main_window)
    return results
