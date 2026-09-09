from __future__ import annotations

from PySide6.QtCore import (
    QModelIndex, QPersistentModelIndex, QSortFilterProxyModel, Signal, QRect, QEvent,
    QItemSelectionModel, QTimer,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QSplitter,
    QStyledItemDelegate,
    QTableView,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QPen, QColor, QShortcut
from SciQLop.core.ui.tooltips import rich_tooltip
from SciQLop.components.theming.icons import get_icon

import math
from datetime import datetime, timezone, timedelta
import uuid as _uuid
from SciQLop.core.ui import Metrics
from ..backend.provider import Capability, CatalogProvider, Catalog, CatalogEvent
from .catalog_tree import CatalogTreeModel, DIRTY_PROVIDER_ROLE, LOADING_ROLE
from .event_table import EventTableModel, EventSortProxy


class _CatalogFilterProxy(QSortFilterProxyModel):
    """Case-insensitive substring filter that keeps ancestors of matching nodes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        regex = self.filterRegularExpression()
        if not regex.pattern():
            return True
        idx = self.sourceModel().index(source_row, 0, source_parent)
        name = self.sourceModel().data(idx, Qt.ItemDataRole.DisplayRole) or ""
        if regex.match(name).hasMatch():
            return True
        # Accept if any child matches (recursive)
        for row in range(self.sourceModel().rowCount(idx)):
            if self.filterAcceptsRow(row, idx):
                return True
        return False


class _SaveButtonDelegate(QStyledItemDelegate):
    """Renders a clickable save icon next to dirty provider nodes
    and an animated spinner next to loading catalog nodes."""

    save_clicked = Signal(QModelIndex)

    _ICON_SIZE = 16
    _SPINNER_SEGMENTS = 8
    _SPINNER_INTERVAL_MS = 80
    _SPINNER_OFFSETS = tuple(
        (math.cos(math.radians(i * 45)), math.sin(math.radians(i * 45)))
        for i in range(8)
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon = None
        self._spinner_angle = 0
        self._has_loading = False
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(self._SPINNER_INTERVAL_MS)
        self._spinner_timer.timeout.connect(self._tick_spinner)

    def _get_icon(self):
        if self._icon is None:
            self._icon = get_icon("save")
        return self._icon

    def _tick_spinner(self):
        self._spinner_angle = (self._spinner_angle + 360 // self._SPINNER_SEGMENTS) % 360
        if self.parent() is not None:
            self.parent().viewport().update()
        if not self._has_loading:
            self._spinner_timer.stop()
        self._has_loading = False

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.data(LOADING_ROLE):
            self._paint_spinner(painter, option)
            self._has_loading = True
            if not self._spinner_timer.isActive():
                self._spinner_timer.start()
        if index.data(DIRTY_PROVIDER_ROLE):
            self._get_icon().paint(painter, self._icon_rect(option))

    def _paint_spinner(self, painter, option):
        s = self._ICON_SIZE
        cx = option.rect.right() - s // 2 - 2
        cy = option.rect.top() + option.rect.height() // 2
        r = s // 2 - 2
        rot = math.radians(self._spinner_angle)
        cos_rot, sin_rot = math.cos(rot), math.sin(rot)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        for i, (ux, uy) in enumerate(self._SPINNER_OFFSETS):
            rx = ux * cos_rot - uy * sin_rot
            ry = ux * sin_rot + uy * cos_rot
            alpha = 255 - i * (200 // self._SPINNER_SEGMENTS)
            color = option.palette.text().color()
            color.setAlpha(max(alpha, 55))
            painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(
                int(cx + (r - 2) * rx), int(cy - (r - 2) * ry),
                int(cx + r * rx), int(cy - r * ry),
            )
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.data(DIRTY_PROVIDER_ROLE) or index.data(LOADING_ROLE):
            size.setWidth(size.width() + self._ICON_SIZE + 4)
        return size

    def _icon_rect(self, option):
        return QRect(
            option.rect.right() - self._ICON_SIZE - 2,
            option.rect.top() + (option.rect.height() - self._ICON_SIZE) // 2,
            self._ICON_SIZE,
            self._ICON_SIZE,
        )

    def editorEvent(self, event, model, option, index):
        if index.data(DIRTY_PROVIDER_ROLE):
            if event.type() == QEvent.Type.MouseButtonRelease:
                if self._icon_rect(option).contains(event.pos()):
                    self.save_clicked.emit(index)
                    return True
        return super().editorEvent(event, model, option, index)


class CatalogBrowser(QWidget):
    """Dock-ready widget: tree of providers/catalogs + event table."""

    event_selected = Signal(object)
    provider_error = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Catalogs")

        self._current_provider: CatalogProvider | None = None
        self._events_changed_provider: CatalogProvider | None = None
        self._current_catalog: Catalog | None = None
        self._panels: list = []
        self._expanded_before_filter: list[QPersistentModelIndex] = []
        self._highlighting = False
        self._manual_widths: dict[str, int] = {}

        # --- filter bar ---
        self._filter_bar = QLineEdit()
        self._filter_bar.setPlaceholderText("Filter catalogs…")
        self._filter_bar.setClearButtonEnabled(True)
        self._filter_bar.setToolTip(rich_tooltip(
            "Filter catalogs",
            "Filter the catalog tree by name."))

        # --- tree view (left) ---
        self._tree_model = CatalogTreeModel()
        self._tree_model.operation_failed.connect(self.provider_error)
        self._wire_provider_error_reporting()
        self._proxy_model = _CatalogFilterProxy()
        self._proxy_model.setSourceModel(self._tree_model)
        self._catalog_tree = QTreeView()
        self._catalog_tree.setModel(self._proxy_model)
        self._catalog_tree.setHeaderHidden(True)
        self._catalog_tree.setDragEnabled(True)
        self._catalog_tree.setAcceptDrops(True)
        self._catalog_tree.setDropIndicatorShown(True)
        self._catalog_tree.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._save_delegate = _SaveButtonDelegate(self._catalog_tree)
        self._save_delegate.save_clicked.connect(self._on_save_clicked)
        self._catalog_tree.setItemDelegate(self._save_delegate)
        self._catalog_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._catalog_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        self._catalog_tree.doubleClicked.connect(self._on_tree_double_clicked)
        self._catalog_tree.viewport().installEventFilter(self)
        self._catalog_tree.selectionModel().currentChanged.connect(self._on_catalog_selected)
        self._filter_bar.textChanged.connect(self._on_filter_changed)
        delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self._catalog_tree)
        delete_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        delete_shortcut.activated.connect(self._on_delete_selected_catalog)

        # --- event table (right) ---
        self._event_model = EventTableModel()
        self._sort_proxy = EventSortProxy(self)
        self._sort_proxy.setSourceModel(self._event_model)
        self._event_table = QTableView()
        self._event_table.setModel(self._sort_proxy)
        self._event_table.setSortingEnabled(True)
        self._event_table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self._event_table.horizontalHeader().setStretchLastSection(True)
        self._event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header = self._event_table.horizontalHeader()
        header.setSectionsMovable(True)
        header.sectionMoved.connect(lambda *_: self._save_view_state())
        header.sectionResized.connect(self._on_section_resized)
        self._width_save_timer = QTimer(self)
        self._width_save_timer.setSingleShot(True)
        self._width_save_timer.setInterval(250)
        self._width_save_timer.timeout.connect(self._save_view_state)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(
            lambda pos: self._open_column_popover(at_header_pos=pos)
        )
        self._event_model.modelReset.connect(self._fit_event_columns)
        self._event_table.selectionModel().currentChanged.connect(self._on_event_selected)
        self._event_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._event_table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._event_table.setDragEnabled(True)
        self._event_table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        # Matches the pre-existing "no modifier = link" default; Shift/Ctrl
        # (Option/Cmd on macOS) now come from Qt's own action resolution
        # instead of being re-derived from raw keyboard modifiers.
        self._event_table.setDefaultDropAction(Qt.DropAction.LinkAction)

        self._propagating_bulk_edit = False
        self._event_model.dataChanged.connect(self._on_event_data_changed)

        from .event_table_delegate import EventTableDelegate
        self._event_delegate = EventTableDelegate(self._event_model, self._event_table)
        self._event_table.setItemDelegate(self._event_delegate)

        # --- event toolbar (above table) ---
        self._add_event_action = QAction(get_icon("add"), "Add event", self)
        self._add_event_action.setVisible(False)
        self._add_event_action.triggered.connect(self._on_add_event)
        self._add_event_action.setToolTip(rich_tooltip(
            "Add event",
            "Create a new event in the target catalog."))

        self._delete_action = QAction(get_icon("delete"), "Delete", self)
        self._delete_action.setVisible(False)
        self._delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self._delete_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self._delete_action.triggered.connect(self._on_delete)
        self._delete_action.setToolTip(rich_tooltip(
            "Delete",
            "Delete the selected events from the catalog."))

        self._columns_action = QAction(get_icon("view_list"), "Columns", self)
        self._columns_action.setToolTip(rich_tooltip(
            "Columns",
            "Show, hide, or reorder the event-table columns."))
        self._columns_action.triggered.connect(lambda: self._open_column_popover())

        self._add_attr_action = QAction("Add attribute…", self)
        self._add_attr_action.setVisible(False)
        self._add_attr_action.setToolTip(rich_tooltip(
            "Add attribute…",
            "Add a metadata attribute to the selected events"
            " (or all events if none are selected)."))
        self._add_attr_action.triggered.connect(self._on_add_attribute_clicked)

        self._event_toolbar = QToolBar()
        self._event_toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._event_toolbar.addAction(self._add_event_action)
        self._event_toolbar.addAction(self._delete_action)
        self._event_toolbar.addAction(self._columns_action)
        self._event_toolbar.addAction(self._add_attr_action)

        # Shortcut fires only with the table focused; same actions also
        # populate the table's own right-click menu (_build_event_context_menu).
        self._event_table.addAction(self._delete_action)
        self._event_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._event_table.customContextMenuRequested.connect(self._on_event_table_context_menu)

        self._event_filter_bar = QLineEdit()
        self._event_filter_bar.setPlaceholderText("Filter events…")
        self._event_filter_bar.setClearButtonEnabled(True)
        self._event_filter_bar.setToolTip(rich_tooltip(
            "Filter events",
            "Filter the event table; matches any column."))
        # simplify: filterAcceptsRow is an O(rows x columns) scan (plus
        # per-cell display formatting) run on every keystroke -- fine up to
        # the thousands-of-events catalogs this targets, but a debounce is
        # cheap insurance. Upgrade path if that's ever not enough: cache a
        # lowercased searchable string per row, invalidated by dataChanged.
        self._event_filter_debounce = QTimer(self)
        self._event_filter_debounce.setSingleShot(True)
        self._event_filter_debounce.setInterval(200)
        self._event_filter_debounce.timeout.connect(
            lambda: self._sort_proxy.setFilterFixedString(self._event_filter_bar.text()))
        self._event_filter_bar.textChanged.connect(lambda _: self._event_filter_debounce.start())

        event_panel = QWidget()
        event_layout = QVBoxLayout(event_panel)
        event_layout.setContentsMargins(0, 0, 0, 0)
        event_layout.addWidget(self._event_toolbar)
        event_layout.addWidget(self._event_filter_bar)
        event_layout.addWidget(self._event_table, 1)

        # --- splitter ---
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._catalog_tree)
        self._splitter.addWidget(event_panel)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)

        # --- layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._filter_bar)
        layout.addWidget(self._splitter, 1)

    # ---- error reporting ----

    def _wire_provider_error_reporting(self) -> None:
        """Forward every provider's error_occurred to provider_error, for
        providers registered before and after this browser is constructed.

        Connects a bound method, not a lambda closing over self, to the
        process-lifetime CatalogRegistry singleton — per
        docs/qt-lifetime-patterns.md pattern 1, Qt auto-disconnects a bound
        QObject method when its receiver is destroyed. A lambda has no
        identifiable receiver, so it would stay connected forever and call
        into this (possibly destroyed) browser on every future registration.
        """
        from ..backend.registry import CatalogRegistry
        registry = CatalogRegistry.instance()
        for provider in registry.providers():
            provider.error_occurred.connect(self.provider_error)
        registry.provider_registered.connect(self._on_future_provider_registered)

    def _on_future_provider_registered(self, provider) -> None:
        provider.error_occurred.connect(self.provider_error)

    def _report_failure(self, description: str, exc: Exception) -> None:
        from SciQLop.components.sciqlop_logging import getLogger
        getLogger(__name__).warning("%s: %s", description, exc)
        self.provider_error.emit(f"{description}: {exc}")

    # ---- slots ----

    def _on_filter_changed(self, text: str) -> None:
        if text and not self._proxy_model.filterRegularExpression().pattern():
            self._expanded_before_filter = self._expanded_source_indexes()
        self._proxy_model.setFilterFixedString(text)
        if text:
            self._catalog_tree.expandAll()
        else:
            self._restore_expansion()

    def _expanded_source_indexes(self) -> list[QPersistentModelIndex]:
        result = []

        def walk(proxy_parent):
            for row in range(self._proxy_model.rowCount(proxy_parent)):
                idx = self._proxy_model.index(row, 0, proxy_parent)
                if self._catalog_tree.isExpanded(idx):
                    result.append(QPersistentModelIndex(self._proxy_model.mapToSource(idx)))
                    walk(idx)
        walk(QModelIndex())
        return result

    def _restore_expansion(self) -> None:
        self._catalog_tree.collapseAll()
        for source in self._expanded_before_filter:
            if source.isValid():
                self._catalog_tree.expand(self._proxy_model.mapFromSource(source))
        self._expanded_before_filter = []

    def eventFilter(self, obj, event):
        if (obj is self._catalog_tree.viewport()
                and event.type() == QEvent.Type.MouseButtonDblClick
                and self._pick_color_at(event.position().toPoint())):
            return True
        return super().eventFilter(obj, event)

    def _swatch_rect(self, proxy_index: QModelIndex) -> QRect:
        from PySide6.QtWidgets import QStyle
        tree = self._catalog_tree
        rect = tree.visualRect(proxy_index)
        icon = tree.iconSize().width()
        if icon <= 0:
            icon = tree.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        margin = tree.style().pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin) + 1
        return QRect(rect.left(), rect.top(), icon + 2 * margin, rect.height())

    def _pick_color_at(self, pos) -> bool:
        proxy_index = self._catalog_tree.indexAt(pos)
        if not proxy_index.isValid() or not self._swatch_rect(proxy_index).contains(pos):
            return False
        node = self._tree_model.node_from_index(self._proxy_model.mapToSource(proxy_index))
        if node.catalog is None:
            return False
        self._pick_catalog_color(node.catalog)
        return True

    def _on_tree_double_clicked(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(proxy_index)
        node = self._tree_model.node_from_index(source_index)
        if node.is_placeholder or (node.catalog is not None and
                self._tree_model.flags(source_index) & Qt.ItemFlag.ItemIsEditable):
            self._catalog_tree.edit(proxy_index)

    def _on_catalog_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(current)
        node = self._tree_model.node_from_index(source_index)
        if node is self._tree_model._root or node.is_placeholder:
            return
        if node.catalog is not None and node.catalog is self._current_catalog:
            return
        self._clear_event_filter_immediately()
        # Disconnect from previously connected provider
        if self._events_changed_provider is not None:
            try:
                self._events_changed_provider.events_changed.disconnect(self._on_events_changed)
            except RuntimeError:
                pass
            self._events_changed_provider = None
        if node.catalog is not None:
            self._current_provider = node.provider
            self._current_catalog = node.catalog
            self._event_model.set_context(node.provider, node.catalog)
            events = node.provider.events(node.catalog)
            self._event_model.set_events(events)
            self._apply_view_state(node.catalog)
            node.provider.events_changed.connect(self._on_events_changed)
            self._events_changed_provider = node.provider
        else:
            self._current_provider = node.provider
            self._current_catalog = None
            self._event_model.set_context(None, None)
            self._event_model.clear()
        self._update_toolbar()

    def _on_event_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        if self._highlighting:
            return
        if current.isValid():
            source_index = self._sort_proxy.mapToSource(current)
            event = self._event_model.event_at(source_index.row())
            if event is not None:
                self.event_selected.emit(event)

    def _on_event_data_changed(self, top_left, bottom_right, roles=None) -> None:
        if self._propagating_bulk_edit:
            return
        if top_left != bottom_right:
            return
        if self._current_provider is None or self._current_catalog is None:
            return
        proxy_idx = self._sort_proxy.mapFromSource(top_left)
        if not proxy_idx.isValid():
            return
        event = self._event_model.event_at(top_left.row())
        if event is None:
            return
        col = top_left.column()
        if col >= len(self._event_model._FIXED_COLUMNS):
            key = self._event_model._meta_keys[col - len(self._event_model._FIXED_COLUMNS)]
            value = event.meta.get(key)
        elif col == 0:
            value = event.start
        else:
            value = event.stop
        self._propagate_bulk_edit(proxy_idx, value)

    def _propagate_bulk_edit(self, proxy_idx, value) -> None:
        sm = self._event_table.selectionModel()
        if sm is None:
            return
        selected_rows = {idx.row() for idx in sm.selectedRows()}
        if proxy_idx.row() not in selected_rows or len(selected_rows) <= 1:
            return
        col = proxy_idx.column()
        source_origin = self._sort_proxy.mapToSource(proxy_idx)
        origin_event = self._event_model.event_at(source_origin.row())
        if origin_event is None:
            return
        targets = []
        for row in selected_rows:
            if row == proxy_idx.row():
                continue
            source_idx = self._sort_proxy.mapToSource(self._sort_proxy.index(row, col))
            ev = self._event_model.event_at(source_idx.row())
            if ev is not None and ev is not origin_event:
                targets.append(ev)
        if not targets:
            return
        self._propagating_bulk_edit = True
        try:
            if col == 0:
                for ev in targets:
                    ev.start = value
            elif col == 1:
                for ev in targets:
                    ev.stop = value
            else:
                key = self._event_model._meta_keys[col - len(self._event_model._FIXED_COLUMNS)]
                self._current_provider.set_events_meta(
                    self._current_catalog, targets, key, value,
                )
        finally:
            self._propagating_bulk_edit = False

    def _clear_event_filter_immediately(self) -> None:
        """Bypass the debounce: a catalog switch is a discrete navigation
        action, not a keystroke in the middle of typing, and delaying it
        would leave the OLD catalog's filter briefly applied to the NEW
        catalog's (just-loaded) events."""
        self._event_filter_bar.clear()  # emits textChanged, (re)starts the debounce
        self._event_filter_debounce.stop()
        self._sort_proxy.setFilterFixedString("")

    def _on_events_changed(self, catalog: Catalog) -> None:
        """Refresh event table when async loading completes for the selected
        catalog, or a peer's edit lands in a shared cocat catalog."""
        if self._current_catalog is None or catalog.uuid != self._current_catalog.uuid:
            return
        try:
            events = self._current_provider.events(self._current_catalog)
        except Exception as e:
            self._report_failure("Could not refresh events", e)
            return
        self._set_events_preserving_selection(events)

    def _row_for_uuid(self, uuid: str) -> int:
        for row in range(self._event_model.rowCount()):
            ev = self._event_model.event_at(row)
            if ev is not None and ev.uuid == uuid:
                return row
        return -1

    def _set_events_preserving_selection(self, events) -> None:
        """set_events() is a full model reset, which drops the table's
        selection -- surprising for a refresh the user didn't ask for (an
        async load completing, or a peer's edit landing in a shared cocat
        catalog), and for _on_add_event's own explicit refresh right after
        adding. Re-select whichever previously-selected events still exist
        by uuid afterward."""
        sm = self._event_table.selectionModel()
        selected_uuids = []
        if sm is not None:
            for proxy_idx in sm.selectedRows():
                source_idx = self._sort_proxy.mapToSource(proxy_idx)
                ev = self._event_model.event_at(source_idx.row())
                if ev is not None:
                    selected_uuids.append(ev.uuid)

        self._event_model.set_events(events)

        if sm is None or not selected_uuids:
            return
        first_proxy_idx = None
        for uuid in selected_uuids:
            row = self._row_for_uuid(uuid)
            if row < 0:
                continue
            proxy_idx = self._sort_proxy.mapFromSource(self._event_model.index(row, 0))
            if not proxy_idx.isValid():
                continue
            sm.select(proxy_idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            if first_proxy_idx is None:
                first_proxy_idx = proxy_idx
        if first_proxy_idx is not None:
            sm.setCurrentIndex(first_proxy_idx, QItemSelectionModel.SelectionFlag.NoUpdate)

    _COLUMN_FIT_SAMPLE_ROWS = 50
    _COLUMN_FIT_PADDING_PX = 16
    _COLUMN_FIT_MAX_WIDTH = 320

    def _fit_event_columns(self) -> None:
        """Resize columns to fit a capped row sample to keep large catalogs fast.

        Why: ResizeToContents on the header recomputes widths against every row
        on every model reset, which is O(rows × cols) and dominates rendering
        time for catalogs with many events and high-precision float columns.
        We sample the first N rows and use the widest header/value width.
        """
        view = self._event_table
        model = self._event_model
        cols = model.columnCount()
        rows = model.rowCount()
        if cols == 0:
            return
        header = view.horizontalHeader()
        header_fm = header.fontMetrics()
        cell_fm = view.fontMetrics()
        sample = min(rows, self._COLUMN_FIT_SAMPLE_ROWS)
        header.blockSignals(True)
        try:
            for col in range(cols):
                self._fit_column(col, sample, header_fm, cell_fm)
        finally:
            header.blockSignals(False)

    def _fit_column(self, col: int, sample: int, header_fm, cell_fm) -> None:
        model = self._event_model
        header = self._event_table.horizontalHeader()
        manual = self._manual_widths.get(self._column_key(col))
        if manual:
            header.resizeSection(col, manual)
        else:
            header_text = model.headerData(col, Qt.Orientation.Horizontal) or ""
            width = header_fm.horizontalAdvance(str(header_text))
            for row in range(sample):
                text = model.data(model.index(row, col), Qt.ItemDataRole.DisplayRole) or ""
                w = cell_fm.horizontalAdvance(str(text))
                if w > width:
                    width = w
            width = min(width + self._COLUMN_FIT_PADDING_PX, self._COLUMN_FIT_MAX_WIDTH)
            header.resizeSection(col, width)

    def _on_section_resized(self, logical: int, _old: int, new_size: int) -> None:
        header = self._event_table.horizontalHeader()
        is_stretched_last = (header.stretchLastSection()
                             and header.visualIndex(logical) == header.count() - 1)
        if new_size <= 0 or is_stretched_last or self._current_catalog is None:
            return
        self._manual_widths[self._column_key(logical)] = new_size
        self._width_save_timer.start()

    def _column_key(self, col: int) -> str:
        if col < len(self._event_model._FIXED_COLUMNS):
            return self._event_model._FIXED_COLUMNS[col]
        return self._event_model._meta_keys[col - len(self._event_model._FIXED_COLUMNS)]

    def _apply_view_state(self, catalog) -> None:
        from ..backend.event_table_view_state import get_view_state
        state = get_view_state(catalog.uuid)
        self._manual_widths = dict(state.column_widths)
        header = self._event_table.horizontalHeader()
        header.blockSignals(True)
        try:
            for col in range(self._event_model.columnCount()):
                key = self._column_key(col)
                self._event_table.setColumnHidden(col, key in state.hidden_columns)
            self._reorder_columns(state.column_order)
        finally:
            header.blockSignals(False)
        self._fit_event_columns()

    def _save_view_state(self) -> None:
        if self._current_catalog is None:
            return
        from ..backend.event_table_view_state import CatalogViewState, save_view_state
        hidden = [
            self._column_key(col)
            for col in range(self._event_model.columnCount())
            if self._event_table.isColumnHidden(col)
        ]
        header = self._event_table.horizontalHeader()
        order = [
            self._column_key(header.logicalIndex(visual))
            for visual in range(self._event_model.columnCount())
        ]
        save_view_state(self._current_catalog.uuid,
                        CatalogViewState(hidden_columns=hidden, column_order=order,
                                         column_widths=dict(self._manual_widths)))

    def _reorder_columns(self, desired_order: list) -> None:
        if not desired_order:
            return
        header = self._event_table.horizontalHeader()
        keys_to_logical = {
            self._column_key(col): col for col in range(self._event_model.columnCount())
        }
        target_visual = 0
        for key in desired_order:
            logical = keys_to_logical.get(key)
            if logical is None:
                continue
            current_visual = header.visualIndex(logical)
            if current_visual != target_visual:
                header.moveSection(current_visual, target_visual)
            target_visual += 1

    def _build_column_entries(self):
        from .column_visibility_popover import ColumnEntry
        header = self._event_table.horizontalHeader()
        order = [header.logicalIndex(visual)
                 for visual in range(self._event_model.columnCount())]
        fixed_count = len(self._event_model._FIXED_COLUMNS)
        entries = []
        for logical in order:
            key = self._column_key(logical)
            entries.append(ColumnEntry(
                key=key,
                label=key,
                visible=not self._event_table.isColumnHidden(logical),
                frozen=logical < fixed_count,
            ))
        return entries

    def _open_column_popover(self, at_header_pos=None) -> None:
        if self._event_model.columnCount() == 0:
            return
        from .column_visibility_popover import ColumnVisibilityPopover
        popover = ColumnVisibilityPopover(self._build_column_entries(), self)
        popover.visibility_changed.connect(self._on_column_visibility_changed)
        popover.reorder_requested.connect(self._on_column_reorder_requested)
        popover.reset_requested.connect(self._on_columns_reset)
        popover.reset_requested.connect(popover.close)
        if at_header_pos is None:
            anchor = self._event_toolbar.widgetForAction(self._columns_action)
            global_pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        else:
            global_pos = self._event_table.horizontalHeader().mapToGlobal(at_header_pos)
        popover.move(global_pos)
        popover.resize(Metrics.em(28), Metrics.ex(30))
        popover.show()
        popover.setFocus()

    def _on_column_visibility_changed(self, key: str, visible: bool) -> None:
        for col in range(self._event_model.columnCount()):
            if self._column_key(col) == key:
                self._event_table.setColumnHidden(col, not visible)
                break
        self._save_view_state()

    def _on_column_reorder_requested(self, new_order: list) -> None:
        self._reorder_columns(new_order)
        self._save_view_state()

    def _on_columns_reset(self) -> None:
        from ..backend.event_table_view_state import CatalogViewState, save_view_state
        if self._current_catalog is None:
            return
        save_view_state(self._current_catalog.uuid, CatalogViewState())
        self._manual_widths = {}
        for col in range(self._event_model.columnCount()):
            self._event_table.setColumnHidden(col, False)
        self._reorder_columns(
            [self._column_key(col) for col in range(self._event_model.columnCount())])
        self._fit_event_columns()

    def _update_toolbar(self) -> None:
        if self._current_provider is None:
            self._add_event_action.setVisible(False)
            self._delete_action.setVisible(False)
            self._columns_action.setVisible(False)
            self._add_attr_action.setVisible(False)
            return
        self._columns_action.setVisible(self._event_model.columnCount() > 0)
        if self._current_catalog is None:
            # These are catalog-scoped operations. Without a target catalog
            # (e.g. a provider/folder node is selected) they'd stay visible
            # yet inert -- including in the table's right-click menu, which
            # would offer Delete/+Attribute over an empty table.
            self._add_event_action.setVisible(False)
            self._delete_action.setVisible(False)
            self._add_attr_action.setVisible(False)
            return

        caps = self._current_provider.capabilities(self._current_catalog)
        self._add_event_action.setVisible(Capability.CREATE_EVENTS in caps)
        self._delete_action.setVisible(Capability.DELETE_EVENTS in caps)
        self._add_attr_action.setVisible(Capability.EDIT_EVENTS in caps)

    def highlight_event(self, event, catalog=None) -> None:
        """Reveal *event* in the event table, opening *catalog* first when
        another one is shown. Selection made here does not re-emit
        event_selected: the plot is the source, echoing back would jump."""
        if catalog is not None and (self._current_catalog is None
                                    or self._current_catalog.uuid != catalog.uuid):
            self._open_catalog_in_tree(catalog)
        row = self._event_model.row_for_event(event)
        if row < 0:
            return
        proxy_index = self._sort_proxy.mapFromSource(self._event_model.index(row, 0))
        self._highlighting = True
        try:
            self._event_table.selectionModel().setCurrentIndex(
                proxy_index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
            )
            self._event_table.scrollTo(proxy_index)
        finally:
            self._highlighting = False

    def _open_catalog_in_tree(self, catalog) -> None:
        node = self._tree_model._find_node_by_uuid(self._tree_model._root, catalog.uuid)
        if node is None:
            return
        proxy_index = self._proxy_model.mapFromSource(self._tree_model.createIndex(node.row(), 0, node))
        if proxy_index.isValid():
            self._catalog_tree.scrollTo(proxy_index)
            self._catalog_tree.setCurrentIndex(proxy_index)

    def _on_plot_event_clicked(self, catalog, event) -> None:
        self.highlight_event(event, catalog)

    def connect_to_panel(self, panel) -> None:
        """Wire bidirectional event selection between this browser and a panel."""
        if panel in self._panels:
            return
        self._panels.append(panel)
        manager = panel.catalog_manager
        self.event_selected.connect(manager.select_event)
        manager.catalog_event_clicked.connect(self._on_plot_event_clicked)
        panel.destroyed.connect(lambda: self._on_panel_destroyed(panel))

    def _on_panel_destroyed(self, panel) -> None:
        if panel in self._panels:
            self._panels.remove(panel)

    def disconnect_from_panel(self, panel) -> None:
        """Remove bidirectional event selection wiring for a panel."""
        if panel not in self._panels:
            return
        self._panels.remove(panel)
        manager = panel.catalog_manager
        try:
            self.event_selected.disconnect(manager.select_event)
        except RuntimeError:
            pass
        try:
            manager.catalog_event_clicked.disconnect(self._on_plot_event_clicked)
        except RuntimeError:
            pass

    def _focused_panel(self):
        """The connected panel currently focused/on top among several open
        ones, or None if none of self._panels is focused. Used to place a
        new event where the user is actually looking, not wherever the
        first-ever-connected panel happens to be."""
        import shiboken6
        from SciQLop.core.sciqlop_application import sciqlop_app
        win = getattr(sciqlop_app(), "main_window", None)
        if win is None or not shiboken6.isValid(win):
            return None
        dock_manager = getattr(win, "dock_manager", None)
        if dock_manager is None:
            return None
        focused_dock = dock_manager.focusedDockWidget()
        if focused_dock is None:
            return None
        from SciQLop.core.ui.mainwindow import _extract_panel
        focused_panel = _extract_panel(focused_dock)
        return focused_panel if focused_panel in self._panels else None

    def _working_panel(self):
        """The connected panel the user is working in: the focused one, else
        the first connected one."""
        return self._focused_panel() or (self._panels[0] if self._panels else None)

    def _on_add_event(self) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        caps = self._current_provider.capabilities(self._current_catalog)
        if Capability.CREATE_EVENTS not in caps:
            return
        target_panel = self._working_panel()
        if target_panel is not None:
            tr = target_panel.time_range
            center = (tr.start() + tr.stop()) / 2.0
            half_span = (tr.stop() - tr.start()) * 0.05  # 10% of visible range
            start = datetime.fromtimestamp(center - half_span, tz=timezone.utc)
            stop = datetime.fromtimestamp(center + half_span, tz=timezone.utc)
        else:
            now = datetime.now(tz=timezone.utc)
            start = now - timedelta(minutes=30)
            stop = now + timedelta(minutes=30)
        event = CatalogEvent(
            uuid=str(_uuid.uuid4()),
            start=start,
            stop=stop,
        )
        try:
            # add_event() synchronously emits events_changed (provider.py's
            # _emit_events_changed), which the connected _on_events_changed
            # turns into the refresh -- no separate explicit read here, that
            # would just do the same model reset a second time.
            self._current_provider.add_event(self._current_catalog, event)
        except Exception as e:
            self._report_failure("Could not add event", e)

    def _on_delete(self) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        caps = self._current_provider.capabilities(self._current_catalog)
        if Capability.DELETE_EVENTS not in caps:
            return
        sm = self._event_table.selectionModel()
        if sm is None:
            return
        events = []
        for proxy_idx in sm.selectedRows():
            source_idx = self._sort_proxy.mapToSource(proxy_idx)
            ev = self._event_model.event_at(source_idx.row())
            if ev is not None:
                events.append(ev)
        if not events:
            return
        if len(events) > 1:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Delete events",
                f"Delete {len(events)} selected events?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        try:
            # batch_events_update coalesces remove_event's per-call
            # events_changed into a single emission on exit, so a bulk
            # delete refreshes the table once, not once per event; the
            # connected _on_events_changed does that refresh -- no separate
            # explicit read/reset here.
            with self._current_provider.batch_events_update(self._current_catalog):
                for ev in events:
                    self._current_provider.remove_event(self._current_catalog, ev)
        except Exception as e:
            self._report_failure("Could not delete event", e)

    def _url_at(self, proxy_index) -> str | None:
        """The cell's display text, if it looks like a clickable URL."""
        if not proxy_index.isValid():
            return None
        text = self._sort_proxy.data(proxy_index, Qt.ItemDataRole.DisplayRole)
        if isinstance(text, str) and text.strip().startswith(("http://", "https://")):
            return text.strip()
        return None

    def _build_event_context_menu(self, url: str | None = None) -> QMenu:
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        if url is not None:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            open_action = menu.addAction("Open link")
            open_action.setToolTip(rich_tooltip(
                "Open link",
                "Open the URL stored in this cell."))
            open_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
            menu.addSeparator()
        if self._delete_action.isVisible():
            menu.addAction(self._delete_action)
        if self._add_attr_action.isVisible():
            menu.addAction(self._add_attr_action)
        if self._current_catalog is not None:
            if not menu.isEmpty():
                menu.addSeparator()
            self._build_color_by_menu(menu, self._current_catalog)
        return menu

    def _on_event_table_context_menu(self, pos) -> None:
        url = self._url_at(self._event_table.indexAt(pos))
        menu = self._build_event_context_menu(url)
        if menu.isEmpty():
            return
        menu.exec(self._event_table.viewport().mapToGlobal(pos))

    def _on_add_attribute_clicked(self) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        from .add_attribute_dialog import run_add_attribute_dialog
        spec = run_add_attribute_dialog(self)
        if spec is None:
            return
        self._current_provider.set_attribute_spec(self._current_catalog, spec.name, spec)
        self._add_attribute_to_selection(spec.name, spec.default)

    def _add_attribute_to_selection(self, key: str, value) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        sm = self._event_table.selectionModel()
        events = []
        if sm is not None:
            for proxy_idx in sm.selectedRows():
                source_idx = self._sort_proxy.mapToSource(proxy_idx)
                ev = self._event_model.event_at(source_idx.row())
                if ev is not None:
                    events.append(ev)
        if not events:
            events = list(self._current_provider.events(self._current_catalog))
        if not events:
            return
        self._current_provider.set_events_meta(
            self._current_catalog, events, key, value,
        )

    def _on_save_clicked(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(proxy_index)
        node = self._tree_model.node_from_index(source_index)
        if node.provider is not None:
            try:
                node.provider.save()
            except Exception as e:
                self._report_failure(f"Could not save '{node.provider.name}'", e)

    def _folder_path(self, node) -> list[str]:
        return self._tree_model._folder_path(node)

    def _trigger_placeholder_edit(self, placeholder_node) -> None:
        """Clear filter and trigger inline edit on a placeholder node."""
        self._filter_bar.clear()
        source_index = self._tree_model.createIndex(placeholder_node.row(), 0, placeholder_node)
        proxy_index = self._proxy_model.mapFromSource(source_index)
        if proxy_index.isValid():
            self._catalog_tree.expand(proxy_index.parent())
            self._catalog_tree.edit(proxy_index)

    def _on_tree_context_menu(self, pos) -> None:
        proxy_index = self._catalog_tree.indexAt(pos)
        menu = self._build_tree_context_menu(proxy_index)
        if menu is None or menu.isEmpty():
            return
        menu.exec(self._catalog_tree.viewport().mapToGlobal(pos))

    def _build_tree_context_menu(self, proxy_index) -> QMenu | None:
        if not proxy_index.isValid():
            return None
        source_index = self._proxy_model.mapToSource(proxy_index)
        node = self._tree_model.node_from_index(source_index)
        if node.provider is None:
            return None

        # `caps` is the provider-level set, used for folder/provider-node
        # decisions. For per-catalog decisions (Save Catalog, Delete Catalog,
        # rename, …) use `node_caps`, which lets a provider opt out of those
        # for synthetic rows like the tscat orphan-events virtual catalog.
        caps = node.provider.capabilities()
        node_caps = node.provider.capabilities(node.catalog) if node.catalog is not None else caps
        menu = QMenu(self)
        menu.setToolTipsVisible(True)

        # Provider-level actions (provider node = parent is root)
        if node.parent is self._tree_model._root:
            for action in node.provider.actions(None) or ():
                a = menu.addAction(action.name)
                if action.icon is not None:
                    a.setIcon(action.icon)
                a.triggered.connect(lambda checked, cb=action.callback: cb(None))

        # Catalog-scoped actions (own place for a provider to expose
        # per-catalog custom operations; the tree is the single surface for
        # every provider action, provider- or catalog-level)
        if node.catalog is not None:
            for action in node.provider.actions(node.catalog) or ():
                a = menu.addAction(action.name)
                if action.icon is not None:
                    a.setIcon(action.icon)
                a.triggered.connect(lambda checked, cb=action.callback, c=node.catalog: cb(c))

        # Explicit folder actions (room nodes)
        if node.is_explicit_folder:
            path = self._folder_path(node)
            for action in node.provider.folder_actions(path):
                a = menu.addAction(action.name)
                if action.icon is not None:
                    a.setIcon(action.icon)
                a.triggered.connect(lambda checked, cb=action.callback, p=path: cb(p))

        # Creation actions (folder or provider node, gated on CREATE_CATALOGS)
        if node.catalog is None and not node.is_placeholder:
            if Capability.CREATE_CATALOGS in caps:
                from .catalog_tree import _PlaceholderType
                cat_ph = next((c for c in node.children if c.placeholder_type == _PlaceholderType.CATALOG), None)
                folder_ph = next((c for c in node.children if c.placeholder_type == _PlaceholderType.FOLDER), None)
                if cat_ph is not None:
                    new_cat_action = menu.addAction("New catalog…")
                    new_cat_action.setToolTip(rich_tooltip(
                        "New catalog…",
                        "Create an empty catalog in this library."))
                    new_cat_action.triggered.connect(lambda checked, ph=cat_ph: self._trigger_placeholder_edit(ph))
                if folder_ph is not None:
                    new_folder_action = menu.addAction("New folder…")
                    new_folder_action.setToolTip(rich_tooltip(
                        "New folder…",
                        "Create an empty folder in this library."))
                    new_folder_action.triggered.connect(lambda checked, ph=folder_ph: self._trigger_placeholder_edit(ph))

        if Capability.SAVE in caps and node.provider.is_dirty():
            if (node.catalog is not None
                    and Capability.SAVE_CATALOG in node_caps
                    and node.provider.is_dirty(node.catalog)):
                save_action = menu.addAction("Save catalog")
                save_action.setToolTip(rich_tooltip(
                    "Save catalog",
                    "Write the catalog to disk."))
                save_action.triggered.connect(lambda: node.provider.save_catalog(node.catalog))
            else:
                save_action = menu.addAction("Save")
                save_action.triggered.connect(lambda: node.provider.save())

        if node.catalog is not None and Capability.RENAME_CATALOG in node_caps:
            rename_action = menu.addAction("Rename…")
            rename_action.setToolTip(rich_tooltip(
                "Rename…",
                "Rename this catalog."))
            rename_action.triggered.connect(lambda: self._catalog_tree.edit(proxy_index))

        if node.catalog is not None and Capability.DELETE_CATALOGS in node_caps:
            delete_action = menu.addAction("Delete catalog…")
            delete_action.setToolTip(rich_tooltip(
                "Delete catalog…",
                "Delete this catalog and all its events."))
            delete_action.triggered.connect(lambda: self._delete_catalog(node))

        if node.catalog is not None:
            self._add_panel_toggle_action(menu, node.catalog)
            self._add_catalog_color_actions(menu, node.catalog)
            self._build_color_by_menu(menu, node.catalog)

        return menu

    def _add_panel_toggle_action(self, menu: QMenu, catalog: Catalog) -> None:
        panel = self._working_panel()
        if panel is None:
            return
        manager = panel.catalog_manager
        title = panel.windowTitle()
        if catalog.uuid in manager.catalog_uuids:
            action = menu.addAction(f"Remove from panel '{title}'")
            action.setToolTip(rich_tooltip(
                f"Remove from panel '{title}'",
                "Stop showing this catalog's events on the panel."))
            action.triggered.connect(lambda: manager.remove_catalog(catalog))
        else:
            action = menu.addAction(f"Add to panel '{title}'")
            action.setToolTip(rich_tooltip(
                f"Add to panel '{title}'",
                "Overlay this catalog's events on the panel."))
            action.triggered.connect(lambda: manager.add_catalog(catalog))

    def _add_catalog_color_actions(self, menu: QMenu, catalog: Catalog) -> None:
        from .color_menus import add_catalog_color_actions
        add_catalog_color_actions(menu, catalog, dialog_parent=self)

    def _pick_catalog_color(self, catalog: Catalog) -> None:
        from .color_menus import pick_catalog_color
        pick_catalog_color(catalog, dialog_parent=self)

    def _build_color_by_menu(self, parent_menu: QMenu, catalog: Catalog) -> QMenu:
        from .color_menus import build_color_by_menu
        return build_color_by_menu(parent_menu, catalog, self._events_for_color_menu(catalog), dialog_parent=self)

    def _events_for_color_menu(self, catalog: Catalog) -> list:
        """The open catalog's events are already in memory; any other
        right-clicked catalog needs a real (sampled) backend call."""
        from .color_menus import sample_events
        if self._current_catalog is not None and catalog.uuid == self._current_catalog.uuid:
            return list(self._event_model._events)
        return sample_events(catalog, self._report_failure)

    def _apply_color_mapper(self, catalog: Catalog, mapper) -> None:
        from SciQLop.components.catalogs.backend.color_mapper_storage import set_color_mapper
        set_color_mapper(catalog, mapper)

    def _on_delete_selected_catalog(self) -> None:
        index = self._catalog_tree.currentIndex()
        if not index.isValid():
            return
        node = self._tree_model.node_from_index(self._proxy_model.mapToSource(index))
        if node.catalog is None or node.provider is None:
            return
        if Capability.DELETE_CATALOGS not in node.provider.capabilities(node.catalog):
            return
        self._delete_catalog(node)

    def _delete_catalog(self, node) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Delete catalog",
            f"Delete catalog '{node.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._current_catalog is not None and self._current_catalog.uuid == node.catalog.uuid:
                self._current_catalog = None
                self._event_model.clear()
                self._update_toolbar()
            node.provider.remove_catalog(node.catalog)

