import shiboken6
from PySide6.QtCore import Qt, QRect, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QPainterPath, QRegion, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from SciQLop.core.ui import Metrics, increase_font_size


class CoachMark(QWidget):
    """Dims the main window except a spotlight cutout around a target
    widget, with an info bubble (title/body/dismiss/skip) beside it."""

    skip_requested = Signal()
    dismiss_clicked = Signal()
    target_destroyed = Signal()

    def __init__(self, main_window: QWidget):
        super().__init__(main_window)
        self._main_window = main_window
        self._target: QWidget | None = None
        self._target_local_rect: QRect | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._bubble = QWidget(self)
        layout = QVBoxLayout(self._bubble)
        layout.setContentsMargins(*Metrics.margins(1, 1, 1, 1))
        layout.setSpacing(Metrics.spacing())
        self._title_label = QLabel(self._bubble)
        self._title_label.setStyleSheet("font-weight: bold;")
        increase_font_size(self._title_label, 1.15)
        self._body_label = QLabel(self._bubble)
        self._body_label.setWordWrap(True)
        increase_font_size(self._body_label, 1.1)
        buttons = QHBoxLayout()
        self._skip_link = QPushButton("Skip tour", self._bubble)
        self._skip_link.setFlat(True)
        self._skip_link.clicked.connect(self.skip_requested)
        self._dismiss_button = QPushButton("Got it / Next", self._bubble)
        self._dismiss_button.clicked.connect(self.dismiss_clicked)
        buttons.addWidget(self._skip_link)
        buttons.addStretch(1)
        buttons.addWidget(self._dismiss_button)
        layout.addWidget(self._title_label)
        layout.addWidget(self._body_label)
        layout.addLayout(buttons)
        # The bubble's own background (palette(window)) can be close in
        # tone to whatever sits behind or beside it, and the dimmed
        # overlay's highlight ring is drawn around the TARGET's cutout,
        # not the bubble -- an explicit border gives the bubble its own
        # boundary. Scoped to "#CoachMarkBubble" (its object name), not a
        # bare property list: an unscoped rule is an implicit universal
        # selector in Qt's style-sheet cascade, so it paints the same box
        # around every plain-QWidget child too (title, body, buttons) --
        # confirmed by rendering to a QImage before adding the selector.
        # palette(highlight) (the same accent the target's spotlight ring
        # uses) reads reliably in both themes; palette(mid) was too close
        # to the background to actually stand out.
        self._bubble.setObjectName("CoachMarkBubble")
        self._bubble.setStyleSheet(
            "#CoachMarkBubble { background-color: palette(window); "
            "border: 2px solid palette(highlight); border-radius: 6px; }")
        # Metrics.em() DPI/font-scales this width -- a hardcoded pixel
        # value here would stay a fixed size while the rest of the app's
        # text scales with the system font/DPI, making the bubble (and
        # its wrapped text) look disproportionately cramped on a scaled
        # display. em(28) matches the previous 280px in the fallback case.
        self._bubble.setFixedWidth(Metrics.em(28))

        main_window.installEventFilter(self)
        self.hide()

    def show_for(self, target: QWidget, title: str, body: str, *,
                 rect: QRect | None = None, show_dismiss: bool = True,
                 block_input: bool = True) -> None:
        self._detach_target()
        self._target = target
        self._target_local_rect = rect
        target.installEventFilter(self)
        target.destroyed.connect(self._on_target_destroyed)
        self._title_label.setText(title)
        self._body_label.setText(body)
        self._dismiss_button.setVisible(show_dismiss)
        # A step whose completion needs a cross-widget drag (pick up the
        # spotlighted target, drop it elsewhere) can't be satisfied by the
        # cutout alone -- the drop point stays covered by this overlay
        # otherwise. WA_TransparentForMouseEvents also affects this widget's
        # children (the info bubble), so a step opting out of blocking loses
        # its mouse-clickable Skip/Got it buttons for as long as it's shown;
        # Escape still works (keyPressEvent isn't mouse input).
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not block_input)
        self.setGeometry(self._main_window.rect())
        self._reposition_bubble()
        self.show()
        self.raise_()
        self.setFocus()

    def dispose(self) -> None:
        """Detach from both the current target and `main_window` itself.

        Called exactly once, by TourController._finish(), when the owning
        tour is truly done. CoachMark has no notion of "the tour is over"
        on its own, so it must not remove its own main_window event filter
        anywhere else (e.g. its destructor) — only the controller knows
        when that's safe."""
        self._detach_target()
        if shiboken6.isValid(self._main_window):
            self._main_window.removeEventFilter(self)
        self.hide()

    def _detach_target(self) -> None:
        if self._target is None or not shiboken6.isValid(self._target):
            return
        self._target.removeEventFilter(self)
        try:
            self._target.destroyed.disconnect(self._on_target_destroyed)
        except RuntimeError:
            pass

    def _on_target_destroyed(self, *_):
        self._target = None
        self.hide()
        self.target_destroyed.emit()

    def eventFilter(self, obj, event):
        if obj is self._main_window and event.type() in (
                QEvent.Type.Resize, QEvent.Type.Move):
            self.setGeometry(self._main_window.rect())
            self._reposition_bubble()
        elif obj is self._target and event.type() in (
                QEvent.Type.Resize, QEvent.Type.Move):
            self._reposition_bubble()
        return False

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.skip_requested.emit()
            return
        super().keyPressEvent(event)

    def _target_rect(self) -> QRect | None:
        if self._target is None:
            return None
        local_rect = self._target_local_rect or self._target.rect()
        top_left = self._target.mapTo(self._main_window, local_rect.topLeft())
        return QRect(top_left, local_rect.size())

    def _reposition_bubble(self) -> None:
        # QWidget.adjustSize()/sizeHint() compute height for the layout's
        # UNCONSTRAINED preferred width, not the bubble's actual
        # setFixedWidth(280) -- for a word-wrapped body label that
        # silently clips the last line or so whenever the text needs more
        # lines at 280px than it would at its wider "natural" width.
        # QLayout.heightForWidth() asks for the height at the width the
        # bubble is actually constrained to, which is the number that
        # matters here.
        bubble_width = self._bubble.width()
        self._bubble.resize(bubble_width, self._bubble.layout().heightForWidth(bubble_width))
        rect = self._target_rect()
        if rect is not None:
            bubble_x = rect.right() + 12
            if bubble_x + bubble_width > self.width():
                bubble_x = rect.left() - bubble_width - 12
                if bubble_x < 0:
                    # Neither side of the target has room -- it spans most of
                    # the window (e.g. a first plot in an otherwise-empty
                    # panel). Anchor inside the target's own left edge instead
                    # of drifting to the window's absolute edge, which can
                    # land the bubble on top of unrelated UI (e.g. a docked
                    # side panel) rather than the target it's meant to label.
                    bubble_x = max(rect.left(), 0)
            bubble_x = min(bubble_x, self.width() - bubble_width)
            bubble_y = max(0, min(rect.top(), self.height() - self._bubble.height()))
            self._bubble.move(bubble_x, bubble_y)
        # Must run AFTER the bubble's own position is finalized above --
        # _update_mask() reads the bubble's current geometry (see
        # _dimmed_path) to keep it out of the click-through cutout, so
        # computing the mask first would carve the hole around the
        # bubble's stale, pre-move position instead of its real one.
        self._update_mask()

    def _cutout_rect(self) -> QRect | None:
        rect = self._target_rect()
        if rect is None:
            return None
        return rect.adjusted(-4, -4, 4, 4)

    def _dimmed_path(self) -> QPainterPath:
        """The region that should actually block mouse input (and get
        painted dark): everything except the spotlight cutout around the
        target, so a click inside the cutout reaches the real widget behind
        it instead of this overlay.

        The bubble's own rect is carved back OUT of the cutout: per
        QWidget.setMask's documented contract, only the parts of a widget
        that overlap the mask are visible or receive mouse events *at
        all* -- that applies to this widget's children too, not just its
        own background. A target spanning nearly the whole window (a
        first plot in an otherwise-empty panel) produces a cutout that
        wide as well, and _reposition_bubble's fallback anchors the
        bubble inside the target's own bounds when there's no room on
        either side -- which, without this exclusion, falls inside that
        same cutout and silently disappears (invisible, unclickable),
        not merely mispositioned."""
        path = QPainterPath()
        path.addRect(self.rect())
        cutout_rect = self._cutout_rect()
        if cutout_rect is not None:
            cutout = QPainterPath()
            cutout.addRoundedRect(cutout_rect, 6, 6)
            bubble_path = QPainterPath()
            bubble_path.addRect(self._bubble.geometry())
            cutout = cutout.subtracted(bubble_path)
            path = path.subtracted(cutout)
        return path

    def _update_mask(self) -> None:
        self.setMask(QRegion(self._dimmed_path().toFillPolygon().toPolygon()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillPath(self._dimmed_path(), QColor(0, 0, 0, 140))
        cutout_rect = self._cutout_rect()
        if cutout_rect is not None:
            # The mask (see _update_mask) excludes cutout_rect entirely so
            # clicks pass through it -- a stroke centered on cutout_rect's
            # own boundary would have its inner half clipped by that mask.
            # Draw it 1px further out so the full pen width stays on the
            # dimmed (visible) side.
            painter.setPen(QPen(self.palette().highlight().color(), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(cutout_rect.adjusted(-1, -1, 1, 1), 7, 7)
