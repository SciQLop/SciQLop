from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLabel

from SciQLop.core.ui import fit_combo_to_content


CATALOG_MODES = [("View", "view"), ("Jump", "jump"), ("Edit", "edit")]


def _make_mode_combo(parent):
    w = QComboBox(parent)
    for label, value in CATALOG_MODES:
        w.addItem(label, userData=value)
    w.setToolTip("Catalog interaction mode")
    fit_combo_to_content(w)
    return w


class CatalogChrome(QWidget):
    """Per-panel catalog controls: interaction mode + target catalog for span creation.

    The target combo is shown only while it has content (typically while in
    edit mode with at least one editable catalog loaded).
    """

    mode_changed = Signal(str)
    target_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._mode_label = QLabel("Catalog:", self)
        self._mode_combo = _make_mode_combo(self)
        self._target_combo = QComboBox(self)
        self._target_combo.setToolTip("Target catalog for new events")
        self._target_combo.setVisible(False)

        layout.addWidget(self._mode_label)
        layout.addWidget(self._mode_combo)
        layout.addWidget(self._target_combo)

        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)

    @property
    def mode(self) -> str:
        return self._mode_combo.currentData()

    @mode.setter
    def mode(self, value: str):
        for i in range(self._mode_combo.count()):
            if self._mode_combo.itemData(i) == value:
                if self._mode_combo.currentIndex() != i:
                    self._mode_combo.blockSignals(True)
                    self._mode_combo.setCurrentIndex(i)
                    self._mode_combo.blockSignals(False)
                return

    def set_targets(self, items: list[tuple[str, str]]) -> None:
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        for name, uuid in items:
            self._target_combo.addItem(name, userData=uuid)
        self._target_combo.blockSignals(False)
        fit_combo_to_content(self._target_combo)
        self._target_combo.setVisible(len(items) > 0)
        if items:
            self._on_target_changed(0)

    def clear_targets(self) -> None:
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        self._target_combo.blockSignals(False)
        self._target_combo.setVisible(False)

    def selected_target(self) -> str | None:
        if self._target_combo.count() == 0:
            return None
        return self._target_combo.currentData()

    def _on_mode_changed(self, _index: int):
        value = self._mode_combo.currentData()
        if value is not None:
            self.mode_changed.emit(value)

    def _on_target_changed(self, index: int):
        uuid = self._target_combo.itemData(index)
        if uuid is not None:
            self.target_changed.emit(uuid)
