from __future__ import annotations

import json
import re
import subprocess
import threading
import urllib.request
from importlib.metadata import PackageNotFoundError, distribution

import packaging.version

from PySide6.QtCore import QObject, Signal, Slot

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.components.workspaces.backend.uv import uv_command

log = getLogger(__name__)

DEFAULT_STORE_URL = "https://sciqlop.github.io/sciqlop-appstore/index.json"

_PEP440_SPLIT = re.compile(r"[><=!~;@\s]")


def _fetch_index(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _latest_version(plugin: dict) -> dict | None:
    versions = plugin.get("versions", [])
    if not versions:
        return None
    return max(versions, key=lambda v: packaging.version.parse(v["version"]))


def _package_name_from_pip(pip_field: str) -> str | None:
    """Extract the distribution name from a pip specifier or wheel URL."""
    pip_field = pip_field.strip()
    if pip_field.startswith("http://") or pip_field.startswith("https://"):
        filename = __import__("pathlib").PurePosixPath(pip_field.split("?")[0].split("#")[0]).name
        if filename.endswith(".whl"):
            return filename.split("-")[0].replace("_", "-").lower()
        return None
    name = _PEP440_SPLIT.split(pip_field, 1)[0].strip()
    return name.replace("_", "-").lower() if name else None


def _installed_version(package_name: str) -> str | None:
    """Return the installed version of a package, or None."""
    try:
        return distribution(package_name).version
    except PackageNotFoundError:
        return None


def _save_installed_package(appstore_name: str, pip_spec: str, dist_name: str) -> None:
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings, InstalledPackage
    with SciQLopPluginsSettings() as settings:
        settings.installed_packages[appstore_name] = InstalledPackage(pip=pip_spec, name=dist_name)


def _remove_installed_package(appstore_name: str) -> None:
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    with SciQLopPluginsSettings() as settings:
        settings.installed_packages.pop(appstore_name, None)


def _try_load_plugin(dist_name: str) -> None:
    """Attempt to hot-load a newly installed entry-point plugin."""
    import importlib.metadata
    from SciQLop.components.plugins.backend.loader.loader import (
        ENTRY_POINT_GROUP, _load_entry_point_plugin,
    )
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings, PluginConfig
    from SciQLop.core.sciqlop_application import sciqlop_app

    main_window = sciqlop_app().main_window
    if main_window is None:
        return

    for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
        try:
            ep_dist = ep.dist.name if ep.dist else None
        except Exception:
            ep_dist = None
        if ep_dist and ep_dist.lower().replace("_", "-") == dist_name.lower().replace("_", "-"):
            with SciQLopPluginsSettings() as settings:
                if ep.name not in settings.plugins:
                    settings.plugins[ep.name] = PluginConfig()
            _load_entry_point_plugin(ep, main_window)
            log.info(f"Hot-loaded plugin {ep.name} from {dist_name}")


class AppStoreBackend(QObject):
    """Python backend exposed to the AppStore page via QWebChannel."""

    packages_ready = Signal(str)
    install_finished = Signal(str)
    uninstall_finished = Signal(str)
    _hot_load_requested = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._packages: list[dict] = []
        self._hot_load_requested.connect(self._do_hot_load)

    @Slot(str)
    def _do_hot_load(self, dist_name: str) -> None:
        _try_load_plugin(dist_name)

    @Slot()
    def fetch_packages(self) -> None:
        def _fetch():
            try:
                self._packages = _fetch_index(DEFAULT_STORE_URL)
                self.packages_ready.emit(json.dumps(self._packages))
            except Exception as e:
                log.error(f"Failed to fetch appstore index: {e}")
                self.packages_ready.emit(json.dumps([]))

        threading.Thread(target=_fetch, daemon=True).start()

    @Slot(result=str)
    def list_packages(self) -> str:
        return json.dumps(self._packages)

    @Slot(result=str)
    def list_tags(self) -> str:
        tags = set()
        for p in self._packages:
            tags.update(p.get("tags", []))
        return json.dumps(sorted(tags))

    @Slot(result=str)
    def get_installed_versions(self) -> str:
        """Return a JSON object mapping package names to installed versions."""
        result = {}
        for pkg in self._packages:
            latest = _latest_version(pkg)
            if not latest:
                continue
            dist_name = _package_name_from_pip(latest["pip"])
            if not dist_name:
                continue
            installed = _installed_version(dist_name)
            if installed:
                result[pkg["name"]] = installed
        return json.dumps(result)

    @Slot(str)
    def install_package(self, name: str) -> None:
        def _install():
            plugin = next((p for p in self._packages if p["name"] == name), None)
            if not plugin:
                self.install_finished.emit(json.dumps({"name": name, "ok": False, "error": "not found"}))
                return
            latest = _latest_version(plugin)
            if not latest:
                self.install_finished.emit(json.dumps({"name": name, "ok": False, "error": "no versions"}))
                return
            try:
                pip_spec = latest["pip"]
                cmd = uv_command("pip", "install", pip_spec)
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                dist_name = _package_name_from_pip(pip_spec) or name
                _save_installed_package(name, pip_spec, dist_name)
                self.install_finished.emit(json.dumps({"name": name, "ok": True, "version": latest["version"]}))
                self._hot_load_requested.emit(dist_name)
            except Exception as e:
                log.error(f"Failed to install {name}: {e}")
                self.install_finished.emit(json.dumps({"name": name, "ok": False, "error": str(e)}))

        threading.Thread(target=_install, daemon=True).start()

    @Slot(str)
    def uninstall_package(self, name: str) -> None:
        def _uninstall():
            plugin = next((p for p in self._packages if p["name"] == name), None)
            if not plugin:
                self.uninstall_finished.emit(json.dumps({"name": name, "ok": False, "error": "not found"}))
                return
            latest = _latest_version(plugin)
            if not latest:
                self.uninstall_finished.emit(json.dumps({"name": name, "ok": False, "error": "no versions"}))
                return
            try:
                dist_name = _package_name_from_pip(latest["pip"])
                if not dist_name:
                    self.uninstall_finished.emit(json.dumps({"name": name, "ok": False, "error": "cannot determine package name"}))
                    return
                cmd = uv_command("pip", "uninstall", dist_name)
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                _remove_installed_package(name)
                self.uninstall_finished.emit(json.dumps({"name": name, "ok": True}))
            except Exception as e:
                log.error(f"Failed to uninstall {name}: {e}")
                self.uninstall_finished.emit(json.dumps({"name": name, "ok": False, "error": str(e)}))

        threading.Thread(target=_uninstall, daemon=True).start()
