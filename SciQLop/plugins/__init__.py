import importlib
import os
import traceback
from types import SimpleNamespace
from SciQLop.backend.sciqlop_logging import getLogger

from PySide6.QtCore import QRunnable, Slot, Signal, QThreadPool, QObject, QThread

here = os.path.dirname(os.path.realpath(__file__))

loaded_plugins = SimpleNamespace()

log = getLogger(__name__)


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
            loaded_plugins.__dict__[name] = r
            return r
        except Exception as e:
            log.error(f"Oups can't load {name} from {mod} , {e}")
            log.error(f"Traceback: {traceback.format_exc()}")
    else:
        log.error(f"Oups can't load {name} , {mod}")


def load_module(name):
    try:
        mod = importlib.import_module(f"SciQLop.plugins.{name}", "*")
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
    plugin_list = list_plugins(here)
    log.info(f"Plugins found: {plugin_list}")
    return {plugin: load_plugin(*load_module(plugin), main_window) for plugin in plugin_list}
