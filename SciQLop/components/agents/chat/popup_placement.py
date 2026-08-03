"""Where to put a popup anchored to a widget.

`QWidget.move()` alone drops a popup wherever it is told, so one anchored to a
widget sitting low on the screen — the chat input strip when the window is
maximised — opens downward and is cropped by the screen edge. Qt only does this
flipping for menus and combo popups, not for plain `Qt.Popup` widgets.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtWidgets import QWidget


def popup_origin(anchor: QRect, size: QSize, screen: QRect) -> QPoint:
    """Top-left for a `size` popup under `anchor`, all in global coordinates.

    Prefers below the anchor, flips above when that would overflow `screen`,
    and clamps when the popup is simply taller or wider than the screen.
    """
    below = anchor.bottom() + 1
    above = anchor.top() - size.height()
    y = below if below + size.height() <= screen.bottom() else above
    return QPoint(
        _clamp(anchor.left(), screen.left(), screen.right() - size.width()),
        _clamp(y, screen.top(), screen.bottom() - size.height()),
    )


def _clamp(value: int, low: int, high: int) -> int:
    return min(max(value, low), max(low, high))


def place_popup(popup: QWidget, anchor: QWidget) -> None:
    """Move `popup` next to `anchor`, keeping it within the anchor's screen."""
    popup.adjustSize()
    anchor_rect = QRect(anchor.mapToGlobal(QPoint(0, 0)), anchor.size())
    screen = anchor.screen().availableGeometry()
    popup.move(popup_origin(anchor_rect, popup.size(), screen))
    popup.show()
