from pydantic import BaseModel
import yaml
from platformdirs import *
import os
from typing import TypeVar, Dict
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

SCIQLOP_CONFIG_DIR = str(user_config_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True))

T = TypeVar('T', bound='ConfigEntry')


class ConfigEntry(BaseModel):

    def _get_file_path(self) -> str:
        return os.path.join(SCIQLOP_CONFIG_DIR, self.__class__.__name__.lower() + ".yaml")

    def __init__(self, **data):
        save = True
        if os.path.exists(self._get_file_path()):
            try:
                with open(self._get_file_path(), 'r') as file:
                    data: Dict = yaml.safe_load(file)
                    save = False
            except Exception as e:
                log.error(f"Error loading settings from {self._get_file_path()}: {e}")
        super().__init__(**data)
        if save:
            self.save()

    def save(self):
        try:
            with open(self._get_file_path(), 'w') as file:
                yaml.safe_dump(self.model_dump(), file)
        except Exception as e:
            log.error(f"Error saving settings to {self._get_file_path()}: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()
