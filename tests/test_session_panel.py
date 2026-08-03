"""SessionListPanel tree: rows, filter, context menus, drop resolution."""
from dataclasses import dataclass, field


@dataclass
class _DS:
    id: str
    name: str
    pinned: bool
    mtime: float
    group: str = ""
    tags: list = field(default_factory=list)


def _panel(qtbot):
    from SciQLop.components.agents.chat.session_panel import SessionListPanel
    p = SessionListPanel()
    qtbot.addWidget(p)
    return p


def _groups():
    from SciQLop.components.agents.chat.sessions_view import SessionGroup, PINNED_GROUP, UNGROUPED
    return [
        SessionGroup(PINNED_GROUP, [_DS("a", "Pinned one", True, 2.0)]),
        SessionGroup("MMS", [_DS("a", "Pinned one", True, 2.0), _DS("b", "Plain", False, 1.0)]),
        SessionGroup(UNGROUPED, [_DS("c", "Loose", False, 0.5)]),
    ]


def test_set_groups_builds_tree(qtbot):
    p = _panel(qtbot)
    p.set_groups(_groups())
    tree = p._tree
    assert tree.topLevelItemCount() == 3
    assert tree.topLevelItem(0).text(0).startswith("📌 Pinned (1)")
    assert tree.topLevelItem(1).text(0) == "MMS (2)"
    # pinned child carries the marker + id role
    from PySide6.QtCore import Qt
    child = tree.topLevelItem(1).child(0)
    assert "📌" in child.text(0)
    assert child.data(0, Qt.ItemDataRole.UserRole) == "a"


def test_activation_emits_only_for_sessions(qtbot):
    p = _panel(qtbot)
    p.set_groups(_groups())
    got = []
    p.session_selected.connect(got.append)
    p._on_activated(p._tree.topLevelItem(1).child(1))  # a session
    p._on_activated(p._tree.topLevelItem(1))           # a header -> no emit
    assert got == ["b"]


def test_filter_box_emits(qtbot):
    p = _panel(qtbot)
    seen = []
    p.filter_changed.connect(seen.append)
    p._filter.setText("mms")
    assert seen[-1] == "mms"


def test_expand_state_preserved_across_rebuild(qtbot):
    p = _panel(qtbot)
    p.set_groups(_groups())
    p._on_collapsed(p._tree.topLevelItem(1))  # user collapsed MMS -> recorded
    p.set_groups(_groups())                   # rebuild
    assert p._tree.topLevelItem(1).isExpanded() is False


def test_resolve_drop_group(qtbot):
    import SciQLop.components.agents.chat.session_panel as sp
    from SciQLop.components.agents.chat.sessions_view import PINNED_GROUP, UNGROUPED
    p = _panel(qtbot)
    p.set_groups(_groups())
    pinned_hdr, mms_hdr, ungrouped_hdr = (p._tree.topLevelItem(i) for i in range(3))
    assert sp._resolve_drop_group(mms_hdr) == "MMS"          # onto a real group
    assert sp._resolve_drop_group(mms_hdr.child(1)) == "MMS"  # onto a session -> its group
    assert sp._resolve_drop_group(ungrouped_hdr) == ""        # onto Ungrouped
    assert sp._resolve_drop_group(None) == ""                 # empty area
    assert sp._resolve_drop_group(pinned_hdr) is None         # Pinned rejects


def test_group_header_menu_signals(qtbot):
    p = _panel(qtbot)
    p.set_groups(_groups())
    renamed, deleted = [], []
    p.group_rename_requested.connect(renamed.append)
    p.group_delete_requested.connect(deleted.append)
    # emulate the actions the header context menu wires
    p._emit_group_rename(p._tree.topLevelItem(1))
    p._emit_group_delete(p._tree.topLevelItem(1))
    assert renamed == ["MMS"] and deleted == ["MMS"]


def test_session_menu_offers_delete_and_emits_the_id(qtbot):
    p = _panel(qtbot)
    p.set_groups(_groups())
    deleted = []
    p.session_delete_requested.connect(deleted.append)
    menu = p.session_menu(p._tree.topLevelItem(1).child(1))  # "Plain", id b
    labels = [a.text() for a in menu.actions() if a.text()]
    assert labels[-1] == "Delete session…"
    menu.actions()[-1].trigger()
    assert deleted == ["b"]


def test_synthetic_group_collapse_preserved(qtbot):
    p = _panel(qtbot)
    p.set_groups(_groups())
    p._on_collapsed(p._tree.topLevelItem(0))  # Pinned header collapsed
    p.set_groups(_groups())                   # rebuild
    assert p._tree.topLevelItem(0).isExpanded() is False
