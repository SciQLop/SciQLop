import importlib
import importlib.metadata
import os
import traceback
from typing import TYPE_CHECKING, List, Optional
from types import SimpleNamespace
from SciQLop.components.sciqlop_logging import getLogger

if TYPE_CHECKING:
    from ..settings import SciQLopPluginsSettings  # noqa: F401  forward-ref target

loaded_plugins = SimpleNamespace()

log = getLogger(__name__)


def plugins_folders(settings: Optional["SciQLopPluginsSettings"] = None) -> List[str]:
    from SciQLop import plugins
    from ..settings import SciQLopPluginsSettings, USER_PLUGINS_FOLDERS
    bundled = os.path.dirname(os.path.realpath(plugins.__file__))
    if settings is None:
        settings = SciQLopPluginsSettings()
    return [bundled, USER_PLUGINS_FOLDERS] + list(settings.extra_plugins_folders)


def import_from_path(module_name, file_path):
    import sys
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_module(path, name):
    try:
        import sys
        # if path not in sys.path:
        #    sys.path.insert(0, path)
        # mod = importlib.import_module(name, "*")
        mod = import_from_path(name, os.path.join(path, name, "__init__.py"))
        return mod
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
                if settings.plugins[plugin].enabled:
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
