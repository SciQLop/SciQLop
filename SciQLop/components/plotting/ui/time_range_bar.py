from PySide6.QtCore import Qt, Signal, QDateTime, QTimeZone, Property, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QWidget, QHBoxLayout, QDateTimeEdit, QComboBox, QPushButton, QLabel

from SciQLop.core import TimeRange
from SciQLop.core.ui import Metrics, fit_combo_to_content

DURATION_PRESETS = [("1m", 60), ("1h", 3600), ("12h", 43200), ("1d", 86400), ("7d", 604800)]
ZOOM_LIMIT_PRESETS = [("1h", 3600.0), ("1d", 86400.0), ("1w", 604800.0), ("1y", 365.25 * 86400), ("Unlimited", 0.0)]


def _make_start_picker(parent):
    w = QDateTimeEdit(parent)
    w.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
    w.setCalendarPopup(True)
    w.setTimeZone(QTimeZone.UTC)
    return w


def _make_duration_combo(parent):
    w = QComboBox(parent)
    for label, _ in DURATION_PRESETS:
        w.addItem(label)
    w.setCurrentText("1d")
    fit_combo_to_content(w)
    return w


def _default_zoom_limit_label() -> str:
    from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings
    return PlotBackendSettings().default_zoom_limit


def _make_zoom_limit_combo(parent):
    w = QComboBox(parent)
    for label, _ in ZOOM_LIMIT_PRESETS:
        w.addItem(label)
    w.setCurrentText(_default_zoom_limit_label())
    w.setToolTip("Maximum zoom-out range")
    fit_combo_to_content(w)
    return w


def _make_nav_button(text, parent):
    b = QPushButton(text, parent)
    b.setFixedWidth(Metrics.em(2.5))
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


def _closest_duration_index(seconds):
    return min(range(len(DURATION_PRESETS)), key=lambda i: abs(DURATION_PRESETS[i][1] - seconds))


