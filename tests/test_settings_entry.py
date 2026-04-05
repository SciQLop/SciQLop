"""Unit tests for the ConfigEntry settings system.

Tests config file path generation, YAML persistence, validation,
and context manager.
"""
from .fixtures import *
import os
import pytest
import yaml
from unittest.mock import patch

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


@pytest.fixture
def tmp_config_dir(tmp_path):
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path)):
        yield tmp_path


def _make_entry_cls(name, tmp_config_dir, category="test", subcategory="sub", **fields):
    """Dynamically create a ConfigEntry subclass with given fields."""
    # Pydantic needs annotations for fields
    annotations = {k: type(v) for k, v in fields.items()}
    ns = {"__annotations__": annotations, "category": category, "subcategory": subcategory}
    ns.update(fields)
    cls = type(name, (ConfigEntry,), ns)
    return cls


class TestConfigFilePath:
    def test_path_is_lowercase(self, tmp_config_dir):
        cls = _make_entry_cls("MyFancySettings", tmp_config_dir, value="default")
        assert cls.config_file().endswith("myfancysettings.yaml")

    def test_path_in_config_dir(self, tmp_config_dir):
        cls = _make_entry_cls("PathTestEntry", tmp_config_dir, value="x")
        assert str(tmp_config_dir) in cls.config_file()


class TestInitSubclass:
    def test_missing_category_raises(self):
        with pytest.raises(ValueError, match="category"):
            type("BadEntry1", (ConfigEntry,), {
                "__annotations__": {}, "subcategory": "sub",
            })

    def test_empty_category_raises(self):
        with pytest.raises(ValueError, match="category"):
            type("BadEntry2", (ConfigEntry,), {
                "__annotations__": {}, "category": "", "subcategory": "sub",
            })

    def test_missing_subcategory_raises(self):
        with pytest.raises(ValueError, match="subcategory"):
            type("BadEntry3", (ConfigEntry,), {
                "__annotations__": {}, "category": "test",
            })

    def test_duplicate_name_raises(self, tmp_config_dir):
        _make_entry_cls("UniqueEntry", tmp_config_dir, val="x")
        with pytest.raises(ValueError, match="Duplicate"):
            _make_entry_cls("UniqueEntry", tmp_config_dir, val="y")


class TestSaveAndLoad:
    def test_saves_on_first_creation(self, tmp_config_dir):
        cls = _make_entry_cls("SaveTest1", tmp_config_dir, greeting="hello")
        instance = cls()
        assert os.path.exists(cls.config_file())
        with open(cls.config_file()) as f:
            data = yaml.safe_load(f)
        assert data["greeting"] == "hello"

    def test_loads_from_existing_file(self, tmp_config_dir):
        cls = _make_entry_cls("LoadTest1", tmp_config_dir, greeting="hello")
        # Write a modified config before instantiation
        with open(cls.config_file(), 'w') as f:
            yaml.safe_dump({"greeting": "bonjour"}, f)
        instance = cls()
        assert instance.greeting == "bonjour"

    def test_context_manager_saves(self, tmp_config_dir):
        cls = _make_entry_cls("CtxTest1", tmp_config_dir, count=0)
        with cls() as s:
            s.count = 42
        reloaded = cls()
        assert reloaded.count == 42


class TestListAndGetEntries:
    def test_list_entries_includes_registered(self, tmp_config_dir):
        cls = _make_entry_cls("ListTest1", tmp_config_dir, x=1)
        assert "ListTest1" in ConfigEntry.list_entries()

    def test_get_entry_returns_instance(self, tmp_config_dir):
        cls = _make_entry_cls("GetTest1", tmp_config_dir, x=1)
        instance = ConfigEntry.get_entry("GetTest1")
        assert isinstance(instance, cls)

    def test_get_entry_not_found(self):
        with pytest.raises(ValueError, match="Entry not found"):
            ConfigEntry.get_entry("NonExistent_Entry_XYZ")


class TestEdgeCases:
    def test_empty_yaml_file_does_not_crash(self, tmp_config_dir):
        """Reproducer: an empty YAML file returns None from safe_load,
        causing **None TypeError in ConfigEntry.__init__."""
        cls = _make_entry_cls("EmptyYamlTest", tmp_config_dir, greeting="default")
        # Create an empty file
        with open(cls.config_file(), 'w') as f:
            f.write("")
        instance = cls()
        assert instance.greeting == "default"

    def test_corrupt_yaml_file_uses_defaults(self, tmp_config_dir):
        cls = _make_entry_cls("CorruptYamlTest", tmp_config_dir, value=99)
        with open(cls.config_file(), 'w') as f:
            f.write(": : : not valid yaml [[[")
        instance = cls()
        assert instance.value == 99
