from PySide6.QtWidgets import QLayout, QLayoutItem, QStyle, QSizePolicy, QApplication
from PySide6.QtCore import QRect, QSize, QPoint, Qt
from typing import List, Optional


class FlowLayout(QLayout):

    def __init__(self, parent=None, margin=0, hspacing=-1, vspacing=-1):
        super().__init__(parent)
        self._item_list: List[QLayoutItem] = []
        self._margin = margin
        self._hspacing = hspacing
        self._vspacing = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item: QLayoutItem):
        self._item_list.append(item)

    def horizontal_spacing(self) -> int:
        if self._hspacing >= 0:
            return self._hspacing
        else:
            return self.smartSpacing(QStyle.PM_LayoutHorizontalSpacing)

    def vertical_spacing(self) -> int:
        if self._vspacing >= 0:
            return self._vspacing
        else:
            return self.smartSpacing(QStyle.PM_LayoutVerticalSpacing)

    def count(self) -> int:
        return len(self._item_list)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        else:
            return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        else:
            return None

    def expandingDirections(self) -> int:
        return Qt.Orientations(Qt.Orientation.Vertical)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self._margin, 2 * self._margin)
        return size

    def doLayout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0

        for item in self._item_list:
            wid = item.widget()
            space_x = self.horizontal_spacing()
            if space_x == -1:
                space_x = wid.style().layoutSpacing(QSizePolicy.PushButton,
                                                    QSizePolicy.PushButton,
                                                    Qt.Horizontal)
            space_y = self.vertical_spacing()
            if space_y == -1:
                space_y = wid.style().layoutSpacing(QSizePolicy.PushButton,
                                                    QSizePolicy.PushButton,
                                                    Qt.Vertical)
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()

    def smartSpacing(self, pm: QStyle.PixelMetric) -> int:
        parent = self.parent()
        if parent is None:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()

    def clear(self):
        for item in self._item_list:
            item.widget().deleteLater()
        self._item_list.clear()
