import shiboken6
from PySide6 import QtWidgets, QtCore, QtGui
from typing import Dict, List, Optional, Any, Callable, TYPE_CHECKING
from SciQLop.components.theming import load_stylesheets, setup_palette, SciQLopStyle
from SciQLop.components.theming.palette import active_theme_name
from SciQLop.components.theming.themes import DEFAULT_THEME
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


def _saved_theme() -> str:
    return SciQLopStyle().color_palette


class SciQLopApp(QApplication):
    quickstart_shortcuts_added = QtCore.Signal(str)
    quickstart_shortcuts_removed = QtCore.Signal(str)
    panels_list_changed = QtCore.Signal(list)
    theme_changed = QtCore.Signal(str)

    def __init__(self, args):
        from SciQLop.components import sciqlop_logging
        from SciQLop.core.common.macos import set_bundle_name
        set_bundle_name("SciQLop")
        super(SciQLopApp, self).__init__(args)
        self.setOrganizationName("LPP")
        self.setOrganizationDomain("lpp.fr")
        self.setApplicationName("SciQLop")
        sciqlop_logging.setup(capture_stdout=False)
        from SciQLop.components.profiling import hang_dump, sampler, watchdog
        self._watchdog = None
        self._watchdog_timer = None
        if sciqlop_logging.is_debug_mode():
            hang_dump.install_signal_dump()
            sampler.maybe_start_from_settings()
            self._watchdog = watchdog.Watchdog()
            self._watchdog.start()
            self._watchdog_timer = watchdog.start_qt_heartbeat(self._watchdog)
        # self.setAttribute(QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles, True)
        self._current_palette = setup_palette(palette_name=_saved_theme())
        self._current_palette_name = active_theme_name()
        self.setPalette(self._current_palette)
        self.load_stylesheet()
        from SciQLop.components.theming.themes import THEMES
        THEMES.signals.added.connect(self._on_theme_added)
        THEMES.signals.removed.connect(self._on_theme_removed)
        SciQLopStyle._notifier.changed.connect(self._on_style_changed)
        from SciQLop.core.quickstart import QUICKSTART
        QUICKSTART.signals.added.connect(self._on_quickstart_added)
        QUICKSTART.signals.removed.connect(self._on_quickstart_removed)
        from SciQLop.components.command_palette.backend.registry import CommandRegistry
        self._command_registry = CommandRegistry()

    def add_quickstart_shortcut(self, name: str, description: str, icon: QtGui.QPixmap or QtGui.QIcon,
                                callback: callable):
        from SciQLop.core.extensions import current_owner
        from SciQLop.core.quickstart import QuickstartShortcut, contribute_shortcut
        contribute_shortcut(QuickstartShortcut(name, description, icon, callback), current_owner())

    def _on_quickstart_added(self, shortcut) -> None:
        if not shiboken6.isValid(self):
            return
        self.quickstart_shortcuts_added.emit(shortcut.name)

    def _on_quickstart_removed(self, shortcut) -> None:
        if not shiboken6.isValid(self):
            return
        self.quickstart_shortcuts_removed.emit(shortcut.name)

    @QtCore.Property(list)
    def quickstart_shortcuts(self) -> List[str]:
        from SciQLop.core.quickstart import QUICKSTART
        return QUICKSTART.keys()

    def quickstart_shortcut(self, name: str) -> Optional[Dict[str, Any]]:
        from SciQLop.core.quickstart import QUICKSTART
        shortcut = QUICKSTART.find(name)
        return shortcut.as_dict() if shortcut is not None else None

    @property
    def command_registry(self) -> "CommandRegistry":
        return self._command_registry

    def _on_style_changed(self, field_name: str, value):
        if field_name == "color_palette":
            self.apply_theme(value)

    def apply_theme(self, palette_name: str):
        self._current_palette = setup_palette(palette_name=palette_name)
        self._current_palette_name = active_theme_name()
        self.setPalette(self._current_palette)
        self.load_stylesheet()
        self._update_plot_themes()
        self.theme_changed.emit(self._current_palette_name)

    def _on_theme_added(self, theme) -> None:
        """A plugin theme saved as the user's choice applies once its plugin contributes it."""
        if not shiboken6.isValid(self):
            return
        if theme.id == _saved_theme() and theme.id != self._current_palette_name:
            self.apply_theme(theme.id)

    def _on_theme_removed(self, theme) -> None:
        """The setting is kept: the theme comes back with its plugin on the next start."""
        if not shiboken6.isValid(self):
            return
        if theme.id == self._current_palette_name:
            self.apply_theme(DEFAULT_THEME)

    def current_theme(self) -> str:
        """Return the name of the active color palette."""
        return self._current_palette_name

    def _update_plot_themes(self):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        for widget in self.allWidgets():
            if isinstance(widget, TimeSyncPanel):
                widget.update_theme()

    def load_stylesheet(self):
        self.setStyleSheet(load_stylesheets(self._current_palette, self._current_palette_name))


def sciqlop_app() -> SciQLopApp:
    """The running SciQLopApp — or a main-thread proxy of it, off the GUI thread.

    Kernel cells (notebook and agent alike) run on the jupyqt kernel thread, and
    this accessor is their usual door to the whole widget tree. Returning the raw
    application there made `sciqlop_app().topLevelWidgets()[0].resize(...)` a
    two-line process abort; the proxy marshals such calls to the GUI thread.
    """
    from SciQLop.user_api.threading import main_thread_safe

    if QtWidgets.QApplication.instance() is None:
        app = SciQLopApp(sys.argv)
    else:
        app = QtWidgets.QApplication.instance()
    if not isinstance(app, SciQLopApp):
        raise TypeError(
            f"QApplication is {type(app).__name__}, expected SciQLopApp. "
            "A foreign QApplication was created before SciQLop initialized."
        )
    return main_thread_safe(app)


class _SciQLopEventLoop(QEventLoop):
    def __init__(self):
        super().__init__(sciqlop_app())
        asyncio.set_event_loop(self)

    def exec(self):
        # run_forever returns when the Qt loop exits. Waiting on an Event set by
        # aboutToQuit instead left a task that aboutToQuit woke on the already
        # stopped loop: "is not the running loop", "Task was destroyed".
        with self:
            self.run_forever()

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
