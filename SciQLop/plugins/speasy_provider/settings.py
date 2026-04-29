"""Bridge Speasy config sections into SciQLop's settings UI.

Each Speasy ConfigSection becomes a SciQLop ConfigEntry subclass whose
fields, types, defaults, and descriptions are read from Speasy at import
time — nothing is hardcoded.
"""

from __future__ import annotations

from typing import ClassVar, Any
from pydantic import BaseModel, Field

import speasy.config as spz_cfg

from SciQLop.components.settings.backend.entry import ConfigEntry


# -- Mixin that proxies load/save to Speasy -----------------------------------

class _SpeasyBridge:
    _speasy_section_: ClassVar[str]

    def __init__(self, **data):
        section = getattr(spz_cfg, self._speasy_section_)
        for field_name in self.__class__.model_fields:
            if field_name not in data:
                data[field_name] = getattr(section, field_name).get()
        # Skip ConfigEntry.__init__ which would load from YAML and call save().
        BaseModel.__init__(self, **data)

    def save(self):
        section = getattr(spz_cfg, self._speasy_section_)
        for field_name in self.__class__.model_fields:
            value = getattr(self, field_name)
            getattr(section, field_name).set(_to_speasy_str(value))

    @classmethod
    def config_file(cls) -> str:
        return ""


def _to_speasy_str(value: Any) -> str:
    if isinstance(value, set):
        return ",".join(str(v) for v in sorted(value))
    if isinstance(value, dict):
        return repr(value)
    return str(value)


# -- Widget hints for known field patterns ------------------------------------

_WIDGET_HINTS: dict[str, dict[str, Any]] = {
    "password": {"widget": "password"},
    "path": {"widget": "path_dir"},
    "cache_path": {"widget": "path_dir"},
    "inventory_data_path": {"widget": "path_dir"},
}


def _field_for_entry(entry: spz_cfg.ConfigEntry) -> tuple[type, Any]:
    """Derive a (type, FieldInfo) pair from a Speasy ConfigEntry."""
    value = entry.get()
    py_type = type(value)
    extra = dict(_WIDGET_HINTS.get(entry.key2, {}))
    if py_type is int and not (-(2**31) <= value <= 2**31 - 1):
        py_type = float
    return (py_type, Field(default=value, description=entry.description, json_schema_extra=extra or None))


def _build_bridge(section_name: str, class_name: str) -> type[ConfigEntry]:
    """Dynamically create a ConfigEntry subclass bridging a Speasy section."""
    section = getattr(spz_cfg, section_name)

    field_defs: dict[str, Any] = {}
    annotations: dict[str, type] = {}
    for attr_name in sorted(dir(section)):
        if attr_name.startswith("_"):
            continue
        attr = getattr(section, attr_name)
        if not isinstance(attr, spz_cfg.ConfigEntry):
            continue
        py_type, field_info = _field_for_entry(attr)
        field_defs[attr_name] = field_info
        annotations[attr_name] = py_type

    namespace = {
        "__annotations__": annotations,
        "__module__": __name__,
        "category": "speasy",
        "subcategory": section_name,
        "_speasy_section_": section_name,
        **field_defs,
    }

    return type(class_name, (_SpeasyBridge, ConfigEntry), namespace)


for _name in dir(spz_cfg):
    _attr = getattr(spz_cfg, _name)
    if isinstance(_attr, spz_cfg.ConfigSection):
        _cls_name = f"Speasy{_name.title()}Settings"
        globals()[_cls_name] = _build_bridge(_name, _cls_name)
