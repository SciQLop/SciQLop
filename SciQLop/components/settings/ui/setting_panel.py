from PySide6.QtCore import Slot, QModelIndex, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListView, QLineEdit,
    QHBoxLayout, QSplitter, QScrollArea, QSpacerItem, QSizePolicy, QFrame,
    QStackedWidget,
)
from PySide6.QtGui import QFont, QPalette, QShowEvent
from SciQLop.components.settings import SettingsCategory, ConfigEntry
from SciQLop.components.sciqlop_logging import getLogger
from ..backend.model import SettingsFilterProxyModel
from .settings_delegates import get_delegate_for_field, is_field_editable
from SciQLop.core.ui import HLine, increase_font_size, Metrics

log = getLogger(__name__)


class SettingsCategories(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsCategories")
        self.setModel(SettingsFilterProxyModel(self))
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)

    @Slot(str)
    def filter(self, text: str):
        model = self.model()
        if isinstance(model, SettingsFilterProxyModel):
            model.setFilterFixedString(text)


class SettingsLeftPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsLeftPanel")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 0, 8)
        self.layout.setSpacing(6)

        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter settings...")
        self.filter.setClearButtonEnabled(True)

        self.layout.addWidget(self.filter)
        self.categories_list = SettingsCategories()
        self.layout.addWidget(self.categories_list)
        self.filter.textChanged.connect(self.categories_list.filter)


class SettingRow(QFrame):
    def __init__(self, field_name: str, field_info, instance, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingRow")
        self._field_name = field_name
        self._instance = instance

        self._delegate = get_delegate_for_field(field_name, field_info)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Metrics.margins(1.5, 0.8, 1.5, 0.8))
        layout.setSpacing(Metrics.spacing(0.4))

        name_label = QLabel(field_name.replace('_', ' ').title())
        font = name_label.font()
        font.setWeight(QFont.Weight.Medium)
        name_label.setFont(font)
        layout.addWidget(name_label)

        if field_info.description:
            desc_label = QLabel(field_info.description)
            desc_label.setObjectName("SettingDescription")
            desc_font = desc_label.font()
            desc_font.setPointSizeF(desc_font.pointSizeF() * 0.85)
            desc_label.setFont(desc_font)
            desc_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        layout.addWidget(self._delegate)

        current_value = getattr(instance, field_name)
        self._delegate.set_value(current_value)
        self._delegate.value_changed.connect(self._on_value_changed)

    @Slot(object)
    def _on_value_changed(self, value):
        try:
            setattr(self._instance, self._field_name, value)
            self._instance.save()
        except Exception as e:
            log.error(f"Failed to save setting {self._field_name}: {e}")
            current = getattr(self._instance, self._field_name)
            self._delegate.set_value(current)


class SectionHeader(QWidget):
    """A section header with title and separator line."""
    def __init__(self, title: str, level: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("SectionHeader")
        layout = QVBoxLayout(self)
        indent = Metrics.em(1.5 + level * 1.5)
        layout.setContentsMargins(indent, Metrics.em(1.5), Metrics.em(1.5), Metrics.spacing())
        layout.setSpacing(Metrics.spacing(0.4))

        lbl = QLabel(title.title())
        lbl.setObjectName("SectionTitle")
        font = lbl.font()
        font.setBold(True)
        if level == 0:
            font.setPointSizeF(font.pointSizeF() * 1.15)
        lbl.setFont(font)
        layout.addWidget(lbl)
        layout.addWidget(HLine())


def _build_entry_widgets(entry_cls: type[ConfigEntry], instance: ConfigEntry,
                         parent_layout: QVBoxLayout, level: int = 0):
    """Recursively build SettingRow widgets for an entry, nesting into
    child ConfigEntry fields."""
    for field_name, field_info in entry_cls.model_fields.items():
        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, ConfigEntry):
            # Nested ConfigEntry — render as a sub-section
            child_instance = getattr(instance, field_name)
            parent_layout.addWidget(
                SectionHeader(field_name.replace('_', ' '), level=level + 1)
            )
            _build_entry_widgets(annotation, child_instance, parent_layout, level=level + 1)
        elif is_field_editable(field_name, field_info):
            row = SettingRow(field_name, field_info, instance)
            if level > 0:
                indent = Metrics.em(1.5 + level * 1.5)
                row.layout().setContentsMargins(indent, Metrics.spacing(), Metrics.em(1.5), Metrics.spacing())
            parent_layout.addWidget(row)


