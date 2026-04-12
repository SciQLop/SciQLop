from PySide6 import QtWidgets, QtCore, QtGui
from typing import Dict, List, Optional, Any, Callable, TYPE_CHECKING
from SciQLop.components.theming import load_stylesheets, setup_palette, SciQLopStyle
from qasync import QEventLoop, QApplication
import asyncio
import math
import sys
import time

if TYPE_CHECKING:
    from SciQLop.components.command_palette.backend.registry import CommandRegistry


# qasync's _SimpleTimer.add_callback crashes on infinite delays (e.g. anyio.sleep_forever())
# because QTimer can't handle int(inf * 1000). For infinite delays, skip the timer entirely —
# the handle is never meant to fire and a real timer would block Qt shutdown.
# See: https://github.com/CabbageDevelopment/qasync/issues/
def _patch_qasync_infinite_timer():
    from qasync import _SimpleTimer
    _original_add_callback = _SimpleTimer.add_callback

    def _safe_add_callback(self, handle, delay=0):
        if math.isinf(delay):
            return handle
        return _original_add_callback(self, handle, delay)

    _SimpleTimer.add_callback = _safe_add_callback


_patch_qasync_infinite_timer()


class SciQLopApp(QApplication):
    quickstart_shortcuts_added = QtCore.Signal(str)
    panels_list_changed = QtCore.Signal(list)
    theme_changed = QtCore.Signal(str)

    def __init__(self, args):
        from SciQLop.components import sciqlop_logging
        super(SciQLopApp, self).__init__(args)
        self.setOrganizationName("LPP")
        self.setOrganizationDomain("lpp.fr")
        self.setApplicationName("SciQLop")
        sciqlop_logging.setup(capture_stdout=False)
        # self.setAttribute(QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles, True)
        self._current_palette_name = SciQLopStyle().color_palette
        self._current_palette = setup_palette(palette_name=self._current_palette_name)
        self.setPalette(self._current_palette)
        self.load_stylesheet()
        SciQLopStyle._notifier.changed.connect(self._on_style_changed)
        self._quickstart_shortcuts: Dict[str, Dict[str, Any]] = {}
        from SciQLop.components.command_palette.backend.registry import CommandRegistry
        self._command_registry = CommandRegistry()

    def add_quickstart_shortcut(self, name: str, description: str, icon: QtGui.QPixmap or QtGui.QIcon,
                                callback: callable):
        self._quickstart_shortcuts[name] = (
            {"name": name, "description": description, "icon": icon, "callback": callback})
        self.quickstart_shortcuts_added.emit(name)

    @QtCore.Property(list)
    def quickstart_shortcuts(self) -> List[str]:
        return list(self._quickstart_shortcuts.keys())

    def quickstart_shortcut(self, name: str) -> Optional[Dict[str, Any]]:
        return self._quickstart_shortcuts.get(name, None)

    @property
    def command_registry(self) -> "CommandRegistry":
        return self._command_registry

    def _on_style_changed(self, field_name: str, value):
        if field_name == "color_palette":
            self.apply_theme(value)

    def apply_theme(self, palette_name: str):
        self._current_palette_name = palette_name
        self._current_palette = setup_palette(palette_name=palette_name)
        self.setPalette(self._current_palette)
        self.load_stylesheet()
        self._update_plot_themes()
        self.theme_changed.emit(palette_name)

    def _update_plot_themes(self):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        for widget in self.allWidgets():
            if isinstance(widget, TimeSyncPanel):
                widget.update_theme()

    def load_stylesheet(self):
        self.setStyleSheet(load_stylesheets(self._current_palette, self._current_palette_name))


def sciqlop_app() -> SciQLopApp:
    if QtWidgets.QApplication.instance() is None:
        app = SciQLopApp(sys.argv)
    else:
        app = QtWidgets.QApplication.instance()
    return app


class _SciQLopEventLoop(QEventLoop):
    def __init__(self):
        super().__init__(sciqlop_app())
        asyncio.set_event_loop(self)
        app = sciqlop_app()
        self.app_close_event = asyncio.Event()
        app.aboutToQuit.connect(self.app_close_event.set)

    def exec(self):
        with self:
            try:
                self.run_until_complete(self.app_close_event.wait())
            except RuntimeError:
                # qasync raises "Event loop stopped before Future completed."
                # when the Qt event loop exits before aboutToQuit fires —
                # this is normal shutdown on macOS (Cmd+Q / window close).
                pass

    def active_sleep(self, delay: float):
        start = time.time()
        while time.time() - start < delay:
            sciqlop_app().processEvents()

    def active_sleep_for(self, delay: float, predicate: Callable[[], bool]):
        start = time.time()
        while time.time() - start < delay:
            if predicate():
                break
            sciqlop_app().processEvents()


_event_loop = None


def sciqlop_event_loop() -> _SciQLopEventLoop:
    global _event_loop
    if _event_loop is None:
        _event_loop = _SciQLopEventLoop()
    return _event_loop
