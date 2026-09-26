import asyncio
import concurrent.futures
import re as _re
import traceback as _traceback
from typing import Any, Dict

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


async def _run_and_capture(shell, code: str) -> Dict[str, Any]:
    """Run a cell on the kernel thread, mirroring jupyqt's own execution path
    (run_cell_async for top-level await, run_cell otherwise) under output capture."""
    from IPython.utils.capture import capture_output

    try:
        transformed = shell.transform_cell(code)
    except Exception:
        transformed = code
    with capture_output() as cap:
        if shell.should_run_async(code, transformed_cell=transformed):
            result = await shell.run_cell_async(code, store_history=False)
        else:
            result = shell.run_cell(code, store_history=False)
    error = None
    if not result.success:
        err = result.error_in_exec or result.error_before_exec
        error = f"{type(err).__name__}: {err}" if err is not None else "cell failed"
    return {
        "stdout": cap.stdout or "",
        "stderr": cap.stderr or "",
        "result": repr(result.result) if result.result is not None else None,
        "success": bool(result.success),
        "error": error,
    }


async def _run_and_capture_rich(shell, code: str, execution_count: int) -> Dict[str, Any]:
    """Like _run_and_capture but also returns rich display outputs, a traceback,
    and the execution_count, for notebook-style write-back."""
    from IPython.utils.capture import capture_output

    try:
        transformed = shell.transform_cell(code)
    except Exception:
        transformed = code
    with capture_output() as cap:
        if shell.should_run_async(code, transformed_cell=transformed):
            result = await shell.run_cell_async(code, store_history=False)
        else:
            result = shell.run_cell(code, store_history=False)
    error = None
    tb: list = []
    if not result.success:
        err = result.error_in_exec or result.error_before_exec
        error = f"{type(err).__name__}: {err}" if err is not None else "cell failed"
        if err is not None:
            tb = _traceback.format_exception(type(err), err, err.__traceback__)
    displays = [{"data": dict(o.data), "metadata": dict(o.metadata or {})}
                for o in cap.outputs]
    stdout = cap.stdout or ""
    if result.result is not None:
        # shell.run_cell's display_trap re-installs the shell displayhook, which
        # echoes "Out[N]: <repr>\n" to captured stdout. result.result already
        # carries the value, so strip only that exact trailing echo (anchored at
        # end, matching the actual repr) to avoid duplicating it as a stream.
        echo = _re.compile(r"Out\[\d+\]: " + _re.escape(repr(result.result)) + r"\n?\Z")
        stdout = echo.sub("", stdout)
    return {
        "stdout": stdout,
        "stderr": cap.stderr or "",
        "result": repr(result.result) if result.result is not None else None,
        "displays": displays,
        "success": bool(result.success),
        "error": error,
        "traceback": tb,
        "execution_count": execution_count,
    }


class KernelManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._jupyter = EmbeddedJupyter()
        self._exec_count = 0
        init_invoker(self._jupyter._invoker)
        register_all_magics(self._jupyter.shell)

    @property
    def shell(self):
        return self._jupyter.shell

    @property
    def notebook_hooks(self):
        return self._jupyter.notebook_hooks

    def start(self, port=0, cwd=None):
        self._jupyter.start(port=port, cwd=cwd)

    def push_variables(self, variables: dict):
        self._jupyter.push(variables)

    def interrupt(self) -> None:
        """Raise KeyboardInterrupt in the kernel thread to stop a running cell."""
        self._jupyter.interrupt()

    def submit_cell(self, code: str) -> concurrent.futures.Future:
        """Schedule ``code`` on the kernel thread — where cells run — and return a
        Future resolving to a captured-output dict (stdout/stderr/result/success/
        error). It never executes on the calling thread, so the GUI event loop
        stays responsive even while the cell blocks (e.g. a slow data fetch).
        Await it from the GUI loop via ``asyncio.wrap_future``.
        """
        loop = self._jupyter.kernel_thread.loop
        if loop is None:
            raise RuntimeError("kernel thread is not running")
        return asyncio.run_coroutine_threadsafe(_run_and_capture(self.shell, code), loop)

    def run_cell_capture(self, code: str) -> concurrent.futures.Future:
        """Schedule ``code`` on the kernel thread and return a Future resolving to
        a rich captured-output dict (stdout/stderr/result/displays/success/error/
        traceback/execution_count). Await via ``asyncio.wrap_future``."""
        loop = self._jupyter.kernel_thread.loop
        if loop is None:
            raise RuntimeError("kernel thread is not running")
        self._exec_count += 1
        return asyncio.run_coroutine_threadsafe(
            _run_and_capture_rich(self.shell, code, self._exec_count), loop,
        )

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
