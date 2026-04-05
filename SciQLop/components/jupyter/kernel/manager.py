from jupyqt import EmbeddedJupyter
from PySide6.QtCore import QObject
from PySide6.QtGui import QColor
from SciQLop.user_api.magics import register_all_magics
from SciQLop.user_api.threading import init_invoker, invoke_on_main_thread  # noqa: F401 — re-export


def _is_dark_palette() -> bool:
    from SciQLop.components.theming.palette import SCIQLOP_PALETTE
    window_color = SCIQLOP_PALETTE.get("Window", "#ffffff")
    c = QColor(window_color)
    return (0.299 * c.redF() + 0.587 * c.greenF() + 0.114 * c.blueF()) < 0.5


def _sync_theme_via_api(launcher):
    """Set JupyterLab theme via its REST settings API."""
    import urllib.request
    import json

    theme = "JupyterLab Dark" if _is_dark_palette() else "JupyterLab Light"
    url = f"http://localhost:{launcher.port}/lab/api/settings/@jupyterlab/apputils-extension:themes"
    data = json.dumps({"raw": json.dumps({"theme": theme})}).encode()
    req = urllib.request.Request(
        url, data=data, method="PUT",
        headers={
            "Authorization": f"token {launcher.token}",
            "Content-Type": "application/json",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


class KernelManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._jupyter = EmbeddedJupyter()
        init_invoker(self._jupyter._invoker)
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
        w = self._jupyter.widget()
        if self._jupyter._launcher is not None:
            from concurrent.futures import ThreadPoolExecutor
            _pool = ThreadPoolExecutor(max_workers=1)
            _pool.submit(_sync_theme_via_api, self._jupyter._launcher)
        return w

    def open_in_browser(self):
        self._jupyter.open_in_browser()

    def shutdown(self):
        self._jupyter.shutdown()
