"""Unit tests for SettingsNode tree building and SettingsModel.

Tests the pure tree-construction logic. The Qt model tests need
qapp but not a full main_window.
"""
from .fixtures import *
import pytest
from unittest.mock import patch

from SciQLop.components.settings.backend.entry import ConfigEntry
from SciQLop.components.settings.backend.model import (
    SettingsNode, _build_entry_node, build_settings_tree,
)


# --- SettingsNode ---

def test_node_row_root():
    node = SettingsNode(name="root")
    assert node.row() == 0


def test_node_row_child():
    parent = SettingsNode(name="parent")
    c0 = parent.append(SettingsNode(name="first"))
    c1 = parent.append(SettingsNode(name="second"))
    assert c0.row() == 0
    assert c1.row() == 1


def test_node_append_sets_parent():
    parent = SettingsNode(name="parent")
    child = SettingsNode(name="child")
    parent.append(child)
    assert child.parent is parent
    assert child in parent.children


# --- _build_entry_node ---

@pytest.fixture
def tmp_config_dir(tmp_path):
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path)):
        yield tmp_path


def _make_entry(name, tmp_config_dir, **fields):
    annotations = {k: type(v) for k, v in fields.items()}
    ns = {"__annotations__": annotations, "category": "test", "subcategory": "sub"}
    ns.update(fields)
    return type(name, (ConfigEntry,), ns)


def test_build_entry_node_creates_field_children(tmp_config_dir):
    cls = _make_entry("EntryA", tmp_config_dir, x=1, y="hello")
    root = SettingsNode(name="root")
    node = _build_entry_node(cls, root)
    assert node.name == "EntryA"
    assert node.entry_cls is cls
    field_names = {c.field_name for c in node.children}
    assert "x" in field_names
    assert "y" in field_names


def test_build_entry_node_field_info_set(tmp_config_dir):
    cls = _make_entry("EntryB", tmp_config_dir, val=42)
    root = SettingsNode(name="root")
    node = _build_entry_node(cls, root)
    child = node.children[0]
    assert child.field_name == "val"
    assert child.field_info is not None


# --- build_settings_tree ---

def test_build_settings_tree_groups_by_category(tmp_config_dir):
    _make_entry("TreeCat1", tmp_config_dir, a=1)
    # Create a second entry in a different category
    annotations = {"b": int}
    ns = {"__annotations__": annotations, "category": "other", "subcategory": "sub", "b": 2}
    type("TreeCat2", (ConfigEntry,), ns)

    tree = build_settings_tree()
    category_names = {c.name for c in tree.children}
    assert "test" in category_names
    assert "other" in category_names


def test_build_settings_tree_has_subcategory_level(tmp_config_dir):
    _make_entry("TreeSub1", tmp_config_dir, v=1)
    tree = build_settings_tree()
    # Find the "test" category
    test_cat = next(c for c in tree.children if c.name == "test")
    sub_names = {c.name for c in test_cat.children}
    assert "sub" in sub_names


# --- SettingsModel (Qt) ---

def test_settings_model_row_count(qtbot, qapp, tmp_config_dir):
    from SciQLop.components.settings.backend.model import SettingsModel
    _make_entry("ModelTest1", tmp_config_dir, z=99)
    model = SettingsModel()
    model.rebuild()
    assert model.rowCount() > 0


def test_settings_model_data_display_role(qtbot, qapp, tmp_config_dir):
    from SciQLop.components.settings.backend.model import SettingsModel
    from PySide6.QtGui import Qt
    _make_entry("ModelTest2", tmp_config_dir, z=99)
    model = SettingsModel()
    model.rebuild()
    index = model.index(0, 0)
    name = model.data(index, Qt.ItemDataRole.DisplayRole)
    assert isinstance(name, str)
    assert len(name) > 0


def test_settings_model_node_from_invalid_index(qtbot, qapp, tmp_config_dir):
    from SciQLop.components.settings.backend.model import SettingsModel
    from PySide6.QtCore import QModelIndex
    model = SettingsModel()
    model.rebuild()
    node = model.node_from_index(QModelIndex())
    assert node is model.root()
