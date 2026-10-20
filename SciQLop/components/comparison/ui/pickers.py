"""Per-dimension widgets that let the user pick the variants of a comparison (sciqlop.comparison_dimensions ids)."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget)

from SciQLop.components.comparison.backend.model import GraphSpec, Variant, base_specs, time_label
from SciQLop.components.comparison.ui.inner_panel import provider_and_node
from SciQLop.components.plotting.panel_template import PanelTemplate
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

VARIANT_ROLE = Qt.ItemDataRole.UserRole


class VariantPicker(QWidget):
    changed = Signal()

    def variants(self) -> list[Variant]:
        return []

    def set_variants(self, variants: list[Variant]) -> None:
        """Show variants picked earlier (edit mode, presets)."""

    def problem(self) -> Optional[str]:
        """Why Compare cannot run with what is picked, or None."""
        return None


def _variant_item(variant: Variant, checked: bool) -> QListWidgetItem:
    item = QListWidgetItem(variant.label)
    item.setData(VARIANT_ROLE, variant)
    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return item


def _checked_variants(view: QListWidget) -> list[Variant]:
    items = (view.item(row) for row in range(view.count()))
    return [item.data(VARIANT_ROLE) for item in items if item.checkState() == Qt.CheckState.Checked]


def _fill(view: QListWidget, variants: list[Variant], checked: bool) -> None:
    view.clear()
    for variant in variants:
        view.addItem(_variant_item(variant, checked))


def time_variant(event) -> Variant:
    return Variant(label=time_label(event.start.timestamp()),
                   params={"start": event.start.timestamp(), "stop": event.stop.timestamp()})


def _all_catalogs():
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    return [(provider, catalog) for provider in CatalogRegistry.instance().providers()
            for catalog in provider.catalogs()]


class TimePicker(VariantPicker):
    """simplify: free intervals are not offered yet; add a "custom interval" row when asked."""

    def __init__(self, template: PanelTemplate, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.catalog_combo = QComboBox()
        self.event_list = QListWidget()
        for provider, catalog in _all_catalogs():
            self.catalog_combo.addItem("/".join([provider.name, *catalog.path, catalog.name]), (provider, catalog))
        self.catalog_combo.setCurrentIndex(-1)
        self.catalog_combo.currentIndexChanged.connect(self._show_catalog)
        self.event_list.itemChanged.connect(lambda _item: self.changed.emit())
        layout = QVBoxLayout(self)
        layout.addWidget(self.catalog_combo)
        layout.addWidget(self.event_list)

    def _show_catalog(self, index: int) -> None:
        picked = self.catalog_combo.itemData(index)
        events = picked[0].events(picked[1]) if picked is not None else []
        _fill(self.event_list, [time_variant(e) for e in events], checked=False)
        self.changed.emit()

    def variants(self) -> list[Variant]:
        return _checked_variants(self.event_list)

    def set_variants(self, variants: list[Variant]) -> None:
        self.catalog_combo.blockSignals(True)
        self.catalog_combo.setCurrentIndex(-1)
        self.catalog_combo.blockSignals(False)
        _fill(self.event_list, variants, checked=True)
        self.changed.emit()


def _spec_label(template: PanelTemplate, spec: GraphSpec) -> str:
    product = template.plots[spec.plot_index].products[spec.product_index]
    return f"plot {spec.plot_index + 1}: {product.label or spec.path.split('//')[-1]}"


def _target_combo(template: PanelTemplate, specs: list[GraphSpec]) -> QComboBox:
    combo = QComboBox()
    for spec in specs:
        combo.addItem(_spec_label(template, spec), spec)
    return combo


def product_node(path: str):
    return provider_and_node(path)[1]


def is_spectrogram(node) -> Optional[bool]:
    from SciQLop.core.product_kinds import SPECTROGRAM, product_kind_of
    kind = product_kind_of(node)
    return None if kind is None else kind.id == SPECTROGRAM


class _ProductLineEdit(QLineEdit):
    """Takes a pasted product path or a product dropped from the products tree."""

    def _accept_products(self, event, fallback) -> None:
        from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
        if event.mimeData().hasFormat(PRODUCT_LIST_MIME_TYPE):
            event.acceptProposedAction()
        else:
            fallback(event)

    def dragEnterEvent(self, event):
        self._accept_products(event, super().dragEnterEvent)

    def dragMoveEvent(self, event):
        # QLineEdit's own dragMoveEvent only accepts text, which would reject a products-tree drag mid-move.
        self._accept_products(event, super().dragMoveEvent)

    def dropEvent(self, event):
        from SciQLop.core.mime import decode_mime, tree_product_path
        from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE
        products = decode_mime(event.mimeData(), [PRODUCT_LIST_MIME_TYPE])
        if products:
            self.setText(tree_product_path("//".join(products[0])))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class ProductPicker(VariantPicker):
    """simplify: one product variant per dialog; add a variant list like SettingsPicker's when asked."""

    def __init__(self, template: PanelTemplate, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.target_combo = _target_combo(template, base_specs(template))
        self.path_edit = _ProductLineEdit()
        self.path_edit.setPlaceholderText("paste a product path or drop a product here")
        self.target_combo.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self.path_edit.textChanged.connect(lambda _t: self.changed.emit())
        layout = QFormLayout(self)
        layout.addRow("Replace", self.target_combo)
        layout.addRow("with", self.path_edit)

    def _path(self) -> str:
        return self.path_edit.text().strip()

    def problem(self) -> Optional[str]:
        if self.target_combo.currentData() is None:
            return "the base panel has no product to replace"
        if self._path() and product_node(self._path()) is None:
            return f"{self._path()!r} is not in the products tree"
        return None

    def variants(self) -> list[Variant]:
        target, path = self.target_combo.currentData(), self._path()
        if target is None or not path or self.problem() is not None:
            return []
        colormap = is_spectrogram(product_node(path))
        return [Variant(label=path.split("//")[-1], params={
            "target": list(target.key), "path": path,
            "is_colormap": target.is_colormap if colormap is None else colormap})]

    def set_variants(self, variants: list[Variant]) -> None:
        if variants:
            params = variants[0].params
            keys = [tuple(self.target_combo.itemData(i).key) for i in range(self.target_combo.count())]
            target = tuple(params.get("target", ()))
            if target in keys:
                self.target_combo.setCurrentIndex(keys.index(target))
            self.path_edit.setText(params.get("path", ""))


def knobs_of(path: str) -> list:
    """Main thread only: the knob specs the product's provider declares, [] when none or unknown."""
    provider, node = provider_and_node(path)
    if provider is None:
        return []
    try:
        return list(provider.get_knobs(node) or [])
    except Exception:
        log.warning(f"get_knobs failed for {path}", exc_info=True)
        return []


def knobs_label(knobs: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in knobs.items()) or "unchanged"


class SettingsPicker(VariantPicker):
    def __init__(self, template: PanelTemplate, parent: Optional[QWidget] = None):
        from SciQLop.components.plotting.ui.knob_inspector.delegates import delegate_for_spec
        super().__init__(parent)
        self._delegate_for_spec = delegate_for_spec
        specs = [s for s in base_specs(template) if knobs_of(s.path)]
        self.target_combo = _target_combo(template, specs)
        self.knobs_box = QWidget()
        self.knobs_layout = QFormLayout(self.knobs_box)
        self.delegates: dict = {}
        self._baseline: dict = {}
        self.add_button = QPushButton("Add variant")
        self.variant_list = QListWidget()
        self.target_combo.currentIndexChanged.connect(self._show_knobs)
        self.add_button.clicked.connect(self.add_variant)
        self.variant_list.itemChanged.connect(lambda _item: self.changed.emit())
        layout = QVBoxLayout(self)
        layout.addWidget(self.target_combo)
        layout.addWidget(self.knobs_box)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.add_button)
        layout.addLayout(row)
        layout.addWidget(self.variant_list)
        self._show_knobs(self.target_combo.currentIndex())

    def _show_knobs(self, index: int) -> None:
        while self.knobs_layout.rowCount():
            self.knobs_layout.removeRow(0)
        target = self.target_combo.itemData(index)
        self.delegates, self._baseline = {}, {}
        for knob in knobs_of(target.path) if target is not None else []:
            self._baseline[knob.name] = target.knobs.get(knob.name, getattr(knob, "default", None))
            delegate = self._delegate_for_spec(knob)
            delegate.set_value(self._baseline[knob.name])
            self.knobs_layout.addRow(knob.label or knob.name, delegate)
            self.delegates[knob.name] = delegate
        self.add_button.setEnabled(bool(self.delegates))
        _fill(self.variant_list, [], checked=True)
        self.changed.emit()

    def add_variant(self) -> None:
        target = self.target_combo.currentData()
        if target is None:
            return
        values = {name: d.get_value() for name, d in self.delegates.items()}
        changed = {k: v for k, v in values.items() if self._baseline.get(k) != v}
        self.variant_list.addItem(_variant_item(
            Variant(label=knobs_label(changed), params={"target": list(target.key), "knobs": changed}), True))
        self.changed.emit()

    def variants(self) -> list[Variant]:
        return _checked_variants(self.variant_list)

    def set_variants(self, variants: list[Variant]) -> None:
        _fill(self.variant_list, variants, checked=True)
        self.changed.emit()


class NoPicker(VariantPicker):
    """A dimension without a picker widget: keeps the variants it was given (edit mode) untouched."""

    def __init__(self, template: PanelTemplate, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._variants: list[Variant] = []
        label = QLabel("no picker for this kind of comparison — use compare() from Python")
        label.setWordWrap(True)
        QVBoxLayout(self).addWidget(label)

    def variants(self) -> list[Variant]:
        return list(self._variants)

    def set_variants(self, variants: list[Variant]) -> None:
        self._variants = list(variants)
        self.changed.emit()


PICKERS: dict[str, Callable[[PanelTemplate, Optional[QWidget]], VariantPicker]] = {
    "time": TimePicker,
    "product": ProductPicker,
    "settings": SettingsPicker,
}


def picker_for(dimension_id: str, template: PanelTemplate, parent: Optional[QWidget] = None) -> VariantPicker:
    return PICKERS.get(dimension_id, NoPicker)(template, parent)
