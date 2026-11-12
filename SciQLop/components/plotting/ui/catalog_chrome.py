from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QComboBox, QLabel, QDoubleSpinBox, QPushButton

from SciQLop.core.ui import fit_combo_to_content
from SciQLop.components.shortcuts import bind_tooltip
from SciQLop.core.ui.tooltips import rich_tooltip


CATALOG_MODES = [("View", "view"), ("Jump", "jump"), ("Edit", "edit")]
NO_TARGET = "No editable catalog on this panel"


def _make_mode_combo(parent):
    w = QComboBox(parent)
    for label, value in CATALOG_MODES:
        w.addItem(label, userData=value)
    bind_tooltip(
        w, "panel.cycle_catalog_mode", "Catalog interaction mode",
        "View: click an event to select it. Jump: picking an event in the "
        "catalog list sets the panel range to it (zoom-out factor on the "
        "right). Edit: hold Shift and click to start a new event, move, "
        "then click again to finish (Esc cancels).")
    fit_combo_to_content(w)
    return w


def _make_zoom_out_spin(parent):
    from SciQLop.components.catalogs.backend.jump_settings import CatalogJumpSettings
    w = QDoubleSpinBox(parent)
    w.setRange(1.0, 100.0)
    w.setSingleStep(0.5)
    w.setDecimals(1)
    w.setPrefix("\u00d7")
    w.setValue(CatalogJumpSettings().zoom_out_factor)
    w.setToolTip(rich_tooltip(
        "Jump zoom-out factor",
        "Visible range around the picked event, as a multiple of its "
        "duration. 1 fills the panel with the event; 2 leaves half an "
        "event of margin on each side."))
    return w


class CatalogChrome(QWidget):
    """Per-panel catalog controls: interaction mode, jump zoom-out factor,
    target catalog for span creation.

    The zoom-out spinbox is shown only in jump mode; the target combo and the
    "New catalog…" button only in edit mode. With no editable catalog on the
    panel the combo says so, greyed out, instead of hiding.
    """

    mode_changed = Signal(str)
    new_catalog_requested = Signal()
    target_changed = Signal(str)
    zoom_out_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._mode_label = QLabel("Catalog mode:", self)
        self._mode_combo = _make_mode_combo(self)
        self._mode_label.setToolTip(self._mode_combo.toolTip())
        self._mode_label.setBuddy(self._mode_combo)

        self._target_combo = QComboBox(self)
        self._target_combo.setToolTip(rich_tooltip(
            "Target catalog",
            "Catalog that newly created events are added to."))
        self._target_combo.setVisible(False)
        self._target_label = QLabel("Add to:", self)
        self._target_label.setToolTip(self._target_combo.toolTip())
        self._target_label.setBuddy(self._target_combo)
        self._target_label.setVisible(False)
        self._new_catalog_btn = QPushButton("New catalog…", self)
        self._new_catalog_btn.setToolTip(rich_tooltip(
            "New catalog",
            "Create a catalog, show it on this panel and add new events to it."))
        self._new_catalog_btn.setVisible(False)
        self._new_catalog_btn.clicked.connect(self.new_catalog_requested)

        self._zoom_out_spin = _make_zoom_out_spin(self)
        self._zoom_out_label = QLabel("Zoom out:", self)
        self._zoom_out_label.setToolTip(self._zoom_out_spin.toolTip())
        self._zoom_out_label.setBuddy(self._zoom_out_spin)

        layout.addWidget(self._mode_label)
        layout.addWidget(self._mode_combo)
        layout.addWidget(self._zoom_out_label)
        layout.addWidget(self._zoom_out_spin)
        layout.addWidget(self._target_label)
        layout.addWidget(self._target_combo)
        layout.addWidget(self._new_catalog_btn)

        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._mode_combo.currentIndexChanged.connect(self._sync_zoom_out_visibility)
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        self._zoom_out_spin.valueChanged.connect(self.zoom_out_changed)
        self._sync_zoom_out_visibility()

    @property
    def zoom_out_factor(self) -> float:
        return self._zoom_out_spin.value()

    def _sync_zoom_out_visibility(self, *_):
        visible = self.mode == "jump"
        self._zoom_out_label.setVisible(visible)
        self._zoom_out_spin.setVisible(visible)

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
                    self._sync_zoom_out_visibility()
                return

    def cycle_mode(self) -> None:
        combo = self._mode_combo
        combo.setCurrentIndex((combo.currentIndex() + 1) % combo.count())

    def set_targets(self, items: list[tuple[str, str]]) -> None:
        previous = self.selected_target()
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        for name, uuid in items:
            self._target_combo.addItem(name, userData=uuid)
        if not items:
            self._target_combo.addItem(NO_TARGET, userData=None)
        index = max(0, self._target_combo.findData(previous)) if items else 0
        self._target_combo.setCurrentIndex(index)
        self._target_combo.blockSignals(False)
        self._target_combo.setEnabled(bool(items))
        fit_combo_to_content(self._target_combo)
        self._set_target_widgets_visible(True)
        if items:
            self._on_target_changed(index)

    def _set_target_widgets_visible(self, visible: bool) -> None:
        for widget in (self._target_label, self._target_combo, self._new_catalog_btn):
            widget.setVisible(visible)

    def clear_targets(self) -> None:
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        self._target_combo.blockSignals(False)
        self._set_target_widgets_visible(False)

    def selected_target(self) -> str | None:
        return self._target_combo.currentData()

    def select_target(self, uuid: str) -> None:
        index = self._target_combo.findData(uuid)
        if index >= 0:
            self._target_combo.setCurrentIndex(index)

    def _on_mode_changed(self, _index: int):
        value = self._mode_combo.currentData()
        if value is not None:
            self.mode_changed.emit(value)

    def _on_target_changed(self, index: int):
        uuid = self._target_combo.itemData(index)
        if uuid is not None:
            self.target_changed.emit(uuid)
