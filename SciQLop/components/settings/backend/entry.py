from pydantic import BaseModel
from enum import Enum
import yaml
from platformdirs import *
import os
from typing import TypeVar, ClassVar, Type
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

SCIQLOP_CONFIG_DIR = str(user_config_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True))

T = TypeVar('T', bound='ConfigEntry')


class SettingsCategory(str, Enum):
    PLUGINS = "plugins"
    WORKSPACES = "workspaces"
    APPLICATION = "application"
    APPEARANCE = "appearance"


class ConfigEntry(BaseModel):
    category: ClassVar[str]
    subcategory: ClassVar[str]

    _entries_: ClassVar[dict[str, Type["ConfigEntry"]]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ in cls._entries_:
            raise ValueError(f"Duplicate entry name: {cls.__name__}")
        if not hasattr(cls, 'category') or not isinstance(cls.category, str) or cls.category == "":
            raise ValueError(f"Entry class {cls.__name__} must have a string 'category' attribute")
        if not hasattr(cls, 'subcategory') or not isinstance(cls.subcategory, str) or cls.subcategory == "":
            raise ValueError(f"Entry class {cls.__name__} must have a string 'subcategory' attribute")
        cls._entries_[cls.__name__] = cls

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

    def __init__(self, **data):
        save = True
        config_file = self.config_file()
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as file:
                    data: dict = yaml.safe_load(file)
                    save = False
            except Exception as e:
                log.error(f"Error loading settings from {config_file}: {e}")
        super().__init__(**data)
        if save:
            self.save()

    def save(self):
        config_file = self.config_file()
        try:
            with open(config_file, 'w') as file:
                yaml.safe_dump(self.model_dump(), file)
        except Exception as e:
            log.error(f"Error saving settings to {config_file}: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()
