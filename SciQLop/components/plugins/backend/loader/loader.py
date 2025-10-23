import importlib
import os
import traceback
from typing import List
from types import SimpleNamespace
from SciQLop.components.sciqlop_logging import getLogger

from PySide6.QtCore import QRunnable, Slot, Signal, QThreadPool, QObject, QThread

loaded_plugins = SimpleNamespace()

log = getLogger(__name__)


def plugins_folders() -> List[str]:
    from SciQLop import plugins
    from ..settings import SciQLopPluginsSettings, USER_PLUGINS_FOLDERS
    bundled = os.path.dirname(os.path.realpath(plugins.__file__))
    return [bundled, USER_PLUGINS_FOLDERS] + list(SciQLopPluginsSettings().extra_plugins_folders)


class WorkerSignals(QObject):
    result = Signal(object, object)


class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        log.info(f"Loading {fn.__name__} args={args} kwargs={kwargs}")
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            log.info(f"Loading {self.fn.__name__}")
            self.signals.result.emit(*self.fn(*self.args, **self.kwargs))
        except Exception as e:
            log.error(f"Oups can't load {self.fn.__name__} , {e}")
            log.error(f"Traceback: {traceback.format_exc()}")


def load_plugin(name, mod, main_window):
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
        mod = import_from_path(name, os.path.join(path, name ,  "__init__.py"))
        return name, mod
    except Exception as e:
        log.error(f"Oups can't load {name} , {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return "", None


def background_load(plugin, main_window):
    log.info(f"Loading {plugin}")
    w = Worker(load_module, plugin)
    w.signals.result.connect(lambda name, mod: load_plugin(name, mod, main_window))
    return QThreadPool.globalInstance().start(w)


def list_plugins_as_modules(plugin_path):
    return [f[:-3] for f in os.listdir(plugin_path) if f[-3:] == '.py' and f != '__init__.py']


def list_plugins_as_packages(plugin_path):
    return [f for f in os.listdir(plugin_path) if os.path.isdir(f"{plugin_path}/{f}") and not f.startswith('_')]


def list_plugins(plugin_path):
    return list_plugins_as_modules(plugin_path) + list_plugins_as_packages(plugin_path)


def load_all(main_window):
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings, PluginConfig
    from .plugin_desc import PluginDesc
    plugin_list = []
    with SciQLopPluginsSettings() as settings:
        for folder in plugins_folders():
            plugins = list_plugins(folder)
            log.info(f"Plugins found: {plugins}")
            for plugin in plugins:
                if plugin not in settings.plugins:
                    desc = PluginDesc.from_json(os.path.join(folder, plugin, "plugin.json"))
                    settings.plugins[plugin] = PluginConfig()
                    if desc.disabled:
                        log.info(f"Plugin {plugin} is disabled by default")
                        settings.plugins[plugin].enabled = False
                        continue
                if settings.plugins[plugin].enabled:
                    plugin_list.append((folder, plugin))

    return {plugin: load_plugin(*load_module(folder, plugin), main_window) for folder, plugin in plugin_list}
