from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Signal, QRect, QEvent, QItemSelectionModel, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QPen, QColor, QShortcut

import math
from datetime import datetime, timezone, timedelta
import uuid as _uuid
from SciQLop.core.ui import Metrics
from ..backend.provider import Capability, CatalogProvider, Catalog, CatalogEvent
from .catalog_tree import CatalogTreeModel, DIRTY_PROVIDER_ROLE, LOADING_ROLE
from .event_table import EventTableModel, EventSortProxy


class _CatalogFilterProxy(QSortFilterProxyModel):
    """Case-insensitive substring filter that keeps ancestors of matching nodes."""

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True
        idx = self.sourceModel().index(source_row, 0, source_parent)
        name = self.sourceModel().data(idx, Qt.ItemDataRole.DisplayRole) or ""
        if pattern.lower() in name.lower():
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
            self._icon = QIcon.fromTheme("document-save")
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

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Catalog Browser")

        self._current_provider: CatalogProvider | None = None
        self._events_changed_provider: CatalogProvider | None = None
        self._current_catalog: Catalog | None = None
        self._panels: list = []

        # --- filter bar ---
        self._filter_bar = QLineEdit()
        self._filter_bar.setPlaceholderText("Filter catalogs...")

        # --- tree view (left) ---
        self._tree_model = CatalogTreeModel()
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
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(
            lambda pos: self._open_column_popover(at_header_pos=pos)
        )
        self._event_model.modelReset.connect(self._fit_event_columns)
        self._event_table.selectionModel().currentChanged.connect(self._on_event_selected)
        self._event_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._event_table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)

        self._propagating_bulk_edit = False
        self._event_model.dataChanged.connect(self._on_event_data_changed)

        from .event_table_delegate import EventTableDelegate
        self._event_delegate = EventTableDelegate(self._event_model, self._event_table)
        self._event_table.setItemDelegate(self._event_delegate)

        # --- event toolbar (above table) ---
        self._add_event_btn = QPushButton("Add Event")
        self._add_event_btn.setVisible(False)
        self._add_event_btn.clicked.connect(self._on_add_event)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(self._on_delete)

        self._columns_btn = QToolButton()
        self._columns_btn.setText("Columns")
        self._columns_btn.setToolTip("Show / hide / reorder columns")
        self._columns_btn.setAutoRaise(True)
        self._columns_btn.clicked.connect(lambda: self._open_column_popover())

        self._add_attr_btn = QToolButton()
        self._add_attr_btn.setText("+ Attribute")
        self._add_attr_btn.setToolTip("Add a new metadata attribute to the selected events (or all events if no selection)")
        self._add_attr_btn.setAutoRaise(True)
        self._add_attr_btn.clicked.connect(self._on_add_attribute_clicked)

        event_toolbar = QHBoxLayout()
        event_toolbar.addWidget(self._add_event_btn)
        event_toolbar.addWidget(self._delete_btn)
        event_toolbar.addWidget(self._columns_btn)
        event_toolbar.addWidget(self._add_attr_btn)
        event_toolbar.addStretch()

        event_panel = QWidget()
        event_layout = QVBoxLayout(event_panel)
        event_layout.setContentsMargins(0, 0, 0, 0)
        event_layout.addLayout(event_toolbar)
        event_layout.addWidget(self._event_table, 1)

        # --- splitter ---
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._catalog_tree)
        self._splitter.addWidget(event_panel)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)

        # --- actions toolbar (bottom) ---
        self._actions_btn = QToolButton()
        self._actions_btn.setText("Actions")
        self._actions_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._actions_menu = QMenu(self._actions_btn)
        self._actions_btn.setMenu(self._actions_menu)
        self._actions_btn.setVisible(False)

        actions_toolbar = QHBoxLayout()
        actions_toolbar.addStretch()
        actions_toolbar.addWidget(self._actions_btn)

        # --- layout ---
        layout = QVBoxLayout(self)
        layout.addWidget(self._filter_bar)
        layout.addWidget(self._splitter, 1)
        layout.addLayout(actions_toolbar)

    # ---- slots ----

    def _on_filter_changed(self, text: str) -> None:
        self._proxy_model.setFilterFixedString(text)
        if text:
            self._catalog_tree.expandAll()

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

    def _on_events_changed(self, catalog: Catalog) -> None:
        """Refresh event table when async loading completes for the selected catalog."""
        if self._current_catalog is not None and catalog.uuid == self._current_catalog.uuid:
            events = self._current_provider.events(self._current_catalog)
            self._event_model.set_events(events)

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
        for col in range(cols):
            header_text = model.headerData(col, Qt.Orientation.Horizontal) or ""
            width = header_fm.horizontalAdvance(str(header_text))
            for row in range(sample):
                text = model.data(model.index(row, col), Qt.ItemDataRole.DisplayRole) or ""
                w = cell_fm.horizontalAdvance(str(text))
                if w > width:
                    width = w
            width = min(width + self._COLUMN_FIT_PADDING_PX, self._COLUMN_FIT_MAX_WIDTH)
            header.resizeSection(col, width)

    def _column_key(self, col: int) -> str:
        if col < len(self._event_model._FIXED_COLUMNS):
            return self._event_model._FIXED_COLUMNS[col]
        return self._event_model._meta_keys[col - len(self._event_model._FIXED_COLUMNS)]

    def _apply_view_state(self, catalog) -> None:
        from ..backend.event_table_view_state import get_view_state
        state = get_view_state(catalog.uuid)
        header = self._event_table.horizontalHeader()
        header.blockSignals(True)
        try:
            for col in range(self._event_model.columnCount()):
                key = self._column_key(col)
                self._event_table.setColumnHidden(col, key in state.hidden_columns)
            self._reorder_columns(state.column_order)
        finally:
            header.blockSignals(False)

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
                        CatalogViewState(hidden_columns=hidden, column_order=order))

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
        if at_header_pos is None:
            anchor = self._columns_btn
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
        for col in range(self._event_model.columnCount()):
            self._event_table.setColumnHidden(col, False)

    def _update_toolbar(self) -> None:
        if self._current_provider is None:
            self._add_event_btn.setVisible(False)
            self._delete_btn.setVisible(False)
            self._columns_btn.setVisible(False)
            self._add_attr_btn.setVisible(False)
            self._actions_btn.setVisible(False)
            return

        caps = self._current_provider.capabilities(self._current_catalog)
        self._add_event_btn.setVisible(Capability.CREATE_EVENTS in caps)
        self._columns_btn.setVisible(self._event_model.columnCount() > 0)
        self._delete_btn.setVisible(Capability.DELETE_EVENTS in caps)
        self._add_attr_btn.setVisible(Capability.EDIT_EVENTS in caps)

        # Populate custom actions menu
        self._actions_menu.clear()
        actions = self._current_provider.actions(self._current_catalog)
        self._actions_btn.setVisible(len(actions) > 0)
        for action in actions:
            menu_action = self._actions_menu.addAction(action.name)
            if action.icon is not None:
                menu_action.setIcon(action.icon)
            cat = self._current_catalog
            menu_action.triggered.connect(lambda checked, cb=action.callback, c=cat: cb(c))

    def highlight_event(self, event) -> None:
        """Select the row in the event table matching the given event."""
        row = self._event_model.row_for_event(event)
        if row >= 0:
            source_index = self._event_model.index(row, 0)
            proxy_index = self._sort_proxy.mapFromSource(source_index)
            self._event_table.selectionModel().setCurrentIndex(
                proxy_index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
            )

    def connect_to_panel(self, panel) -> None:
        """Wire bidirectional event selection between this browser and a panel."""
        if panel in self._panels:
            return
        self._panels.append(panel)
        manager = panel.catalog_manager
        self.event_selected.connect(manager.select_event)
        manager.event_clicked.connect(self.highlight_event)
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
            manager.event_clicked.disconnect(self.highlight_event)
        except RuntimeError:
            pass

    def _on_add_event(self) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        caps = self._current_provider.capabilities(self._current_catalog)
        if Capability.CREATE_EVENTS not in caps:
            return
        # Use the first connected panel's visible range to place the new event
        if self._panels:
            tr = self._panels[0].time_range
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
        self._current_provider.add_event(self._current_catalog, event)
        # Refresh event table
        events = self._current_provider.events(self._current_catalog)
        self._event_model.set_events(events)

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
        for ev in events:
            self._current_provider.remove_event(self._current_catalog, ev)
        events_after = self._current_provider.events(self._current_catalog)
        self._event_model.set_events(events_after)

    def _on_add_attribute_clicked(self) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add attribute", "Attribute name:")
        if not ok or not name:
            return
        self._add_attribute_to_selection(name, "")

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
            node.provider.save()

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
        if not proxy_index.isValid():
            return
        source_index = self._proxy_model.mapToSource(proxy_index)
        node = self._tree_model.node_from_index(source_index)
        if node.provider is None:
            return

        caps = node.provider.capabilities()
        menu = QMenu(self)

        # Provider-level actions (provider node = parent is root)
        if node.parent is self._tree_model._root:
            for action in node.provider.actions(None):
                a = menu.addAction(action.name)
                if action.icon is not None:
                    a.setIcon(action.icon)
                a.triggered.connect(lambda checked, cb=action.callback: cb(None))

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
                    new_cat_action = menu.addAction("New Catalog")
                    new_cat_action.triggered.connect(lambda checked, ph=cat_ph: self._trigger_placeholder_edit(ph))
                if folder_ph is not None:
                    new_folder_action = menu.addAction("New Folder")
                    new_folder_action.triggered.connect(lambda checked, ph=folder_ph: self._trigger_placeholder_edit(ph))

        if Capability.SAVE in caps and node.provider.is_dirty():
            if (node.catalog is not None
                    and Capability.SAVE_CATALOG in caps
                    and node.provider.is_dirty(node.catalog)):
                save_action = menu.addAction("Save Catalog")
                save_action.triggered.connect(lambda: node.provider.save_catalog(node.catalog))
            else:
                save_action = menu.addAction("Save")
                save_action.triggered.connect(lambda: node.provider.save())

        if node.catalog is not None and Capability.DELETE_CATALOGS in caps:
            delete_action = menu.addAction("Delete Catalog")
            delete_action.triggered.connect(lambda: self._delete_catalog(node))

        if node.catalog is not None:
            self._build_color_by_menu(menu, node.catalog)

        if menu.isEmpty():
            return
        menu.exec(self._catalog_tree.viewport().mapToGlobal(pos))

    def _build_color_by_menu(self, parent_menu: QMenu, catalog: Catalog) -> None:
        from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
        from SciQLop.components.catalogs.backend.color_mapper_storage import (
            get_color_mapper, set_color_mapper,
        )

        current = get_color_mapper(catalog)
        color_menu = parent_menu.addMenu("Color by...")

        uniform_action = color_menu.addAction("Uniform (default)")
        uniform_action.setCheckable(True)
        uniform_action.setChecked(current.column is None)
        uniform_action.triggered.connect(
            lambda: self._apply_color_mapper(catalog, ColorMapper())
        )

        events = catalog.provider.events(catalog)
        columns: set[str] = set()
        for event in events[:200]:
            columns.update(event.meta.keys())

        if columns:
            color_menu.addSeparator()
            for col in sorted(columns):
                action = color_menu.addAction(col)
                action.setCheckable(True)
                action.setChecked(current.column == col)
                action.triggered.connect(
                    lambda checked, c=col: self._apply_color_mapper(
                        catalog, ColorMapper(column=c)
                    )
                )

        # Configure colormap... (only meaningful when a column is selected)
        if current.column is not None:
            color_menu.addSeparator()
            configure_action = color_menu.addAction("Configure colormap...")
            configure_action.triggered.connect(
                lambda: self._show_colormap_dialog(catalog, current)
            )

    def _show_colormap_dialog(self, catalog: Catalog, current_mapper) -> None:
        from .colormap_dialog import ColormapDialog
        from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
        dialog = ColormapDialog(
            current_colormap=current_mapper.colormap,
            current_vmin=current_mapper.vmin,
            current_vmax=current_mapper.vmax,
            parent=self,
        )
        if dialog.exec() == ColormapDialog.DialogCode.Accepted:
            mapper = ColorMapper(
                column=current_mapper.column,
                colormap=dialog.colormap,
                vmin=dialog.vmin,
                vmax=dialog.vmax,
            )
            self._apply_color_mapper(catalog, mapper)

    def _apply_color_mapper(self, catalog: Catalog, mapper) -> None:
        from SciQLop.components.catalogs.backend.color_mapper_storage import set_color_mapper
        set_color_mapper(catalog, mapper)
        for panel in self._panels:
            overlay = panel.catalog_manager.overlay(catalog.uuid)
            if overlay is not None:
                overlay.update_color_mapper(mapper)

    def _on_delete_selected_catalog(self) -> None:
        index = self._catalog_tree.currentIndex()
        if not index.isValid():
            return
        node = self._tree_model.node_from_index(self._proxy_model.mapToSource(index))
        if node.catalog is None or node.provider is None:
            return
        if Capability.DELETE_CATALOGS not in node.provider.capabilities():
            return
        self._delete_catalog(node)

    def _delete_catalog(self, node) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Delete Catalog",
            f"Delete catalog '{node.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self._current_catalog is not None and self._current_catalog.uuid == node.catalog.uuid:
                self._current_catalog = None
                self._event_model.clear()
                self._update_toolbar()
            node.provider.remove_catalog(node.catalog)

