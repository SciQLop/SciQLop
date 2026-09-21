"""Tests for human-readable byte-size settings.

Covers the parsing/formatting helpers, the ByteSizeDelegate, and the Speasy
bridge exposing ``cache.size`` as a byte size (stored as an integer).
"""

from .fixtures import *

import pytest
import yaml
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from pydantic import ByteSize

from SciQLop.components.settings.backend.byte_size import (
    format_byte_size,
    parse_byte_size,
)


class TestParsingAndFormatting:
    def test_default_displays_as_20_gb(self):
        assert format_byte_size(20_000_000_000) == "20 GB"

    def test_plain_number_means_bytes(self):
        assert parse_byte_size("123") == 123

    def test_decimal_units(self):
        assert parse_byte_size("500MB") == 500_000_000
        assert parse_byte_size("1.5 GB") == 1_500_000_000

    def test_binary_units(self):
        assert parse_byte_size("2 TiB") == 2 * 2**40

    def test_garbage_is_rejected(self):
        with pytest.raises(Exception):
            parse_byte_size("not a size")

    def test_round_trip(self):
        for value in (0, 1, 500_000_000, 1_500_000_000, 20_000_000_000):
            assert parse_byte_size(format_byte_size(value)) == value


def _type(delegate, text):
    delegate._edit.clear()
    QTest.keyClicks(delegate._edit, text)


def _commit(delegate):
    QTest.keyClick(delegate._edit, Qt.Key.Key_Return)


@pytest.fixture
def delegate(qtbot, qapp):
    from SciQLop.components.settings.ui.settings_delegates import ByteSizeDelegate

    d = ByteSizeDelegate()
    qtbot.addWidget(d)
    d.set_value(20_000_000_000)
    return d


class TestByteSizeDelegate:
    def test_shows_human_readable(self, delegate):
        assert delegate._edit.text() == "20 GB"
        assert delegate.get_value() == 20_000_000_000

    def test_nothing_is_emitted_while_typing(self, delegate):
        """The settings panel saves on every emission: '2', then '20' then '20 G' must not
        reach Speasy as a 2 byte cache limit."""
        received = []
        delegate.value_changed.connect(received.append)

        _type(delegate, "500MB")

        assert received == []
        assert delegate.get_value() == 20_000_000_000

    def test_committing_emits_the_bytes_once_and_normalises_the_text(self, delegate):
        received = []
        delegate.value_changed.connect(received.append)
        _type(delegate, "500MB")

        _commit(delegate)

        assert received == [500_000_000]
        assert delegate.get_value() == 500_000_000
        assert delegate._edit.text() == "500 MB"

    def test_committing_an_unchanged_value_emits_nothing(self, delegate):
        received = []
        delegate.value_changed.connect(received.append)

        _commit(delegate)

        assert received == []

    def test_invalid_text_is_flagged_while_typing_and_cleared_when_fixed(self, delegate):
        _type(delegate, "garbage")
        assert delegate.is_valid() is False

        _type(delegate, "1 GB")
        assert delegate.is_valid() is True

    def test_committing_invalid_text_restores_the_previous_value(self, delegate):
        received = []
        delegate.value_changed.connect(received.append)
        _type(delegate, "garbage")

        _commit(delegate)

        assert received == []
        assert delegate.get_value() == 20_000_000_000
        assert delegate._edit.text() == "20 GB"
        assert delegate.is_valid() is True


def _cache_bridge():
    from SciQLop.components.settings.backend.entry import ConfigEntry
    from SciQLop.plugins.speasy_provider.settings import _SpeasyBridge

    return next(
        cls
        for cls in ConfigEntry.list_entries().values()
        if issubclass(cls, _SpeasyBridge) and cls._speasy_section_ == "cache"
    )


class TestSpeasyBridge:
    def test_size_field_is_byte_size(self):
        assert _cache_bridge().model_fields["size"].annotation is ByteSize

    def test_size_uses_byte_size_delegate(self, qapp):
        from SciQLop.components.settings.ui.settings_delegates import (
            ByteSizeDelegate,
            get_delegate_for_field,
        )

        cls = _cache_bridge()
        delegate = get_delegate_for_field("size", cls.model_fields["size"])
        assert isinstance(delegate, ByteSizeDelegate)

    def test_existing_int_value_loads(self):
        assert _cache_bridge()().size == 20_000_000_000

    def test_save_writes_plain_integer_string(self, monkeypatch):
        import speasy.config as spz_cfg

        captured = {}
        monkeypatch.setattr(
            spz_cfg.cache.size, "set", lambda v: captured.__setitem__("value", v)
        )
        instance = _cache_bridge()()
        instance.size = 500_000_000
        instance.save()
        assert captured["value"] == "500000000"


class TestConfigEntryBackwardCompat:
    def test_existing_int_loads_and_serializes_as_int(self, tmp_path, monkeypatch):
        from SciQLop.components.settings.backend.entry import ConfigEntry

        monkeypatch.setattr(
            "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
            str(tmp_path),
        )
        cls = type(
            "ByteSizeBackwardCompatEntry",
            (ConfigEntry,),
            {
                "__annotations__": {"size": ByteSize},
                "size": 0,
                "category": "test",
                "subcategory": "byte_size",
            },
        )
        with open(cls.config_file(), "w") as f:
            yaml.safe_dump({"size": 20_000_000_000}, f)

        instance = cls()
        assert instance.size == 20_000_000_000
        with open(cls.config_file()) as f:
            assert yaml.safe_load(f)["size"] == 20_000_000_000
