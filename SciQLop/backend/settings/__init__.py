from platformdirs import *

import configparser
import os
from typing import Any

SCIQLOP_CONFIG_DIR = str(user_config_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True))

SCIQLOP_CONFIG_FILE = os.path.join(SCIQLOP_CONFIG_DIR, "config.ini")
_config = configparser.ConfigParser()
_config.read(SCIQLOP_CONFIG_FILE)

def _save_changes():
    with open(SCIQLOP_CONFIG_FILE, 'w') as f:
        _config.write(f)


class ConfigEntry:
    """Configuration entry class. Used to set and get configuration values.

    Attributes
    ----------
    section: str
        Module or category name
    name: str
        Entry name
    default: str
        Default value
    type_ctor: Any
        function called to get value from string repr
    env_var_name: str
        Environment variable name to use to set this entry

    Methods
    -------
    get:
        Get entry current value
    set:
        Set entry value (could be env or file)
    """

    def __init__(self, section: str, key2: str, default: Any = "", type_ctor=None, description: str = ""):
        self.section = section
        self.name = key2
        self.default = str(default)
        self.type_ctor = type_ctor or (lambda x: x)
        self.description = description
        self.env_var_name = f"SCIQLOP_{self.section}_{self.name}".upper().replace(
            '-', '_')

    def __repr__(self):
        return f"""ConfigEntry: {self.section}/{self.name}
    environment variable name: {self.env_var_name}
    value:                     {self.get()}
    description:               {self.description}"""

    def get(self):
        """Get entry current value, first from environment variable, then from config file, then default value.

        Returns
        -------
        Any
            The current value of the entry
        """
        if self.env_var_name in os.environ:
            return self.type_ctor(os.environ[self.env_var_name])
        if self.section in _config and self.name in _config[self.section]:
            return self.type_ctor(_config[self.section][self.name])
        return self.type_ctor(self.default)

    def set(self, value: str):
        if self.env_var_name in os.environ:
            os.environ[self.env_var_name] = str(value)
        if self.section not in _config:
            _config.add_section(self.section)
        _config[self.section][self.name] = str(value)
        _save_changes()

    def __call__(self, *args, **kwargs):
        return self.get()


def remove_entry(entry: ConfigEntry):
    """Deletes entry from config file and its section if it was the last entry

    Parameters
    ----------
    entry: ConfigEntry
        the entry to delete

    Returns
    -------
    None

    """
    if entry.section in _config:
        section = _config[entry.section]
        if entry.name in section:
            section.pop(entry.name)
        if len(section) == 0:
            _config.remove_section(entry.section)
        _save_changes()

