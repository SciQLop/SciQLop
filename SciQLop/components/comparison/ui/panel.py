"""The dockable Comparison panel: a header choosing the view and alignment over the view it draws."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMenu, QTabBar, QToolButton, QVBoxLayout, QWidget)

from SciQLop.components.comparison.backend.dimensions import ANCHOR_LABELS, dimension, resolve_sides
from SciQLop.components.comparison.backend.model import Comparison, Side
from SciQLop.components.comparison.backend.views import (COMPARISON_VIEWS, ComparisonView, available_views,
                                                         options_for)
from SciQLop.components.comparison.ui.panel_kind import COMPARISON_PANEL
from SciQLop.core.extensions import NotRegistered
from SciQLop.core.panel_kinds import KIND_PROPERTY


def _message(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    return label


def _time_range_of(inner: Optional[QWidget]) -> Optional[tuple[float, float]]:
    rng = getattr(inner, "time_range", None)
    return (rng.start(), rng.stop()) if rng is not None else None


class ComparisonPanel(QWidget):
    edit_requested = Signal()

    def __init__(self, name: str, comparison: Comparison, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName(name)
        self.setWindowTitle(name)
        self.setProperty(KIND_PROPERTY, COMPARISON_PANEL)
        self._comparison = comparison
        self.inner: Optional[QWidget] = None
        self.options_widget: Optional[QWidget] = None
        self.option_combos: dict[str, QComboBox] = {}
        self._options_view: Optional[str] = None
        self._build_header()
        self.edit_requested.connect(self._edit)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._header)
        self.set_comparison(comparison)

    def _build_header(self) -> None:
        self.title = QLabel()
        self.tab_bar = QTabBar()
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        # A tab bar always has a current tab, so an unknown stored view leaves one selected: clicking it must still switch.
        self.tab_bar.tabBarClicked.connect(self._on_tab_changed)
        self.anchor_label = QLabel()
        self.anchor_combo = QComboBox()
        for anchor, label in ANCHOR_LABELS.items():
            self.anchor_combo.addItem(label, anchor)
        self.anchor_combo.currentIndexChanged.connect(self._on_anchor_changed)
        self.menu_button = QToolButton()
        self.menu_button.setText("⋯")
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_button.setMenu(self._build_menu())
        self._header = QHBoxLayout()
        for widget in (self.title, self.tab_bar):
            self._header.addWidget(widget)
        self._header.addStretch()
        self._options_box = QHBoxLayout()
        self._header.addLayout(self._options_box)
        for widget in (self.anchor_label, self.anchor_combo, self.menu_button):
            self._header.addWidget(widget)

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Edit comparison…", self.edit_requested.emit)
        menu.addAction("Save as template…", self.save_as_template)
        return menu

    def _edit(self) -> None:
        from SciQLop.components.comparison.ui.wizard import edit_comparison  # the wizard imports this module
        edit_comparison(self)

    @property
    def comparison(self) -> Comparison:
        return self._comparison

    def to_config(self) -> dict:
        return self._comparison.model_dump(mode="json")

    def set_comparison(self, comparison: Comparison) -> None:
        self._comparison = comparison
        sides = self._sides()
        self._show_header(sides)
        self._rebuild(sides)

    def set_view(self, view_id: str) -> None:
        if view_id != self._comparison.view:
            self.set_comparison(self._comparison.model_copy(update={"view": view_id}))

    def _sides(self) -> list[Side] | str:
        """The sides, or why they cannot be resolved."""
        try:
            return resolve_sides(self._comparison)
        except NotRegistered:
            return f"this comparison needs the {self._comparison.dimension!r} dimension, which is not installed"
        except ValueError as e:
            return f"cannot build this comparison: {e}"

    def _show_header(self, sides: list[Side] | str) -> None:
        resolved = not isinstance(sides, str)
        d = dimension(self._comparison.dimension) if resolved else None
        self.title.setText(f"Compare: {len(sides)} {d.noun}" if resolved else "Compare")
        self._fill_tabs(sides if resolved else [])
        self._show_options(COMPARISON_VIEWS.find(self._comparison.view))
        is_time = self._comparison.dimension == "time"
        self.anchor_label.setVisible(is_time)
        self.anchor_combo.setVisible(is_time)
        self.anchor_label.setText(f"aligned on event {ANCHOR_LABELS[self._comparison.anchor]}")
        self._quietly(self.anchor_combo, lambda: self.anchor_combo.setCurrentIndex(
            self.anchor_combo.findData(self._comparison.anchor)))

    def _tab_ids(self) -> list[str]:
        return [self.tab_bar.tabData(i) for i in range(self.tab_bar.count())]

    def _fill_tabs(self, sides: list[Side]) -> None:
        """Updates the tabs in place when the views are the same: this runs inside the bar's own currentChanged."""
        views = available_views(self._comparison, sides) if sides else []

        def fill():
            if [view.id for view, _ in views] != self._tab_ids():
                while self.tab_bar.count():
                    self.tab_bar.removeTab(0)
                for view, _ in views:
                    self.tab_bar.setTabData(self.tab_bar.addTab(view.label), view.id)
            for i, (view, reason) in enumerate(views):
                self.tab_bar.setTabEnabled(i, reason is None)
                self.tab_bar.setTabToolTip(i, reason or "")
                if view.id == self._comparison.view:
                    self.tab_bar.setCurrentIndex(i)
        self._quietly(self.tab_bar, fill)

    def _show_options(self, view: Optional[ComparisonView]) -> None:
        view_id = view.id if view is not None else None
        if view_id != self._options_view:
            self._replace_options_widget(view)
        options = options_for(self._comparison, view) if view is not None else {}
        for key, combo in self.option_combos.items():
            self._quietly(combo, lambda c=combo, k=key: c.setCurrentIndex(c.findData(options.get(k))))

    def _replace_options_widget(self, view: Optional[ComparisonView]) -> None:
        if self.options_widget is not None:
            self.options_widget.deleteLater()
        self.options_widget = QWidget()
        box = QHBoxLayout(self.options_widget)
        box.setContentsMargins(0, 0, 0, 0)
        self.option_combos = {}
        for key, choices in (view.option_choices if view is not None else {}).items():
            combo = QComboBox()
            for choice in choices:
                combo.addItem(view.choice_labels.get(choice, choice), choice)
            combo.currentIndexChanged.connect(lambda i, c=combo, k=key: self.set_option(k, c.itemData(i)))
            box.addWidget(QLabel(key))
            box.addWidget(combo)
            self.option_combos[key] = combo
        self._options_box.addWidget(self.options_widget)
        self._options_view = view.id if view is not None else None

    def set_option(self, key: str, value: str) -> None:
        c = self._comparison
        current = c.view_options.get(c.view, {})
        if current.get(key) != value:
            self.set_comparison(c.model_copy(update={"view_options": {**c.view_options,
                                                                      c.view: {**current, key: value}}}))

    @staticmethod
    def _quietly(widget: QWidget, change) -> None:
        widget.blockSignals(True)
        try:
            change()
        finally:
            widget.blockSignals(False)

    def _rebuild(self, sides: list[Side] | str) -> None:
        old = self.inner
        self.inner = self._build_inner(sides, _time_range_of(old))
        if old is not None:
            self.layout().replaceWidget(old, self.inner)
            old.deleteLater()
        else:
            self.layout().addWidget(self.inner, 1)

    def _build_inner(self, sides: list[Side] | str, time_range) -> QWidget:
        if isinstance(sides, str):
            return _message(sides)
        view = COMPARISON_VIEWS.find(self._comparison.view)
        if view is None:
            return _message(f"this comparison needs the {self._comparison.view!r} view, which is not installed")
        reason = view.applies(self._comparison, sides)
        if reason is not None:
            return _message(f"{view.label}: {reason}")
        try:
            return view.build(self._comparison, sides, options_for(self._comparison, view), time_range, self)
        except ValueError as e:
            return _message(f"cannot build this comparison: {e}")

    def _on_tab_changed(self, index: int) -> None:
        view_id = self.tab_bar.tabData(index)
        if view_id is not None and self.tab_bar.isTabEnabled(index):
            self.set_view(view_id)

    def _on_anchor_changed(self, index: int) -> None:
        anchor = self.anchor_combo.itemData(index)
        if anchor is not None and anchor != self._comparison.anchor:
            self.set_comparison(self._comparison.model_copy(update={"anchor": anchor}))

    def save_as_template(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        from SciQLop.components.plotting import panel_template
        name, ok = QInputDialog.getText(self, "Save as template", "Template name:", text=self.windowTitle())
        if ok and name.strip():
            path = str(panel_template.templates_dir() / f"{name.strip()}.json")
            template = panel_template.PanelTemplate.from_panel(self)
            template.name = name.strip()
            template.to_file(path)
            panel_template.save_preview(self, path)


class UnreadableComparisonPanel(QWidget):
    """A stored comparison that does not parse: says why, and saves back exactly what was stored."""

    def __init__(self, name: str, config: dict, error: Exception, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName(name)
        self.setWindowTitle(name)
        self.setProperty(KIND_PROPERTY, COMPARISON_PANEL)
        self._config = config
        layout = QVBoxLayout(self)
        layout.addWidget(_message(f"cannot open this comparison: {error}"))
        layout.addStretch()

    def to_config(self) -> dict:
        return self._config
