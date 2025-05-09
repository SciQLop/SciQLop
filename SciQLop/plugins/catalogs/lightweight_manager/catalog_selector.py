from typing import Mapping, Union, List, Any, Optional

from PySide6.QtCore import Signal, QModelIndex, QSize, QPersistentModelIndex, QAbstractItemModel, Slot, \
    QAbstractProxyModel, QSortFilterProxyModel, QIdentityProxyModel
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel, QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QTreeView, QAbstractScrollArea, QSizePolicy, QPushButton, QHeaderView, \
    QStyledItemDelegate, QWidget, QStyleOptionViewItem, QAbstractItemView, QStyle, QColorDialog

from SciQLop.backend.common.ExtraColumnsProxyModel import ExtraColumnsProxyModel
from SciQLop.backend import sciqlop_logging

from tscat_gui.tscat_driver.model import tscat_model
from tscat_gui.model_base.constants import EntityRole, UUIDDataRole
from tscat_gui.tscat_driver.actions import SetAttributeAction

log = sciqlop_logging.getLogger(__name__)

__DEFAULT_COLOR__ = QColor(100, 100, 100, 50)


# stolen from https://qtadventures.wordpress.com/2012/02/04/adding-button-to-qviewtable/
class ButtonDelegate(QStyledItemDelegate):
    create_event = Signal(str)
    change_color = Signal(QColor, str)

    def __init__(self, item_view: QAbstractItemView, *args, update_button=None, **kwargs):
        QStyledItemDelegate.__init__(self, item_view, *args, **kwargs)
        self._btn = QPushButton(item_view)
        self._btn.hide()
        self._btn.pressed.connect(self._handle_btn_pressed)
        item_view.setMouseTracking(True)
        item_view.entered.connect(self.cellEntered)
        self._edit_mode = False
        self._currentEditedCellIndex = QPersistentModelIndex()
        if update_button is None:
            self._update_button = lambda index, btn: btn.setText(str(index.data()))
        else:
            self._update_button = update_button

    @Slot()
    def _handle_btn_pressed(self):
        uuid = self._currentEditedCellIndex.data(UUIDDataRole)
        checked = Qt.CheckState(
            self._currentEditedCellIndex.sibling(self._currentEditedCellIndex.row(), 0).data(Qt.CheckStateRole))
        if checked == Qt.CheckState.Checked and uuid is not None:
            self.create_event.emit(uuid)

    @staticmethod
    def _is_column(index: Union[QModelIndex, QPersistentModelIndex], col_number: int):
        return index.column() == col_number

    def checked(self, index: Union[QModelIndex, QPersistentModelIndex]):
        return Qt.CheckState(index.sibling(index.row(), 0).data(Qt.CheckStateRole)) == Qt.CheckState.Checked

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: Union[QModelIndex, QPersistentModelIndex]) -> QWidget:
        uuid = index.data(UUIDDataRole)
        if self._is_column(index, 1):
            if uuid is not None and self.checked(index):
                btn = QPushButton(parent)
                btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                self._update_button(index, btn)
                btn.pressed.connect(self._handle_btn_pressed)
                return btn
            return None
        elif self._is_column(index, 2):
            if uuid is not None:
                d = QColorDialog(index.data(Qt.ItemDataRole.BackgroundRole))
                d.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
                return d
            else:
                return None
        else:
            return QStyledItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor: QWidget, index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1):
            btn: QPushButton = editor
        elif self._is_column(index, 2):
            dial: QColorDialog = editor
        else:
            QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel,
                     index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1):
            btn: QPushButton = editor
        elif self._is_column(index, 2):
            dial: QColorDialog = editor
            model.setData(index, editor.currentColor(), Qt.ItemDataRole.BackgroundRole)
            self.change_color.emit(editor.currentColor(), index.sibling(index.row(), 0).data(UUIDDataRole))
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1) and index.data(Qt.DisplayRole) == "Add event":
            if self.checked(index):
                self._btn.setEnabled(True)
            else:
                self._btn.setEnabled(False)
            self._btn.setGeometry(option.rect)
            self._update_button(index, self._btn)
            if option.state & QStyle.StateFlag.State_Selected == QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())
            px = self._btn.grab()
            painter.drawPixmap(option.rect.x(), option.rect.y(), px)
        elif self._is_column(index, 2):
            color = index.data(Qt.ItemDataRole.BackgroundRole)
            if color is not None:
                painter.save()
                painter.fillRect(option.rect, QBrush(color))
                painter.setPen(QPen(option.palette.mid().color(), 2))
                painter.drawRect(option.rect)
                painter.restore()
        else:
            QStyledItemDelegate.paint(self, painter, option, index)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem,
                             index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        editor.setGeometry(option.rect)

    @Slot()
    def cellEntered(self, index: QModelIndex):
        if self._is_column(index, 1) and index.data(Qt.DisplayRole) == "Add event" and self.checked(index):
            if self._edit_mode:
                self.parent().closePersistentEditor(self._currentEditedCellIndex)
            self.parent().openPersistentEditor(index)
            self._edit_mode = True
            self._currentEditedCellIndex = QPersistentModelIndex(index)
        else:
            if self._edit_mode:
                self.parent().closePersistentEditor(self._currentEditedCellIndex)