class TimeRangeBar(QWidget):
    range_changed = Signal(TimeRange)
    catalog_choice_changed = Signal(str)
    limit_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppressing = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)
        self.setMaximumHeight(Metrics.ex(2.5))

        self._start_picker = _make_start_picker(self)
        self._duration_combo = _make_duration_combo(self)
        self._fast_backward_btn = _make_nav_button("|◀", self)
        self._backward_btn = _make_nav_button("◀", self)
        self._forward_btn = _make_nav_button("▶", self)
        self._fast_forward_btn = _make_nav_button("▶|", self)
        self._zoom_limit_combo = _make_zoom_limit_combo(self)
        self._zoom_limit_label = QLabel("Max:", self)
        self._catalog_combo = QComboBox(self)
        self._catalog_combo.setVisible(False)

        layout.addStretch(1)
        layout.addWidget(self._fast_backward_btn)
        layout.addWidget(self._backward_btn)
        layout.addWidget(self._start_picker)
        layout.addWidget(self._duration_combo)
        layout.addWidget(self._forward_btn)
        layout.addWidget(self._fast_forward_btn)
        layout.addWidget(self._zoom_limit_label)
        layout.addWidget(self._zoom_limit_combo)
        layout.addWidget(self._catalog_combo)
        layout.addStretch(1)

        self._start_picker.dateTimeChanged.connect(self._on_user_changed)
        self._duration_combo.currentTextChanged.connect(self._on_user_changed)
        self._backward_btn.clicked.connect(lambda: self.step(-1))
        self._forward_btn.clicked.connect(lambda: self.step(1))
        self._fast_backward_btn.clicked.connect(lambda: self.step(-5))
        self._fast_forward_btn.clicked.connect(lambda: self.step(5))
        self._zoom_limit_combo.currentTextChanged.connect(self._on_zoom_limit_changed)
        self._catalog_combo.currentIndexChanged.connect(self._on_catalog_choice_changed)

    @property
    def _duration_seconds(self):
        return dict(DURATION_PRESETS).get(self._duration_combo.currentText(), 86400)

    @property
    def duration_text(self) -> str:
        return self._duration_combo.currentText()

    @duration_text.setter
    def duration_text(self, value: str):
        self._duration_combo.setCurrentText(value)

    @property
    def time_range(self):
        start = self._start_picker.dateTime().toMSecsSinceEpoch() / 1000.0
        return TimeRange(start, start + self._duration_seconds)

    def set_range(self, tr: TimeRange):
        self._suppressing = True
        try:
            self._start_picker.setDateTime(tr.datetime_start())
            dt = tr.stop() - tr.start()
            self._duration_combo.setCurrentIndex(_closest_duration_index(dt))
        finally:
            self._suppressing = False

    def _on_user_changed(self, _=None):
        if not self._suppressing:
            self.range_changed.emit(self.time_range)

    def step(self, n):
        start = self._start_picker.dateTime().toMSecsSinceEpoch() / 1000.0
        new_start = start + n * self._duration_seconds
        self._suppressing = True
        try:
            self._start_picker.setDateTime(
                QDateTime.fromMSecsSinceEpoch(int(new_start * 1000), QTimeZone.UTC)
            )
        finally:
            self._suppressing = False
        self.range_changed.emit(self.time_range)

    def set_catalog_choices(self, items: list[tuple[str, str]]) -> None:
        self._catalog_combo.blockSignals(True)
        self._catalog_combo.clear()
        for name, uuid in items:
            self._catalog_combo.addItem(name, userData=uuid)
        self._catalog_combo.blockSignals(False)
        fit_combo_to_content(self._catalog_combo)
        self._catalog_combo.setVisible(len(items) > 0)
        if items:
            self._on_catalog_choice_changed(0)

    def clear_catalog_choices(self) -> None:
        self._catalog_combo.blockSignals(True)
        self._catalog_combo.clear()
        self._catalog_combo.blockSignals(False)
        self._catalog_combo.setVisible(False)

    def selected_catalog_uuid(self) -> str | None:
        if self._catalog_combo.count() == 0:
            return None
        return self._catalog_combo.currentData()

    @property
    def max_range_seconds(self) -> float:
        return dict(ZOOM_LIMIT_PRESETS).get(self._zoom_limit_combo.currentText(), 0.0)

    @max_range_seconds.setter
    def max_range_seconds(self, value: float):
        for label, secs in ZOOM_LIMIT_PRESETS:
            if secs == value:
                self._zoom_limit_combo.setCurrentText(label)
                return
        self._zoom_limit_combo.setCurrentText("Unlimited")

    def _on_zoom_limit_changed(self, _text: str):
        self.limit_changed.emit(self.max_range_seconds)

    def _on_catalog_choice_changed(self, index: int) -> None:
        uuid = self._catalog_combo.itemData(index)
        if uuid is not None:
            self.catalog_choice_changed.emit(uuid)

    def _get_highlight(self):
        return getattr(self, '_highlight_value', 0.0)

    def _set_highlight(self, v):
        self._highlight_value = v
        width = max(1, int(v * 4))
        alpha = int(v * 255)
        self._start_picker.setStyleSheet(
            f"QDateTimeEdit {{ border: {width}px solid rgba(230, 50, 50, {alpha}); border-radius: 4px; }}"
        )

    highlight = Property(float, _get_highlight, _set_highlight)

    def pulse(self):
        anim = QPropertyAnimation(self, b"highlight", self)
        anim.setDuration(2000)
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.25, 0.2)
        anim.setKeyValueAt(0.5, 1.0)
        anim.setKeyValueAt(0.75, 0.2)
        anim.setKeyValueAt(1.0, 0.0)
        anim.finished.connect(lambda: self._start_picker.setStyleSheet(""))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _get_limit_highlight(self):
        return getattr(self, '_limit_highlight_value', 0.0)

    def _set_limit_highlight(self, v):
        self._limit_highlight_value = v
        width = max(1, int(v * 4))
        alpha = int(v * 255)
        self._zoom_limit_combo.setStyleSheet(
            f"QComboBox {{ border: {width}px solid rgba(230, 160, 50, {alpha}); border-radius: 4px; }}"
        )

    limit_highlight = Property(float, _get_limit_highlight, _set_limit_highlight)

    def pulse_limit(self):
        anim = QPropertyAnimation(self, b"limit_highlight", self)
        anim.setDuration(1500)
        anim.setKeyValueAt(0.0, 1.0)
        anim.setKeyValueAt(0.3, 0.2)
        anim.setKeyValueAt(0.6, 1.0)
        anim.setKeyValueAt(1.0, 0.0)
        anim.finished.connect(lambda: self._zoom_limit_combo.setStyleSheet(""))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
