import os
import traceback
import importlib
from PySide6.QtCore import QRunnable, Slot, Signal, QThreadPool, QObject

here = os.path.dirname(os.path.realpath(__file__))

threadpool = QThreadPool()


class WorkerSignals(QObject):
    result = Signal(object)


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
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            self.signals.result.emit(self.fn(*self.args, **self.kwargs))
        except Exception as e:
            print(f"Oups can't load {name} , {e}")
            traceback.print_exc()


def load_plugin(mod, main_window):
    if mod:
        try:
            return mod.load(main_window)
        except Exception as e:
            print(f"Oups can't load {mod} , {e}")
            traceback.print_exc()


def load_module(name):
    try:
        mod = importlib.import_module(f"SciQLop.plugins.{name}", "*")
        return mod
    except Exception as e:
        print(f"Oups can't load {name} , {e}")
        traceback.print_exc()


def background_load(plugin, main_window):
    w = Worker(load_module, plugin)
    w.signals.result.connect(lambda mod: load_plugin(mod, main_window))
    return threadpool.start(w)


def load_all(main_window):
    plugin_list = [f[:-3] for f in os.listdir(here) if f[-3:] == '.py' and f != '__init__.py']
    print(plugin_list)
    return [background_load(plugin, main_window) for plugin in plugin_list]
