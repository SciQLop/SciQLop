"""Tests for the Speasy → SciQLop settings bridge.

Verifies that settings are dynamically discovered from Speasy's config,
that reads/writes proxy through to Speasy, and that the settings UI
can render delegates for the bridged fields.
"""
from .fixtures import *

import pytest
import speasy.config as spz_cfg

from SciQLop.components.settings.backend.entry import ConfigEntry
from SciQLop.plugins.speasy_provider.settings import _SpeasyBridge


def _all_speasy_sections():
    return {
        name: getattr(spz_cfg, name)
        for name in dir(spz_cfg)
        if isinstance(getattr(spz_cfg, name), spz_cfg.ConfigSection)
    }


def _all_bridge_classes():
    return {
        name: cls
        for name, cls in ConfigEntry.list_entries().items()
        if issubclass(cls, _SpeasyBridge)
    }


class TestDiscovery:
    def test_every_speasy_section_has_a_bridge(self):
        sections = _all_speasy_sections()
        bridges = _all_bridge_classes()
        bridge_sections = {cls._speasy_section_ for cls in bridges.values()}
        for section_name in sections:
            assert section_name in bridge_sections, (
                f"Speasy section {section_name!r} has no bridge ConfigEntry"
            )

    def test_every_speasy_entry_has_a_field(self):
        for section_name, section in _all_speasy_sections().items():
            bridge_cls = next(
                cls for cls in _all_bridge_classes().values()
                if cls._speasy_section_ == section_name
            )
            for attr_name in dir(section):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(section, attr_name)
                if isinstance(attr, spz_cfg.ConfigEntry):
                    assert attr_name in bridge_cls.model_fields, (
                        f"Speasy entry {section_name}.{attr_name} missing from {bridge_cls.__name__}"
                    )


class TestReadFromSpeasy:
    def test_bridge_reads_live_values(self):
        for cls in _all_bridge_classes().values():
            section = getattr(spz_cfg, cls._speasy_section_)
            instance = cls()
            for field_name in cls.model_fields:
                expected = getattr(section, field_name).get()
                actual = getattr(instance, field_name)
                assert actual == expected, (
                    f"{cls.__name__}.{field_name}: expected {expected!r}, got {actual!r}"
                )


class TestWriteToSpeasy:
    def test_save_propagates_to_speasy(self):
        bridge_cls = next(
            cls for cls in _all_bridge_classes().values()
            if cls._speasy_section_ == "proxy"
        )
        section = spz_cfg.proxy
        original = section.url.get()
        try:
            instance = bridge_cls()
            instance.url = "https://test.example.com/"
            instance.save()
            assert section.url.get() == "https://test.example.com/"
        finally:
            section.url.set(original)

    def test_set_field_round_trips(self):
        bridge_cls = next(
            cls for cls in _all_bridge_classes().values()
            if cls._speasy_section_ == "core"
        )
        section = spz_cfg.core
        original = section.disabled_providers.get()
        try:
            instance = bridge_cls()
            instance.disabled_providers = {"csa", "ssc"}
            instance.save()
            reloaded = section.disabled_providers.get()
            assert reloaded == {"csa", "ssc"}
        finally:
            from SciQLop.plugins.speasy_provider.settings import _to_speasy_str
            section.disabled_providers.set(_to_speasy_str(original))


class TestUIIntegration:
    def test_editable_fields_have_delegates(self, qapp):
        from SciQLop.components.settings.ui.settings_delegates import (
            get_delegate_for_field, is_field_editable, NotEditableDelegate,
        )
        for cls in _all_bridge_classes().values():
            for field_name, field_info in cls.model_fields.items():
                delegate = get_delegate_for_field(field_name, field_info)
                if is_field_editable(field_name, field_info):
                    assert not isinstance(delegate, NotEditableDelegate), (
                        f"{cls.__name__}.{field_name} is editable but got NotEditableDelegate"
                    )

    def test_delegates_accept_live_values(self, qapp):
        from SciQLop.components.settings.ui.settings_delegates import (
            get_delegate_for_field, is_field_editable,
        )
        for cls in _all_bridge_classes().values():
            instance = cls()
            for field_name, field_info in cls.model_fields.items():
                if not is_field_editable(field_name, field_info):
                    continue
                delegate = get_delegate_for_field(field_name, field_info)
                value = getattr(instance, field_name)
                delegate.set_value(value)
                assert delegate.get_value() == value, (
                    f"{cls.__name__}.{field_name}: delegate round-trip failed "
                    f"(set {value!r}, got {delegate.get_value()!r})"
                )
