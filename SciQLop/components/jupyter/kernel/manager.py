from jupyqt import EmbeddedJupyter
from PySide6.QtCore import QObject
from SciQLop.user_api.magics import register_all_magics

_invoker = None


def invoke_on_main_thread(func, *args, **kwargs):
    """Run func on the Qt main thread, blocking until done.

    Safe to call from the kernel background thread. No-op if already
    on the main thread. The invoker is created during KernelManager
    construction (on the main thread) so its QObject receiver lives
    on the correct thread.
    """
    if _invoker is None:
        return func(*args, **kwargs)
    return _invoker(func, *args, **kwargs)


class KernelManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._jupyter = EmbeddedJupyter()
        global _invoker
        _invoker = self._jupyter._invoker
        register_all_magics(self._jupyter.shell)

    @property
    def shell(self):
        return self._jupyter.shell

    def start(self, port=0, cwd=None):
        self._jupyter.start(port=port, cwd=cwd)

    def push_variables(self, variables: dict):
        self._jupyter.push(variables)

    def wrap_qt(self, obj):
        return self._jupyter.wrap_qt(obj)

    def widget(self):
        return self._jupyter.widget()

    def open_in_browser(self):
        self._jupyter.open_in_browser()

    def shutdown(self):
        self._jupyter.shutdown()
