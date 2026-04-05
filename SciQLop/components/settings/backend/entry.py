from pydantic import BaseModel
from enum import Enum
import yaml
from platformdirs import *
import os
from typing import TypeVar, ClassVar, Type
from PySide6.QtCore import QObject, Signal
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

SCIQLOP_CONFIG_DIR = str(user_config_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True))

T = TypeVar('T', bound='ConfigEntry')


class _SettingsNotifier(QObject):
    changed = Signal(str, object)


class SettingsCategory(str, Enum):
    PLUGINS = "plugins"
    WORKSPACES = "workspaces"
    APPLICATION = "application"
    APPEARANCE = "appearance"
    CATALOGS = "catalogs"


class KeyringMapping:
    """Declares which fields are backed by the system keyring.

    ``service_field`` names the field whose *value* is used as the keyring
    service identifier (typically a URL).  ``username_field`` and
    ``password_field`` name the fields that map to the keyring credential.
    """

    def __init__(self, service_field: str, username_field: str, password_field: str):
        self.service_field = service_field
        self.username_field = username_field
        self.password_field = password_field


def _load_keyring(mapping: KeyringMapping, data: dict) -> None:
    import keyring
    service = data.get(mapping.service_field, "").rstrip("/")
    if not service:
        return
    try:
        creds = keyring.get_credential(service, None)
    except Exception as e:
        log.debug("Cannot read credentials from keyring for %s: %s", service, e)
        return
    if creds is None:
        return
    if not data.get(mapping.username_field):
        data[mapping.username_field] = creds.username
    if not data.get(mapping.password_field):
        data[mapping.password_field] = creds.password


def _save_keyring(mapping: KeyringMapping, data: dict) -> None:
    import keyring
    service = data.get(mapping.service_field, "").rstrip("/")
    username = data.get(mapping.username_field, "")
    password = data.get(mapping.password_field, "")
    if not service or not username:
        return
    try:
        keyring.set_password(service, username, password)
    except Exception as e:
        log.error("Cannot write credentials to keyring for %s: %s", service, e)


class ConfigEntry(BaseModel):
    category: ClassVar[str]
    subcategory: ClassVar[str]

    _entries_: ClassVar[dict[str, Type["ConfigEntry"]]] = {}
    _notifier: ClassVar[_SettingsNotifier]
    _keyring_: ClassVar[KeyringMapping | None] = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ in cls._entries_:
            raise ValueError(f"Duplicate entry name: {cls.__name__}")
        if not hasattr(cls, 'category') or not isinstance(cls.category, str) or cls.category == "":
            raise ValueError(f"Entry class {cls.__name__} must have a string 'category' attribute")
        if not hasattr(cls, 'subcategory') or not isinstance(cls.subcategory, str) or cls.subcategory == "":
            raise ValueError(f"Entry class {cls.__name__} must have a string 'subcategory' attribute")
        cls._notifier = _SettingsNotifier()
        cls._entries_[cls.__name__] = cls

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name in self.__class__.model_fields:
            self.__class__._notifier.changed.emit(name, value)

    @classmethod
    def list_entries(cls) -> dict[str, Type["ConfigEntry"]]:
        return cls._entries_

    @classmethod
    def get_entry(cls, name: str) -> 'ConfigEntry':
        if name not in cls._entries_:
            raise ValueError(f"Entry not found: {name}")
        return cls._entries_[name]()

    @classmethod
    def config_file(cls) -> str:
        return os.path.join(SCIQLOP_CONFIG_DIR, cls.__name__.lower() + ".yaml")

    @classmethod
    def _keyring_field_names(cls) -> set[str]:
        m = cls._keyring_
        if m is None:
            return set()
        return {m.username_field, m.password_field}

    def __init__(self, **data):
        save = True
        config_file = self.config_file()
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as file:
                    loaded = yaml.safe_load(file)
                    if isinstance(loaded, dict):
                        data = loaded
                        save = False
            except Exception as e:
                log.error(f"Error loading settings from {config_file}: {e}")
        if self.__class__._keyring_ is not None:
            _load_keyring(self.__class__._keyring_, data)
        super().__init__(**data)
        if save:
            self.save()

    def save(self):
        config_file = self.config_file()
        dump = self.model_dump()
        keyring_fields = self._keyring_field_names()
        if keyring_fields and self.__class__._keyring_ is not None:
            _save_keyring(self.__class__._keyring_, dump)
            for f in keyring_fields:
                dump.pop(f, None)
        try:
            with open(config_file, 'w') as file:
                yaml.safe_dump(dump, file)
        except Exception as e:
            log.error(f"Error saving settings to {config_file}: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()
