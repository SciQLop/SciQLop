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


# --- Keyring-backed credentials ---

class _FakeKeyring:
    """Stub backend that mimics macOS: no get_credential, only get/set_password."""

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def get_password(self, service, username):
        return self.store.get((service, username))


@pytest.fixture
def fake_keyring(monkeypatch):
    import keyring as kr
    fake = _FakeKeyring()
    monkeypatch.setattr(kr, "set_password", fake.set_password)
    monkeypatch.setattr(kr, "get_password", fake.get_password)

    def _no_credential(*_a, **_kw):
        return None
    monkeypatch.setattr(kr, "get_credential", _no_credential)
    return fake


def _make_cred_entry(name, tmp_config_dir):
    from SciQLop.components.settings.backend.entry import KeyringMapping
    annotations = {"server_url": str, "username": str, "password": str}
    ns = {
        "__annotations__": annotations,
        "category": "test", "subcategory": "sub",
        "server_url": "https://example.test/svc",
        "username": "",
        "password": "",
        "_keyring_": KeyringMapping("server_url", "username", "password"),
    }
    return type(name, (ConfigEntry,), ns)


def test_keyring_credentials_persist_across_reload(tmp_config_dir, fake_keyring):
    """Regression: on macOS the base-class get_credential returns None for
    username=None, so credentials saved via set_password were never loaded
    back. Loading must use get_password with the stored username."""
    cls = _make_cred_entry("CredEntry1", tmp_config_dir)

    instance = cls()
    instance.username = "alice@example.test"
    instance.password = "s3cret"
    instance.save()

    assert ("https://example.test/svc", "alice@example.test") in fake_keyring.store
    assert fake_keyring.store[("https://example.test/svc", "alice@example.test")] == "s3cret"

    reloaded = cls()
    assert reloaded.username == "alice@example.test"
    assert reloaded.password == "s3cret"


def test_keyring_username_persisted_to_yaml(tmp_config_dir, fake_keyring):
    """Username is a non-secret identifier — it must be stored in YAML so we
    can look up the password in the keyring on reload."""
    import yaml
    cls = _make_cred_entry("CredEntry2", tmp_config_dir)
    instance = cls()
    instance.username = "bob@example.test"
    instance.password = "hunter2"
    instance.save()

    with open(cls.config_file()) as f:
        dumped = yaml.safe_load(f)
    assert dumped["username"] == "bob@example.test"
    assert "password" not in dumped or not dumped["password"]


def test_keyring_legacy_linux_yaml_migration(tmp_config_dir, monkeypatch):
    """Linux users upgrading from ≤0.11.3 have YAML without a username field
    (older code popped it before dumping). On Linux/Windows the keyring
    backend supports get_credential(service, None), so we must fall back to
    it, recover the pair, and persist the username back to YAML on save()."""
    import yaml
    import keyring as kr

    store: dict[tuple[str, str], str] = {
        ("https://example.test/svc", "dave@example.test"): "legacy-pw",
    }

    class _Cred:
        def __init__(self, username, password):
            self.username = username
            self.password = password

    def _get_credential(service, username):
        if username is None:
            for (svc, user), pw in store.items():
                if svc == service:
                    return _Cred(user, pw)
            return None
        pw = store.get((service, username))
        return _Cred(username, pw) if pw else None

    monkeypatch.setattr(kr, "get_credential", _get_credential)
    monkeypatch.setattr(kr, "get_password",
                        lambda service, username: store.get((service, username)))
    monkeypatch.setattr(kr, "set_password",
                        lambda service, username, password: store.update({(service, username): password}))

    cls = _make_cred_entry("CredEntryMigrate", tmp_config_dir)
    # Write legacy YAML: no username field, empty password
    with open(cls.config_file(), "w") as f:
        yaml.safe_dump({"server_url": "https://example.test/svc"}, f)

    instance = cls()
    assert instance.username == "dave@example.test"
    assert instance.password == "legacy-pw"

    instance.save()
    with open(cls.config_file()) as f:
        dumped = yaml.safe_load(f)
    assert dumped["username"] == "dave@example.test"


def test_keyring_empty_password_not_saved(tmp_config_dir, fake_keyring):
    """Partial edits (username without a password yet) must not overwrite an
    existing keyring entry with an empty password."""
    cls = _make_cred_entry("CredEntry3", tmp_config_dir)
    fake_keyring.store[("https://example.test/svc", "carol@example.test")] = "existing"

    instance = cls()
    instance.username = "carol@example.test"
    instance.save()

    assert fake_keyring.store[("https://example.test/svc", "carol@example.test")] == "existing"
