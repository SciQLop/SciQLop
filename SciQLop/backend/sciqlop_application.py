from PySide6 import QtWidgets, QtPrintSupport, QtOpenGL, QtQml, QtCore, QtGui
from typing import Dict, List, Optional, Tuple, Union, Any
from SciQLop.backend.theming.loader import load_stylesheets, build_palette
from qasync import QEventLoop, QApplication
import asyncio
import sys


class SciQLopApp(QApplication):
    quickstart_shortcuts_added = QtCore.Signal(str)
    panels_list_changed = QtCore.Signal(list)

    def __init__(self, args):
        from . import sciqlop_logging
        super(SciQLopApp, self).__init__(args)
        self.setOrganizationName("LPP")
        self.setOrganizationDomain("lpp.fr")
        self.setApplicationName("SciQLop")
        # self.setAttribute(QtCore.Qt.AA_UseStyleSheetPropagationInWidgetStyles, True)
        self._palette = build_palette("white", self.palette())
        self.setPalette(self._palette)
        self.load_stylesheet()
        sciqlop_logging.setup(capture_stdout=False)
        self._quickstart_shortcuts: Dict[str, Dict[str, Any]] = {}

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

    def load_stylesheet(self, path=None):
        self.setStyleSheet(load_stylesheets(self._palette))


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
            self.run_until_complete(self.app_close_event.wait())


_event_loop = None


def sciqlop_event_loop() -> _SciQLopEventLoop:
    global _event_loop
    if _event_loop is None:
        _event_loop = _SciQLopEventLoop()
    return _event_loop
