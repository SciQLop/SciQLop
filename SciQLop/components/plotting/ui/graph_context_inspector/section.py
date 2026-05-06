"""Read-only summary panel + Show full metadata… dialog for a graph context.

The layout is a vertical stack of {bold name} → {value} pairs with word-wrap
on values, so it stays readable in narrow inspector docks. Buttons sit in a
horizontal row at the bottom and stretch to match available width.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy, QToolButton,
    QTreeView, QVBoxLayout, QWidget,
)

from SciQLop.core.graph_context import context_of, provider_for, _last_fetch_line


class _MetadataDialog(QDialog):
    """Renders a (potentially nested) dict as an expandable tree."""

    def __init__(self, title: str, payload: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(560, 480)
        layout = QVBoxLayout(self)
        view = QTreeView(self)
        view.setUniformRowHeights(True)
        view.setAlternatingRowColors(True)
        model = QStandardItemModel(self)
        model.setHorizontalHeaderLabels(["Key", "Value"])
        _populate_tree(model.invisibleRootItem(), payload)
        view.setModel(model)
        view.expandToDepth(1)
        view.resizeColumnToContents(0)
        layout.addWidget(view)
        close = QPushButton("Close", self)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(close)
        layout.addLayout(bottom)


def _populate_tree(parent_item: QStandardItem, value: Any) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            key_item = QStandardItem(str(k))
            key_item.setEditable(False)
            if isinstance(v, (dict, list, tuple)):
                parent_item.appendRow([key_item, QStandardItem("")])
                _populate_tree(key_item, v)
            else:
                parent_item.appendRow([key_item, _leaf_item(v)])
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            key_item = QStandardItem(f"[{i}]")
            key_item.setEditable(False)
            if isinstance(v, (dict, list, tuple)):
                parent_item.appendRow([key_item, QStandardItem("")])
                _populate_tree(key_item, v)
            else:
                parent_item.appendRow([key_item, _leaf_item(v)])
    else:
        parent_item.appendRow([QStandardItem(""), _leaf_item(value)])


def _leaf_item(v: Any) -> QStandardItem:
    item = QStandardItem(repr(v) if isinstance(v, str) else str(v))
    item.setEditable(False)
    return item


_FIELD_TOOLTIPS = {
    "Source": "What this graph plots — Speasy product UID, virtual product "
              "path, or callable qualname.",
    "Plot": "Panel and plot index this graph belongs to, plus the graph type.",
    "Parameters": "Current parameter values for this graph. Updated live when "
                  "you edit them in the Parameters section above.",
    "Last loaded": "Number of points and dtype of the last data set on this "
                   "graph (read live from graph.data()).",
}


class GraphContextSection(QWidget):
    """Read-only graph identity panel + 'Copy Python code' / 'Show metadata…'.

    Vertical stack of bold field names above word-wrapped values — stays
    readable in narrow inspector docks. Refreshes on graph.data_changed.
    """

    def __init__(self, graph, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._graph = graph

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._labels: dict[str, QLabel] = {}
        for field in ("Source", "Plot", "Parameters", "Last loaded"):
            layout.addLayout(self._build_field(field))

        layout.addLayout(self._build_buttons())
        self._refresh()
        if hasattr(graph, "data_changed"):
            try:
                graph.data_changed.connect(self._refresh)
            except Exception:
                pass

    def _build_field(self, name: str) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(2)
        title = QLabel(name, self)
        title.setStyleSheet("font-weight: 600;")
        title.setToolTip(_FIELD_TOOLTIPS[name])
        value = QLabel("—", self)
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Preferred)
        value.setToolTip(_FIELD_TOOLTIPS[name])
        block.addWidget(title)
        block.addWidget(value)
        self._labels[name] = value
        return block

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        self._copy_btn = QToolButton(self)
        self._copy_btn.setText("Copy Python code")
        self._copy_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._copy_btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Fixed)
        self._copy_btn.setToolTip(
            "Copy a paste-ready Python snippet that reproduces this graph."
        )
        self._copy_menu = QMenu(self._copy_btn)
        self._copy_btn.setMenu(self._copy_menu)
        self._show_btn = QPushButton("Show full metadata…", self)
        self._show_btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Fixed)
        self._show_btn.setToolTip(
            "Open provider-supplied metadata (ISTP attrs for Speasy products, "
            "knobs schema for virtual products) in a tree dialog."
        )
        self._show_btn.clicked.connect(self._show_full)
        row.addWidget(self._copy_btn)
        row.addWidget(self._show_btn)
        return row

    def _refresh(self) -> None:
        ctx = context_of(self._graph)
        if ctx is None:
            for lbl in self._labels.values():
                lbl.setText("—")
            self._copy_btn.setEnabled(False)
            self._show_btn.setEnabled(False)
            return
        self._labels["Source"].setText(_source_line(ctx))
        self._labels["Plot"].setText(
            f'Panel "{ctx.panel_name}" · plot {ctx.plot_index} ({ctx.graph_type})'
        )
        if ctx.knobs:
            self._labels["Parameters"].setText(
                ", ".join(f"{k}={v!r}" for k, v in ctx.knobs.items())
            )
        else:
            self._labels["Parameters"].setText("(none)")
        last = _last_fetch_line(self._graph)
        self._labels["Last loaded"].setText(last or "(no data yet)")

        provider = provider_for(ctx)
        variants = {}
        if provider is not None:
            try:
                variants = provider.python_snippets(ctx, graph=self._graph) or {}
            except Exception:
                variants = {}
        self._rebuild_copy_menu(variants)
        self._copy_btn.setEnabled(bool(variants))
        self._show_btn.setEnabled(provider is not None)

    def _rebuild_copy_menu(self, variants: dict) -> None:
        self._copy_menu.clear()
        for label, snippet in variants.items():
            if not snippet:
                continue
            act = QAction(label, self._copy_menu)
            act.triggered.connect(
                lambda _checked=False, s=snippet: QGuiApplication.clipboard().setText(s)
            )
            self._copy_menu.addAction(act)

    def _show_full(self) -> None:
        ctx = context_of(self._graph)
        if ctx is None:
            return
        provider = provider_for(ctx)
        if provider is None:
            return
        try:
            payload = provider.extended_metadata(ctx)
        except Exception as exc:
            payload = {"error": repr(exc)}
        title = ctx.speasy_id or ctx.vp_path or "Graph metadata"
        dlg = _MetadataDialog(f"Metadata — {title}", payload or {}, parent=self)
        dlg.exec()


def _source_line(ctx) -> str:
    if ctx.kind == "speasy":
        return f"Speasy: {ctx.speasy_id}"
    if ctx.kind == "vp":
        return f"Virtual: {ctx.vp_path}"
    if ctx.kind == "function":
        cb = f"{ctx.callback_module}.{ctx.callback_qualname}".strip(".")
        return f"Function: {cb}"
    return "Static data"
