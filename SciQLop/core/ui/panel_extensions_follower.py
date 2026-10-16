"""One main window's view of sciqlop.panel_extensions: attach to its panels, run the clean-ups (plan 2g).

Bound-method slots, not a receiver context (this PySide6 refuses one): EP signals live for the process,
main windows do not, so each slot first checks this follower is alive."""
from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

import shiboken6
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.panel_extensions import PANEL_EXTENSIONS, PanelExtension
from SciQLop.core.panel_kinds import panel_kind_of

log = getLogger(__name__)

_Entry = Tuple[QWidget, PanelExtension, Optional[Callable[[], None]]]


def matches(ext: PanelExtension, panel: QWidget) -> bool:
    return not ext.kinds or panel_kind_of(panel) in ext.kinds


class PanelExtensionsFollower(QObject):
    def __init__(self, main_window):
        super().__init__(main_window)
        self._main_window = main_window
        self._cleanups: Dict[Tuple[str, int], _Entry] = {}
        PANEL_EXTENSIONS.signals.added.connect(self.added)
        PANEL_EXTENSIONS.signals.removed.connect(self.removed)

    def panel_opened(self, panel: QWidget) -> None:
        if not shiboken6.isValid(self):
            return
        self._forget_dead_panels()
        for ext in PANEL_EXTENSIONS.list():
            if matches(ext, panel):
                self._attach(ext, panel)

    def panel_closing(self, panel: QWidget) -> None:
        if not shiboken6.isValid(self):
            return
        self._run_cleanups(lambda ext_id, entry: entry[0] is panel)

    def added(self, ext: PanelExtension) -> None:
        if not shiboken6.isValid(self):
            return
        self._run_cleanups(lambda ext_id, entry: ext_id == ext.id)
        for panel in self._main_window.panels():
            if matches(ext, panel):
                self._attach(ext, panel)

    def removed(self, ext: PanelExtension) -> None:
        if not shiboken6.isValid(self):
            return
        self._run_cleanups(lambda ext_id, entry: ext_id == ext.id)

    def _forget_dead_panels(self) -> None:
        """A panel destroyed without closing (e.g. by user code) never reaches panel_closing."""
        self._run_cleanups(lambda ext_id, entry: not shiboken6.isValid(entry[0]))

    def _run_cleanups(self, selected: Callable[[str, _Entry], bool]) -> None:
        keys = [key for key, entry in self._cleanups.items() if selected(key[0], entry)]
        for key in keys:
            self._cleanup(*self._cleanups.pop(key))

    def _attach(self, ext: PanelExtension, panel: QWidget) -> None:
        try:
            cleanup = ext.attach(panel)
        except Exception:
            log.error(f"panel extension {ext.id} failed on {panel.objectName()!r}", exc_info=True)
            cleanup = None
        self._cleanups[(ext.id, id(panel))] = (panel, ext, cleanup)

    @staticmethod
    def _cleanup(panel: QWidget, ext: PanelExtension, cleanup: Optional[Callable[[], None]]) -> None:
        # A dead panel took the plugin's objects with it: nothing left to clean up.
        if cleanup is None or not shiboken6.isValid(panel):
            return
        try:
            cleanup()
        except Exception:
            log.error(f"panel extension {ext.id} failed on {panel.objectName()!r}", exc_info=True)