class CategoryView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsCategoryView")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel()
        self._header.setObjectName("SettingsCategoryHeader")
        self._header.setContentsMargins(*Metrics.margins(1.5, 1.2, 1.5, 1.2))
        increase_font_size(self._header, 1.4)
        font = self._header.font()
        font.setBold(True)
        self._header.setFont(font)
        layout.addWidget(self._header)
        layout.addWidget(HLine())

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._page_cache: dict[str, int] = {}

    def clear_cache(self):
        """Remove all cached pages so they are rebuilt on next selection."""
        while self._stack.count():
            w = self._stack.widget(0)
            self._stack.removeWidget(w)
            w.deleteLater()
        self._page_cache.clear()

    def show_category(self, category_name: str):
        self._header.setText(category_name.title())

        if category_name in self._page_cache:
            self._stack.setCurrentIndex(self._page_cache[category_name])
            return

        page = self._build_category_page(category_name)
        idx = self._stack.addWidget(page)
        self._page_cache[category_name] = idx
        self._stack.setCurrentIndex(idx)

    def _build_category_page(self, category_name: str) -> QWidget:
        entries = [
            cls for cls in ConfigEntry.list_entries().values()
            if cls.category == category_name
        ]

        subcategory_groups: dict[str, list] = {}
        for entry_cls in entries:
            subcategory_groups.setdefault(entry_cls.subcategory, []).append(entry_cls)
        sorted_groups = sorted(subcategory_groups.items())
        multiple_subcategories = len(sorted_groups) > 1

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(*Metrics.margins(1, 0.5, 1, 1))
        inner_layout.setSpacing(Metrics.spacing())

        for subcategory, entry_classes in sorted_groups:
            if multiple_subcategories:
                inner_layout.addWidget(SectionHeader(subcategory, level=0))
            for entry_cls in entry_classes:
                instance = entry_cls()
                _build_entry_widgets(entry_cls, instance, inner_layout, level=0)

        inner_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        scroll.setWidget(inner)
        return scroll


class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPanel")
        self._initialized = False
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._splitter.setHandleWidth(1)
        self._splitter.setContentsMargins(0, 0, 0, 0)

        self._left_panel = SettingsLeftPanel()
        self._splitter.addWidget(self._left_panel)

        self._category_view = CategoryView()
        self._splitter.addWidget(self._category_view)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)

        # Wire up selection
        sel = self._left_panel.categories_list.selectionModel()
        sel.currentChanged.connect(self._on_category_changed)

    def sizeHint(self):
        return Metrics.size(55, 35)

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        if not self._initialized:
            self._initialized = True
            self._refresh()

    def _refresh(self):
        """Rebuild the model from current ConfigEntry registry and select first item."""
        proxy = self._left_panel.categories_list.model()
        if isinstance(proxy, SettingsFilterProxyModel):
            proxy.rebuild()
        self._category_view.clear_cache()
        model = self._left_panel.categories_list.model()
        if model.rowCount(QModelIndex()) > 0:
            self._left_panel.categories_list.setCurrentIndex(
                model.index(0, 0, QModelIndex())
            )

    @Slot(QModelIndex, QModelIndex)
    def _on_category_changed(self, current: QModelIndex, _previous: QModelIndex):
        name = current.data(Qt.ItemDataRole.DisplayRole)
        if name:
            self._category_view.show_category(name)
