import shiboken6
from PySide6.QtCore import Qt, QRect, QSize, QPoint, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from SciQLop.core.ui import Metrics, increase_font_size

_CUTOUT_PADDING = 4
_BUBBLE_GAP = 12
_DIM_COLOR = QColor(0, 0, 0, 140)


def _has_keyboard_focus(widget: QWidget | None) -> bool:
    # window().focusWidget() also holds while the window isn't active,
    # unlike hasFocus(); the card must not take a text field's focus away
    # from a user who was asked to type in it.
    return widget is not None and widget.window().focusWidget() is widget


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def _bubble_position(target: QRect, bubble: QSize, window: QRect) -> QPoint:
    """Beside the target when there is room (right, left, above, below),
    otherwise inside its own top-left corner; never outside the window."""
    max_x = window.width() - bubble.width()
    max_y = window.height() - bubble.height()
    y_beside = _clamp(target.top(), 0, max_y)
    x_stacked = _clamp(target.left(), 0, max_x)
    candidates = [
        QPoint(target.right() + _BUBBLE_GAP, y_beside),
        QPoint(target.left() - _BUBBLE_GAP - bubble.width(), y_beside),
        QPoint(x_stacked, target.top() - _BUBBLE_GAP - bubble.height()),
        QPoint(x_stacked, target.bottom() + _BUBBLE_GAP),
    ]
    for position in candidates:
        if window.contains(QRect(position, bubble)):
            return position
    return QPoint(x_stacked, y_beside)


