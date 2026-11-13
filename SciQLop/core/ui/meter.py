from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QProgressBar


class Meter(QProgressBar):
    """A progress bar whose text stays readable: one colour on the filled part, another on the rest.

    A style sheet gives the text a single colour, which cannot contrast both the fill and the trough."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)  # the style draws the bar, paintEvent the text

    def _longest_text(self) -> str:
        fmt = self.format()
        for token, value in (("%v", str(self.maximum())), ("%m", str(self.maximum())), ("%p", "100")):
            fmt = fmt.replace(token, value)
        return fmt

    def _wide_enough(self, hint: QSize) -> QSize:
        """With its text hidden from the style, the bar would only ask for the room of an empty one."""
        metrics = self.fontMetrics()
        text_width = metrics.horizontalAdvance(self._longest_text()) + 2 * metrics.averageCharWidth()
        return QSize(max(hint.width(), text_width), hint.height())

    def sizeHint(self) -> QSize:
        return self._wide_enough(super().sizeHint())

    def minimumSizeHint(self) -> QSize:
        return self._wide_enough(super().minimumSizeHint())

    def _filled_width(self) -> int:
        span = self.maximum() - self.minimum()
        return round(self.width() * (self.value() - self.minimum()) / span) if span > 0 else 0

    def paintEvent(self, event):
        super().paintEvent(event)
        painter, filled = QPainter(self), self._filled_width()
        parts = ((QRect(0, 0, filled, self.height()), QPalette.ColorRole.HighlightedText),
                 (QRect(filled, 0, self.width() - filled, self.height()), QPalette.ColorRole.Text))
        for clip, role in parts:
            painter.setClipRect(clip)
            painter.setPen(self.palette().color(role))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
