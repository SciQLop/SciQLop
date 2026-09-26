"""Load newly added or newly enabled plugins without restarting SciQLop.

Watches the plugin settings; for each plugin that is enabled and was never
loaded in this process, installs its missing python dependencies (off the GUI
thread, with the running stack pinned) and then loads it on the GUI thread.
Removals are not handled here: running code can't be unloaded, so those keep
the settings page's restart button.
"""
import threading

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.components.workspaces.backend.live_install import guarded_install
from .loader import loader
from .settings import SciQLopPluginsSettings

log = getLogger(__name__)

_WATCHED_FIELDS = ("plugins", "extra_plugins_folders")


class PluginsLiveLoader(QObject):
    _ready = Signal(object)  # [(folder, name)] whose dependencies are in place

    def __init__(self, main_window, install=guarded_install, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._install = install
        self._ready.connect(self._load)
        SciQLopPluginsSettings._notifier.changed.connect(self._on_setting_changed)

    @Slot(str, object)
    def _on_setting_changed(self, field_name, _value):
        if field_name in _WATCHED_FIELDS:
            # The notifier fires on assignment; the settings are saved just after.
            QTimer.singleShot(0, self._scan)

    def _scan(self):
        threading.Thread(target=self._prepare, daemon=True).start()

    def _prepare(self):
        ready = []
        for folder, name in loader.new_enabled_plugins():
            missing = loader.missing_requirements(loader.plugin_requirements(folder, name))
            if missing and not self._installed(name, missing):
                continue
            ready.append((folder, name))
        if ready:
            self._ready.emit(ready)

    def _installed(self, name, missing) -> bool:
        log.info(f"Installing {', '.join(missing)} for plugin {name}")
        result = self._install(missing)
        if result.returncode != 0:
            log.error(f"Plugin {name} not loaded: installing {', '.join(missing)} failed:\n{result.stderr}")
            return False
        return True

    @Slot(object)
    def _load(self, ready):
        for folder, name in ready:
            if name in loader._attempted:
                continue
            log.info(f"Loading plugin {name} without restart")
            loader.load_one(folder, name, self._main_window)
