from typing import Mapping, Union, List

import tscat
from PySide6.QtCore import Signal, QModelIndex, QSize, QPersistentModelIndex, QAbstractItemModel, Slot
from PySide6.QtGui import Qt, QStandardItem, QStandardItemModel, QPainter, QColor
from PySide6.QtWidgets import QTableView, QAbstractScrollArea, QSizePolicy, QPushButton, QHeaderView, \
    QStyledItemDelegate, QWidget, QStyleOptionViewItem, QAbstractItemView, QStyle, QColorDialog


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
        self.create_event.emit(self._currentEditedCellIndex.data(Qt.ItemDataRole.UserRole))

    @staticmethod
    def _is_column(index: Union[QModelIndex, QPersistentModelIndex], col_number: int):
        return index.column() == col_number

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem,
                     index: Union[QModelIndex, QPersistentModelIndex]) -> QWidget:
        if self._is_column(index, 1):
            btn = QPushButton(parent)
            self._update_button(index, btn)
            btn.pressed.connect(self._handle_btn_pressed)
            return btn
        elif self._is_column(index, 2):
            d = QColorDialog(index.data(Qt.ItemDataRole.BackgroundRole))
            d.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
            return d
        else:
            return QStyledItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor: QWidget, index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1):
            btn: QPushButton = editor
            btn.setProperty("data_value", index.data())
        elif self._is_column(index, 2):
            dial: QColorDialog = editor
        else:
            QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor: QWidget, model: QAbstractItemModel,
                     index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1):
            btn: QPushButton = editor
            model.setData(index, btn.property("data_value"))
        elif self._is_column(index, 2):
            dial: QColorDialog = editor
            model.setData(index, editor.currentColor(), Qt.ItemDataRole.BackgroundRole)
            self.change_color.emit(editor.currentColor(), model.data(index, Qt.ItemDataRole.UserRole))
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: Union[QModelIndex, QPersistentModelIndex]) -> None:
        if self._is_column(index, 1):
            self._btn.setGeometry(option.rect)
            self._update_button(index, self._btn)
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


class CatalogColorItem(QStandardItem):
    _tscat_obj: tscat._Catalogue

    def __init__(self, catalog: tscat._Catalogue):
        QStandardItem.__init__(self)
        self.tscat_instance = catalog

    def setData(self, value, role=Qt.ItemDataRole.UserRole + 1) -> None:
        QStandardItem.setData(self, value, role)
        if role == Qt.ItemDataRole.BackgroundRole:
            self.tscat_instance.color = value.name(QColor.NameFormat.HexArgb)

    @property
    def tscat_instance(self):
        return self._tscat_obj

    @tscat_instance.setter
    def tscat_instance(self, tscat_obj):
        self._tscat_obj = tscat_obj
        self.setData(tscat_obj.uuid, Qt.UserRole)
        if 'color' not in tscat_obj.variable_attributes():
            tscat_obj.color = QColor(100, 100, 100, 50).name(QColor.NameFormat.HexArgb)
        self.setData(QColor.fromString(tscat_obj.color), Qt.ItemDataRole.BackgroundRole)


class CatalogItem(QStandardItem):
    _tscat_obj: tscat._Catalogue
    _events: List[tscat._Event]

    def __init__(self, catalog: tscat._Catalogue):
        QStandardItem.__init__(self)
        self._add_event = CreateEventItem()
        self._color_item = CatalogColorItem(catalog)
        self.tscat_instance = catalog
        self.setCheckable(True)
        self.setCheckState(Qt.Unchecked)

    def setData(self, value, role=Qt.ItemDataRole.UserRole + 1) -> None:
        QStandardItem.setData(self, value, role)
        if self.text() != self.tscat_instance.name:
            self.tscat_instance.name = self.text()

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
        self._color_item.tscat_instance = tscat_obj

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

    @property
    def color_item(self):
        return self._color_item

    @property
    def color(self) -> QColor:
        return self._color_item.data(Qt.ItemDataRole.BackgroundRole)

    def __str__(self):
        return self.name


class CatalogSelector(QTableView):
    catalog_selected = Signal(list)
    create_event = Signal(str)
    change_color = Signal(QColor, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = QStandardItemModel()
        self.catalogs: Mapping[str, CatalogItem] = {}
        self._selected_catalogs = []
        self.setModel(self.model)
        self.update_list()
        self.clicked.connect(self._catalog_selected)
        self.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        # self.setShowGrid(False)
        self.horizontalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().hide()
        self._createEventBtnDelegate = ButtonDelegate(self)
        self.setItemDelegate(self._createEventBtnDelegate)
        self._createEventBtnDelegate.create_event.connect(self.create_event)
        self._createEventBtnDelegate.change_color.connect(self.change_color)

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
        self.model.clear()
        self.catalogs = {c.uuid: CatalogItem(c) for c in tscat.get_catalogues()}
        selected_catalogs = []
        for index, catalog in enumerate(self.catalogs.values()):
            if any(filter(lambda c: c.uuid == catalog.uuid, self._selected_catalogs)):
                catalog.setCheckState(Qt.CheckState.Checked)
                selected_catalogs.append(catalog)
            self.model.setItem(index, 0, catalog)
            self.model.setItem(index, 1, catalog.create_event_item)
            self.model.setItem(index, 2, catalog.color_item)
        self._selected_catalogs = selected_catalogs
        self.catalog_selected.emit(self._selected_catalogs)

    def color(self, catalog_uid):
        return self.catalogs[catalog_uid].color