class TrashAlwaysTopOrBottomSortFilterModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRecursiveFilteringEnabled(True)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def lessThan(self, source_left: Union[QModelIndex, QPersistentModelIndex],
                 source_right: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        left = self.sourceModel().data(source_left)
        right = self.sourceModel().data(source_right)
        if left == 'Trash':
            return False
        elif right == 'Trash':
            return True
        else:
            return left.lower() < right.lower()


class CatalogsModelWithExtraColumns(ExtraColumnsProxyModel):

    def __init__(self, source_model, parent=None):
        super().__init__(parent=parent, columns=["Add event", "Color"], first_column_item_checkable=True)
        self.setSourceModel(source_model)

    def extra_column_flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def extra_column_data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if index.isValid():
            source_item = self.mapToSource(self.sibling(index.row(), 0, index))
            if source_item is not None:
                source_catalog = source_item.data(EntityRole)
                if source_catalog is not None:
                    if index.column() == 1 and role == Qt.DisplayRole:
                        return "Add event"
                    elif index.column() == 2 and role == Qt.DisplayRole:
                        if 'color' not in source_catalog.variable_attributes():
                            source_catalog.color = __DEFAULT_COLOR__.name(QColor.NameFormat.HexArgb)
                    elif index.column() == 2 and role == Qt.BackgroundRole:
                        return QColor.fromString(source_catalog.color)
                    elif role == UUIDDataRole:
                        return source_catalog.uuid
                    elif role == EntityRole:
                        return source_catalog

    def set_extra_column_data(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if index.isValid():
            source_item = self.mapToSource(self.sibling(index.row(), 0, index))
            if source_item is not None:
                if index.column() == 2:
                    source_catalog = source_item.data(UUIDDataRole)
                    if source_catalog is not None:
                        tscat_model.do(
                            SetAttributeAction(user_callback=None, uuids=[source_catalog], name="color",
                                               values=[value.name(QColor.NameFormat.HexArgb)]))

    def set_extra_column_flags(self, index: QModelIndex, flags: Qt.ItemFlag) -> bool:
        return False


class CatalogSelector(QTreeView):
    catalog_selection_changed = Signal(list)
    create_event = Signal(str)
    change_color = Signal(QColor, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = tscat_model.tscat_root()
        self._model = CatalogsModelWithExtraColumns(self._root, self)
        self._sort_model = TrashAlwaysTopOrBottomSortFilterModel(self)
        self._sort_model.setSourceModel(self._model)
        self._selected_catalogs = []
        self.setModel(self._sort_model)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.setHeaderHidden(True)
        self.setWordWrap(False)
        self.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        self._createEventBtnDelegate = ButtonDelegate(self)
        self.setItemDelegate(self._createEventBtnDelegate)
        self._createEventBtnDelegate.create_event.connect(self.create_event)
        self._createEventBtnDelegate.change_color.connect(self.change_color)

        self.model().dataChanged.connect(self._resize_columns)
        self._model.checkStateChanged.connect(self._check_state_changed)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def _resize_columns(self):
        for i in range(3):
            self.resizeColumnToContents(i)

    @Slot()
    def _check_state_changed(self, index: QModelIndex, state: Qt.CheckState):
        log.debug(f"Check state changed {index.data(UUIDDataRole)} {state}")
        if Qt.CheckState(state) == Qt.CheckState.Checked:
            self._selected_catalogs.append(index.data(UUIDDataRole))
        else:
            self._selected_catalogs.remove(index.data(UUIDDataRole))
        self.catalog_selection_changed.emit(self._selected_catalogs)

    def color(self, uuid: str) -> QColor:
        c = tscat_model.tscat_root().index_from_uuid(uuid).data(EntityRole)
        if 'color' not in c.variable_attributes():
            return __DEFAULT_COLOR__
        return QColor.fromString(c.color)

    def catalogs(self) -> List[str]:
        catalogs = []
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            catalog = index.data(EntityRole)
            if catalog is not None:
                catalogs.append(catalog.name)
        return catalogs

    def catalog_uuid(self, catalog: str) -> Optional[str]:
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            _catalog = index.data(EntityRole)
            if _catalog is not None and _catalog.name == catalog:
                return _catalog.uuid
        return None
