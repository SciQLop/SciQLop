from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets

ITEM_HEIGHT = 36
PADDING = 8


class PaletteItemDelegate(QtWidgets.QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QtCore.QSize(option.rect.width(), ITEM_HEIGHT)

    def paint(self, painter: QtGui.QPainter, option, index):
        painter.save()
        self.initStyleOption(option, index)
        is_selected = option.state & QtWidgets.QStyle.StateFlag.State_Selected
        bg = option.palette.highlight() if is_selected else option.palette.base()
        painter.fillRect(option.rect, bg)
        data = index.data(QtCore.Qt.ItemDataRole.UserRole) or {}
        name = index.data(QtCore.Qt.ItemDataRole.DisplayRole) or ""
        description = data.get("description", "")
        match_positions = set(data.get("match_positions", []))
        category = data.get("category", "")
        text_color = option.palette.highlightedText() if is_selected else option.palette.text()
        dim_color = option.palette.placeholderText()
        icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        x = option.rect.left() + PADDING
        y = option.rect.top()
        h = option.rect.height()
        if icon and not icon.isNull():
            icon_size = h - 2 * PADDING
            icon.paint(painter, x, y + PADDING, icon_size, icon_size)
            x += icon_size + PADDING
        font = painter.font()
        bold_font = QtGui.QFont(font)
        bold_font.setBold(True)
        fm = QtGui.QFontMetrics(font)
        for i, ch in enumerate(name):
            if i in match_positions:
                painter.setFont(bold_font)
                painter.setPen(text_color.color())
            else:
                painter.setFont(font)
                painter.setPen(text_color.color())
            painter.drawText(x, y, 500, h, QtCore.Qt.AlignmentFlag.AlignVCenter, ch)
            x += QtGui.QFontMetrics(painter.font()).horizontalAdvance(ch)
        if category:
            painter.setFont(font)
            painter.setPen(dim_color.color())
            cat_rect = QtCore.QRect(
                option.rect.right() - fm.horizontalAdvance(category) - 2 * PADDING,
                y, fm.horizontalAdvance(category) + 2 * PADDING, h,
            )
            painter.drawText(cat_rect, QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight, category)
        if description:
            painter.setFont(font)
            painter.setPen(dim_color.color())
            desc_x = x + PADDING
            desc_rect = QtCore.QRect(desc_x, y, option.rect.right() - desc_x - (fm.horizontalAdvance(category) + 3 * PADDING if category else PADDING), h)
            elided = fm.elidedText(description, QtCore.Qt.TextElideMode.ElideRight, desc_rect.width())
            painter.drawText(desc_rect, QtCore.Qt.AlignmentFlag.AlignVCenter, elided)
        painter.restore()
