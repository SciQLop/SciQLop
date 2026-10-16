"""A panel that stands in for one whose kind is not available; it keeps its tree so saving again loses nothing.

It looks its plugin up in the App Store, offers to install it, and becomes the real panel once the kind is
contributed (plan 2g §5)."""
import copy
import json
from typing import Optional

import shiboken6
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from SciQLop.components.plugins.install_offer import find_store_entry
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.panel_kinds import KIND_PROPERTY, PANEL_KINDS
from SciQLop.core.plot_kinds import plugin_of
from SciQLop.core.unique_names import auto_name, release_name

log = getLogger(__name__)

PLACEHOLDER_PANEL = "sciqlop.placeholder_panel"


def _message(kind: str) -> str:
    return f"This panel needs plugin {plugin_of(kind)!r} (panel kind {kind!r})."


def _install_outcome(result: dict) -> str:
    if not result.get("ok"):
        return f"Install failed: {result.get('error', 'unknown error')}"
    if result.get("restart_required"):
        return "Installed. Restart SciQLop to open this panel."
    if not result.get("loaded", True):
        return f"Installed, but not loaded: {result.get('reason', '')}"
    return "Installed."


def _centered_label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    return label


class PlaceholderPanel(QWidget):
    """Tagged with KIND_PROPERTY so it docks, lists and closes like any panel; not a PANEL_KINDS contribution."""

    def __init__(self, root: dict, parent=None, main_window=None):
        super().__init__(parent)
        self.root = copy.deepcopy(root)
        self.missing_kind = root["kind"]
        self.lookup_done = False
        self._main_window = main_window
        self._install: Optional[QPushButton] = None
        self.setProperty(KIND_PROPERTY, PLACEHOLDER_PANEL)
        self._label = _centered_label(_message(self.missing_kind), self)
        self._status = _centered_label("", self)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._status)
        PANEL_KINDS.signals.added.connect(self._on_kind_added)
        find_store_entry(self.missing_kind, self._on_entry)

    def message(self) -> str:
        return self._label.text()

    def status(self) -> str:
        return self._status.text()

    def install_button(self) -> Optional[QPushButton]:
        return self._install

    def _on_entry(self, entry: Optional[dict]) -> None:
        if not shiboken6.isValid(self):
            return
        self.lookup_done = True
        if entry is not None and self._install is None:
            self._install = QPushButton(f"Install {entry['name']}", self)
            self._install.clicked.connect(lambda: self._start_install(entry))
            self.layout().addWidget(self._install, alignment=Qt.AlignmentFlag.AlignCenter)

    def _start_install(self, entry: dict) -> None:
        from SciQLop.components.appstore.backend import AppStoreBackend
        # Parented to the main window, not to self: the install and hot-load go on if this placeholder closes.
        backend = AppStoreBackend(self._main_window, packages=[entry])
        backend.install_finished.connect(self._on_install_finished)
        backend.install_finished.connect(backend.deleteLater)
        self._install.setEnabled(False)
        self._status.setText(f"Installing {entry['name']}…")
        backend.install_package(entry["name"])

    def _on_install_finished(self, payload: str) -> None:
        if not shiboken6.isValid(self):
            return
        result = json.loads(payload)
        self._status.setText(_install_outcome(result))
        if self._install is not None and not result.get("ok"):
            self._install.setEnabled(True)

    def _on_kind_added(self, kind) -> None:
        if not shiboken6.isValid(self) or kind.id != self.missing_kind or self._main_window is None:
            return
        # Deferred: `added` fires inside the plugin's activate; the swap waits until activate has finished
        # (or failed, and the loader withdrew the kind).
        QTimer.singleShot(0, self, self._swap_if_contributed)

    def _swap_if_contributed(self) -> None:
        if not shiboken6.isValid(self) or self.missing_kind not in PANEL_KINDS:
            return
        if self._main_window._dock_of(self) is None:  # already swapped by an earlier contribution
            return
        try:
            _swap(self._main_window, self)
        except Exception as e:
            log.error(f"Could not open the {self.missing_kind!r} panel in place of its placeholder: {e}",
                      exc_info=True)
            self._status.setText(f"Could not open this panel: {e}")


def open_placeholder(main_window, root: dict, name: str) -> PlaceholderPanel:
    from SciQLop.core.ui.panel_host import dock_panel
    name = auto_name(base="Panel", name=name)
    try:
        widget = PlaceholderPanel(root, main_window=main_window)
        widget.setObjectName(name)
        widget.setWindowTitle(name)
        dock_panel(main_window, widget, PLACEHOLDER_PANEL)
    except Exception:
        release_name(name)
        raise
    return widget


def _swap(main_window, placeholder: PlaceholderPanel) -> QWidget:
    """Open the real panel next to the placeholder, close the placeholder, then give the real one its name.
    Why not release the name and open under it: QtAds keys docks by name, and closing the placeholder's dock
    would then also drop the real panel's dock from the dock manager's map."""
    name = placeholder.objectName()
    dock = main_window._dock_of(placeholder)
    area = dock.dockAreaWidget() if dock is not None else None
    config = copy.deepcopy(placeholder.root.get("config", {}))
    real = main_window._open_panel(placeholder.missing_kind, None, area, config)
    PANEL_KINDS.signals.added.disconnect(placeholder._on_kind_added)
    main_window.remove_panel(placeholder)
    real.setObjectName(name)
    real.setWindowTitle(real.objectName())
    return real
