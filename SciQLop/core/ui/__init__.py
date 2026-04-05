from PySide6.QtWidgets import QFrame, QWidget, QSizePolicy, QLabel, QVBoxLayout, QApplication, QComboBox
from PySide6.QtCore import QSize
from PySide6.QtGui import QFontMetrics

from .tree_view import TreeView


class Metrics:
    """DPI-aware sizing helpers based on the application font.

    All values scale with font size, DPI, and platform defaults.
    Use this instead of hardcoded pixel values for widget sizing.

    Usage::

        from SciQLop.core.ui import Metrics

        widget.setMinimumWidth(Metrics.em(30))
        widget.setFixedSize(Metrics.size(20, 15))
        layout.setContentsMargins(*Metrics.margins(1.5, 1, 1.5, 1))
        layout.setSpacing(Metrics.spacing())
    """

    _FALLBACK_EM = 10

    @staticmethod
    def _fm() -> QFontMetrics | None:
        app = QApplication.instance()
        if app is None:
            return None
        return app.fontMetrics()

    @staticmethod
    def _em_px() -> float:
        fm = Metrics._fm()
        return fm.horizontalAdvance('m') if fm else Metrics._FALLBACK_EM

    @staticmethod
    def _ex_px() -> float:
        fm = Metrics._fm()
        return fm.height() if fm else Metrics._FALLBACK_EM

    @staticmethod
    def em(n: float = 1) -> int:
        """Return *n* em-widths (width of 'm') in pixels."""
        return round(Metrics._em_px() * n)

    @staticmethod
    def ex(n: float = 1) -> int:
        """Return *n* ex-heights (font height) in pixels."""
        return round(Metrics._ex_px() * n)

    @staticmethod
    def size(w_em: float, h_em: float) -> QSize:
        """Return a QSize of *w_em* x *h_em* in em units."""
        return QSize(Metrics.em(w_em), Metrics.em(h_em))

    @staticmethod
    def margins(left: float = 1, top: float = 1,
                right: float = 1, bottom: float = 1) -> tuple[int, int, int, int]:
        """Return (left, top, right, bottom) margins in em units."""
        e = Metrics.em()
        return round(left * e), round(top * e), round(right * e), round(bottom * e)

    @staticmethod
    def spacing(n: float = 0.5) -> int:
        """Return a spacing value of *n* em."""
        return Metrics.em(n)

    @staticmethod
    def icon_size(n: float = 2) -> QSize:
        """Return a square icon size of *n* em."""
        px = Metrics.em(n)
        return QSize(px, px)


class HLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        #self.setStyleSheet("background-color: #ccc;")


class Container(QFrame):
    def __init__(self, label: str, widget: QWidget):
        super().__init__()
        #self.setStyleSheet("Container { border: 1px solid black; border-radius: 2px; }")
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.addWidget(QLabel(label))
        self._layout.addWidget(widget)


def apply_size_policy(widget: QWidget, horizontal: QSizePolicy.Policy, vertical: QSizePolicy.Policy) -> QWidget:
    widget.setSizePolicy(horizontal, vertical)
    return widget


def expand_size(size: QSize, horizontal: int, vertical: int) -> QSize:
    return QSize(size.width() + (2 * horizontal), size.height() + (2 * vertical))


def fit_combo_to_content(combo: QComboBox) -> None:
    """Set minimum width so the widest item text is fully visible.

    On macOS the popup matches the widget width, so making the widget
    wide enough prevents item text from being clipped.
    """
    fm = combo.fontMetrics()
    widest = max((fm.horizontalAdvance(combo.itemText(i))
                  for i in range(combo.count())), default=0)
    # account for icon, dropdown arrow, and frame margins
    padding = combo.iconSize().width() + Metrics.em(3)
    combo.setMinimumWidth(widest + padding)


def increase_font_size(label: QLabel, factor: float = 1.2) -> QLabel:
    font = label.font()
    font.setPointSizeF(font.pointSizeF() * factor)
    label.setFont(font)
    return label
