from typing import Mapping, Union, List

import tscat
from PySide6.QtCore import Signal, QModelIndex, QSize, QPersistentModelIndex, QAbstractItemModel, Slot
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel, QPainter
from PySide6.QtWidgets import QTableView, QAbstractScrollArea, QSizePolicy, QPushButton, QHeaderView, \
    QStyledItemDelegate, QWidget, QStyleOptionViewItem, QAbstractItemView, QStyle


# stolen from https://qtadventures.wordpress.com/2012/02/04/adding-button-to-qviewtable/
class ButtonDelegate(QStyledItemDelegate):
    create_event = Signal(str)

    def __init__(self, item_view: QAbstractItemView, *args, **kwargs):
        QStyledItemDelegate.__init__(self, item_view, *args, **kwargs)
        self._btn = QPushButton(item_view)
        self._btn.hide()
        self._btn.pressed.connect(self._handle_btn_pressed)
        item_view.setMouseTracking(True)
        item_view.entered.connect(self.cellEntered)
        self._edit_mode = False
        self._currentEditedCellIndex = QPersistentModelIndex()

    @Slot()
    def _handle_btn_pressed(self):
        self.create_event.emit(self._currentEditedCellIndex.data(Qt.ItemDataRole.UserRole))

    @staticmethod
    def _is_column(index: Union[QModelIndex, QPersistentModelIndex], col_number: int):
        return index.column() == col_number

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: Union[QModelIndex, QPersistentModelIndex]) -> QWidget:
        if self._is_column(index, 1):
            btn = QPushButton(parent)
            btn.setText(str(index.data()))
            btn.pressed.connect(self._handle_btn_pressed)
            return btn
        else:
            return QStyledItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor: QWidget, index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1):
            btn: QPushButton = editor
            btn.setProperty("data_value", index.data())
        else:
            QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel,
                     index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1):
            btn: QPushButton = editor
            model.setData(index, btn.property("data_value"))
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1):
            self._btn.setGeometry(option.rect)
            self._btn.setText(str(index.data()))
            if option.state == QStyle.StateFlag.State_Selected:
                painter.fillRect(option.rect, option.palette.hignlight)
            px = self._btn.grab()
            painter.drawPixmap(option.rect.x(), option.rect.y(), px)
        else:
            QStyledItemDelegate.paint(self, painter, option, index)

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem,
                             index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        editor.setGeometry(option.rect)

    @Slot()
    def cellEntered(self, index: QModelIndex):
        if self._is_column(index, 1):
            if self._edit_mode:
                self.parent().closePersistentEditor(self._currentEditedCellIndex)
            self.parent().openPersistentEditor(index)
            self._edit_mode = True
            self._currentEditedCellIndex = QPersistentModelIndex(index)
        else:
            if self._edit_mode:
                self.parent().closePersistentEditor(self._currentEditedCellIndex)


class CreateEventItem(QStandardItem):
    def __init__(self, *args, **kwargs):
        QStandardItem.__init__(self, *args, **kwargs)
        self.setText("Add event")


class CatalogItem(QStandardItem):
    _tscat_obj: tscat._Catalogue
    _events: List[tscat._Event]

    def __init__(self, catalog: tscat._Catalogue):
        QStandardItem.__init__(self)
        self._add_event = CreateEventItem()
        self.tscat_instance = catalog
        self.setCheckable(True)
        self.setCheckState(Qt.Unchecked)

    @property
    def tscat_instance(self):
        return self._tscat_obj

    @tscat_instance.setter
    def tscat_instance(self, tscat_obj):
        self._tscat_obj = tscat_obj
        self._events = tscat.get_events(tscat_obj)
        self.setText(tscat_obj.name)
        self.setData(tscat_obj.uuid, Qt.UserRole)
        self._add_event.setData(tscat_obj.uuid, Qt.UserRole)

    @property
    def uuid(self):
        return self._tscat_obj.uuid

    @property
    def name(self):
        return self._tscat_obj.name

    @property
    def events(self):
        return self._events

    @property
    def create_event_item(self):
        return self._add_event

    def __str__(self):
        return self.name


class CatalogSelector(QTableView):
    catalog_selected = Signal(list)
    create_event = Signal(str)
    catalogs: Mapping[str, CatalogItem] = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStandardItemModel()
        self.setModel(self.model)
        self.update_list()
        self.clicked.connect(self._catalog_selected)
        self._selected_catalogs = []
        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.setShowGrid(False)
        self.horizontalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().hide()
        self._btnDelegate = ButtonDelegate(self)
        self.setItemDelegate(self._btnDelegate)
        self._btnDelegate.create_event.connect(self.create_event)

    def minimumSizeHint(self):
        return QSize(0, 0)

    def _catalog_selected(self, index: QModelIndex):
        item = self.model.itemFromIndex(index)
        if item.column() == 0:
            selected_catalog = self.catalogs[item.data(Qt.UserRole)]
            if selected_catalog:
                if item.checkState() == Qt.CheckState.Checked:
                    if selected_catalog not in self._selected_catalogs:
                        self._selected_catalogs.append(selected_catalog)
                        self.catalog_selected.emit(self._selected_catalogs)
                else:
                    if selected_catalog in self._selected_catalogs:
                        self._selected_catalogs.remove(selected_catalog)
                        self.catalog_selected.emit(self._selected_catalogs)

    def reload_catalog(self, catalog_uuid):
        c = tscat.get_catalogues(tscat.filtering.UUID(catalog_uuid))[0]
        self.catalogs[catalog_uuid].tscat_instance = c
        print("reload !")
        if self.catalogs[catalog_uuid] in self._selected_catalogs:
            print("Update !")
            self.catalog_selected.emit(self._selected_catalogs)

    def update_list(self):
        self.catalogs = {c.uuid: CatalogItem(c) for c in tscat.get_catalogues()}
        self.model.clear()
        for index, catalog in enumerate(self.catalogs.values()):
            self.model.setItem(index, 0, catalog)
            self.model.setItem(index, 1, catalog.create_event_item)
            # self.setIndexWidget(self.model.index(index, 1), catalog.create_event_item.button)