class TourBubble(QWidget):
    """The tour's card: progress, title, body and Skip / Back / Next.

    A sibling of the overlay rather than its child: the overlay is
    transparent to mouse input, and a child would inherit that."""

    next_clicked = Signal()
    back_clicked = Signal()
    skip_clicked = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("CoachMarkBubble")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # A QWidget subclass paints its style-sheet background only with
        # this attribute set. The rule is scoped to the object name: an
        # unscoped rule cascades to every plain-QWidget child. tooltip-base
        # stands out from the palette(window) chrome, in both themes.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#CoachMarkBubble { background-color: palette(tooltip-base); "
            "border: 2px solid palette(highlight); border-radius: 6px; }")
        self.setFixedWidth(Metrics.em(28))

        self._progress_label = QLabel(self)
        self._progress_label.setStyleSheet("color: palette(placeholder-text);")
        self._title_label = QLabel(self)
        self._title_label.setStyleSheet("font-weight: bold;")
        increase_font_size(self._title_label, 1.15)
        self._body_label = QLabel(self)
        self._body_label.setWordWrap(True)
        increase_font_size(self._body_label, 1.1)

        self._skip_button = QPushButton("Skip tour", self)
        self._skip_button.setFlat(True)
        self._skip_button.clicked.connect(self.skip_clicked)
        self._back_button = QPushButton("Back", self)
        self._back_button.setFlat(True)
        self._back_button.clicked.connect(self.back_clicked)
        self._next_button = QPushButton("Next", self)
        self._next_button.setObjectName("CoachMarkNextButton")
        self._next_button.setStyleSheet(
            "#CoachMarkNextButton { background-color: palette(highlight); "
            "color: palette(highlighted-text); font-weight: bold; border: none; "
            f"border-radius: 4px; padding: {Metrics.ex(0.4)}px {Metrics.em(1.2)}px; }}")
        self._next_button.clicked.connect(self.next_clicked)

        header = QHBoxLayout()
        header.addWidget(self._title_label)
        header.addStretch(1)
        header.addWidget(self._progress_label)
        buttons = QHBoxLayout()
        buttons.addWidget(self._skip_button)
        buttons.addStretch(1)
        buttons.addWidget(self._back_button)
        buttons.addWidget(self._next_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Metrics.margins(1, 1, 1, 1))
        layout.setSpacing(Metrics.spacing())
        layout.addLayout(header)
        layout.addWidget(self._body_label)
        layout.addLayout(buttons)

    def set_content(self, title: str, body: str, *, progress: str = "",
                    can_go_back: bool = False, next_label: str = "Next") -> None:
        self._title_label.setText(title)
        self._body_label.setText(body)
        self._progress_label.setText(progress)
        self._back_button.setVisible(can_go_back)
        self._next_button.setText(next_label)
        self._fit_height()

    def _fit_height(self) -> None:
        # sizeHint() sizes a wrapped label for its unconstrained width, so
        # ask for the height at the width the card actually has, and keep
        # one descent of slack: at fractional DPI scales an exact fit
        # crops descenders. heightForWidth() clamps to the label's current
        # minimumHeight, hence the reset before measuring.
        margins = self.layout().contentsMargins()
        body_width = self.width() - margins.left() - margins.right()
        self._body_label.setMinimumHeight(0)
        needed = (self._body_label.heightForWidth(body_width)
                  + self._body_label.fontMetrics().descent())
        self._body_label.setMinimumHeight(needed)
        self.resize(self.width(), self.layout().heightForWidth(self.width()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.skip_clicked.emit()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.next_clicked.emit()
        else:
            super().keyPressEvent(event)


class CoachMark(QWidget):
    """Dims the main window except a spotlight around the current target,
    with a TourBubble beside it. The overlay is transparent to mouse input
    everywhere: the dimming guides the eye but never blocks a click or a
    drag, so every tip can be acted on while it is displayed."""

    skip_requested = Signal()
    next_clicked = Signal()
    back_clicked = Signal()
    target_hidden = Signal(object)

    def __init__(self, main_window: QWidget):
        super().__init__(main_window)
        self._main_window = main_window
        self._target: QWidget | None = None
        self._target_local_rect: QRect | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._bubble = TourBubble(main_window)
        self._bubble.next_clicked.connect(self.next_clicked)
        self._bubble.back_clicked.connect(self.back_clicked)
        self._bubble.skip_clicked.connect(self.skip_requested)
        main_window.installEventFilter(self)
        self.hide()

    @property
    def bubble(self) -> TourBubble:
        return self._bubble

    @property
    def target(self) -> QWidget | None:
        return self._target

    def show_step(self, target: QWidget | None, title: str, body: str, *,
                  rect: QRect | None = None, progress: str = "",
                  can_go_back: bool = False, next_label: str = "Next") -> None:
        self._attach_target(target, rect)
        self._bubble.set_content(title, body, progress=progress,
                                 can_go_back=can_go_back, next_label=next_label)
        self.setGeometry(self._main_window.rect())
        self._reposition_bubble()
        self.show()
        self.raise_()
        self._bubble.raise_()
        if not _has_keyboard_focus(target):
            self._bubble.setFocus()
        self.update()

    def setVisible(self, visible: bool) -> None:
        self._bubble.setVisible(visible)
        super().setVisible(visible)

    def dispose(self) -> None:
        """Detach from the target and the main window; the owning
        controller calls this exactly once when the tour is over."""
        self._detach_target()
        if shiboken6.isValid(self._main_window):
            self._main_window.removeEventFilter(self)
        self.hide()
        self._bubble.deleteLater()

    def _attach_target(self, target: QWidget | None, rect: QRect | None) -> None:
        self._detach_target()
        self._target = target
        self._target_local_rect = rect
        if target is not None:
            target.installEventFilter(self)
            target.destroyed.connect(self._on_target_destroyed)

    def _detach_target(self) -> None:
        if self._target is None or not shiboken6.isValid(self._target):
            return
        self._target.removeEventFilter(self)
        try:
            self._target.destroyed.disconnect(self._on_target_destroyed)
        except RuntimeError:
            pass

    def _on_target_destroyed(self, *_):
        # A step's own action can destroy its target (picking a product
        # deletes the search box it pointed at): keep the tip, drop the
        # spotlight. This runs from the target's destructor, so nothing
        # beyond a repaint request is done here.
        self._target = None
        self._target_local_rect = None
        self.update()

    def eventFilter(self, obj, event):
        if obj is self._main_window and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self.setGeometry(self._main_window.rect())
            self._reposition_bubble()
        elif obj is self._target and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._reposition_bubble()
        elif obj is self._target and event.type() == QEvent.Type.Hide:
            self.target_hidden.emit(obj)
        return False

    def _target_rect(self) -> QRect | None:
        if self._target is None:
            return None
        local_rect = self._target_local_rect or self._target.rect()
        top_left = self._target.mapTo(self._main_window, local_rect.topLeft())
        return QRect(top_left, local_rect.size())

    def _cutout_rect(self) -> QRect | None:
        rect = self._target_rect()
        if rect is None:
            return None
        return rect.adjusted(-_CUTOUT_PADDING, -_CUTOUT_PADDING, _CUTOUT_PADDING, _CUTOUT_PADDING)

    def _reposition_bubble(self) -> None:
        target = self._target_rect()
        if target is None:
            self._bubble.move((self.width() - self._bubble.width()) // 2,
                              (self.height() - self._bubble.height()) // 2)
        else:
            self._bubble.move(_bubble_position(target, self._bubble.size(), self.rect()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cutout = self._cutout_rect()
        dimmed = QPainterPath()
        dimmed.addRect(self.rect())
        if cutout is not None:
            hole = QPainterPath()
            hole.addRoundedRect(cutout, 6, 6)
            dimmed = dimmed.subtracted(hole)
        painter.fillPath(dimmed, _DIM_COLOR)
        if cutout is not None:
            painter.setPen(QPen(self.palette().highlight().color(), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(cutout.adjusted(-1, -1, 1, 1), 7, 7)
