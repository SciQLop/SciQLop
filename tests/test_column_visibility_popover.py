from .fixtures import *
from PySide6.QtCore import Qt
from SciQLop.components.catalogs.ui.column_visibility_popover import (
    ColumnVisibilityPopover,
    ColumnEntry,
)


def test_popover_filters_columns_by_search(qtbot, qapp):
    entries = [
        ColumnEntry(key="start", label="start", visible=True, frozen=True),
        ColumnEntry(key="stop", label="stop", visible=True, frozen=True),
        ColumnEntry(key="author", label="author", visible=True, frozen=False),
        ColumnEntry(key="rating", label="rating", visible=False, frozen=False),
    ]
    pop = ColumnVisibilityPopover(entries)
    qtbot.addWidget(pop)
    pop.set_filter("rat")
    assert pop.visible_entry_keys() == ["rating"]


def test_popover_emits_visibility_changed(qtbot, qapp):
    entries = [ColumnEntry(key="author", label="author", visible=True, frozen=False)]
    pop = ColumnVisibilityPopover(entries)
    qtbot.addWidget(pop)
    received = []
    pop.visibility_changed.connect(lambda key, vis: received.append((key, vis)))
    pop.set_visible("author", False)
    assert received == [("author", False)]


def test_popover_show_all_unhides_non_frozen(qtbot, qapp):
    entries = [
        ColumnEntry(key="start", label="start", visible=True, frozen=True),
        ColumnEntry(key="author", label="author", visible=False, frozen=False),
    ]
    pop = ColumnVisibilityPopover(entries)
    qtbot.addWidget(pop)
    received = []
    pop.visibility_changed.connect(lambda key, vis: received.append((key, vis)))
    pop.show_all()
    assert ("author", True) in received


def test_popover_hide_all_skips_frozen(qtbot, qapp):
    entries = [
        ColumnEntry(key="start", label="start", visible=True, frozen=True),
        ColumnEntry(key="author", label="author", visible=True, frozen=False),
    ]
    pop = ColumnVisibilityPopover(entries)
    qtbot.addWidget(pop)
    received = []
    pop.visibility_changed.connect(lambda key, vis: received.append((key, vis)))
    pop.hide_all()
    assert ("author", False) in received
    assert ("start", False) not in received


def test_popover_reset_emits_signal(qtbot, qapp):
    entries = [ColumnEntry(key="author", label="author", visible=True, frozen=False)]
    pop = ColumnVisibilityPopover(entries)
    qtbot.addWidget(pop)
    received = []
    pop.reset_requested.connect(lambda: received.append(True))
    pop._reset_btn.click()
    assert received == [True]
