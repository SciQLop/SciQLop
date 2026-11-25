"""Where plugins are looked for.

Kept apart from ``loader.py`` — and free of any Qt import — because the
launcher needs the search paths while preparing a workspace, long before the
GUI stack exists. See tests/test_launcher_thin_imports.py.
"""

import os
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .settings import SciQLopPluginsSettings


def bundled_plugins_folder() -> str:
    """The plugins shipped inside the running SciQLop package."""
    from SciQLop import plugins
    return os.path.dirname(os.path.realpath(plugins.__file__))


def plugins_folders(settings: Optional["SciQLopPluginsSettings"] = None) -> List[str]:
    from .settings import SciQLopPluginsSettings, USER_PLUGINS_FOLDERS
    if settings is None:
        settings = SciQLopPluginsSettings()
    return [bundled_plugins_folder(), USER_PLUGINS_FOLDERS] + list(settings.extra_plugins_folders)
