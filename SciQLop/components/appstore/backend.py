from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from importlib.metadata import PackageNotFoundError, distribution

import packaging.version

from PySide6.QtCore import QObject, Signal, Slot

from SciQLop.components.plugins.plugin_registry import (
    DEFAULT_STORE_URL,
    fetch_index as _fetch_index,
    filter_packages as _filter_packages,
    latest_version as _latest_version,
    package_name_from_pip as _package_name_from_pip,
)
from SciQLop.components.plugins.plugin_registry import is_compatible as _is_compatible  # noqa: F401  re-exported for tests
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.components.workspaces.backend.uv import error_detail, uv_command
from SciQLop.components.workspaces.backend.live_install import guarded_install

log = getLogger(__name__)


def _installed_version(package_name: str) -> str | None:
    """Return the installed version of a package, or None."""
    try:
        return distribution(package_name).version
    except PackageNotFoundError:
        return None


def _is_newer(candidate: str, installed: str) -> bool:
    try:
        return packaging.version.parse(candidate) > packaging.version.parse(installed)
    except packaging.version.InvalidVersion:
        return False


def available_updates(packages: list[dict]) -> list[dict]:
    """Installed store packages with a newer compatible version, as the store's
    Updates page lists them. *packages* is already filtered to compatible
    versions (``filter_packages``)."""
    updates = []
    for pkg in packages:
        latest = _latest_version(pkg)
        dist_name = _package_name_from_pip(latest["pip"]) if latest else None
        installed = _installed_version(dist_name) if dist_name else None
        if installed and _is_newer(latest["version"], installed):
            updates.append({"name": pkg["name"], "installed": installed, "latest": latest["version"]})
    return updates


def _uv_uninstall_cmd(dist_name: str) -> list[str]:
    return uv_command("pip", "uninstall", "--native-tls", "--python", sys.executable, "--", dist_name)


def _save_installed_package(pip_spec: str, dist_name: str) -> None:
    from SciQLop.components.plugins.backend.settings import (
        InstalledPackage, SciQLopPluginsSettings, canonical_package_name,
    )
    with SciQLopPluginsSettings() as settings:
        settings.installed_packages[canonical_package_name(dist_name)] = InstalledPackage(
            pip=pip_spec, name=dist_name)


def _installed_spec(dist_name: str) -> str | None:
    """The pip spec saved for *dist_name* in the plugin settings, if any."""
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings, canonical_package_name
    entry = SciQLopPluginsSettings().installed_packages.get(canonical_package_name(dist_name))
    return entry.pip if entry is not None else None


def _staging_workspace() -> Path | None:
    """The workspace whose live venv slot runs this process, or None (e.g. a dev checkout,
    which runs from its own venv): only then can an update go to the other slot."""
    from SciQLop.components.workspaces.backend.venv_slots import active_venv_dir
    workspace = os.environ.get("SCIQLOP_WORKSPACE_DIR")
    if not workspace:
        return None
    running_from_live_slot = Path(sys.prefix).resolve() == active_venv_dir(workspace).resolve()
    return Path(workspace) if running_from_live_slot else None


def _stage_update(workspace_dir: Path, pip_spec: str, dist_name: str) -> None:
    """Build the update into the workspace's other venv slot, live after a restart.

    The running venv is never touched (Windows can't replace a loaded file).
    On failure the previously saved spec is put back, so nothing changes.
    """
    from SciQLop.components.workspaces.backend import workspace_setup
    previous = _installed_spec(dist_name)
    _save_installed_package(pip_spec, dist_name)
    try:
        workspace_setup.stage_environment(workspace_dir)
    except Exception:
        if previous is None:
            _remove_installed_package(dist_name)
        else:
            _save_installed_package(previous, dist_name)
        raise


def _remove_installed_package(dist_name: str) -> None:
    """Drop the entry for *dist_name*, including one left under a legacy
    display-name key (its `.name` still canonicalises to *dist_name*)."""
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings, canonical_package_name
    canonical = canonical_package_name(dist_name)
    with SciQLopPluginsSettings() as settings:
        settings.installed_packages = {
            key: pkg for key, pkg in settings.installed_packages.items()
            if canonical_package_name(pkg.name) != canonical
        }


def _incompatibility_reason(ep) -> str:
    """Human-readable reason a gated entry point's host compat check failed."""
    from SciQLop.components.plugins.compat import host_version, sciqlop_specifier

    requires = ep.dist.requires if ep.dist else None
    spec = sciqlop_specifier(requires or []) or "(any)"
    return f"needs SciQLop {spec}, this workspace has {host_version()}"


def _try_load_plugin(dist_name: str) -> str | None:
    """Attempt to hot-load a newly installed entry-point plugin.

    Returns ``None`` when a matching entry point loaded (or there was
    nothing to hot-load: no matching entry point yet, or the main window
    isn't up), or a short reason string when the host compat gate refused
    to load it -- I1: the caller must not report a gated install as a plain
    success.
    """
    import importlib.metadata
    from SciQLop.components.plugins.backend.loader.loader import (
        ENTRY_POINT_GROUP, entry_point_host_compatible, load_one,
    )
    from SciQLop.components.plugins.backend.settings import (
        SciQLopPluginsSettings, PluginConfig, canonical_package_name,
    )
    from SciQLop.core.sciqlop_application import sciqlop_app

    main_window = sciqlop_app().main_window
    if main_window is None:
        return None

    canonical_dist_name = canonical_package_name(dist_name)
    for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP):
        try:
            ep_dist = ep.dist.name if ep.dist else None
        except Exception:
            ep_dist = None
        if ep_dist and canonical_package_name(ep_dist) == canonical_dist_name:
            with SciQLopPluginsSettings() as settings:
                if ep.name not in settings.plugins:
                    settings.plugins[ep.name] = PluginConfig()
            if not entry_point_host_compatible(ep):
                return _incompatibility_reason(ep)
            load_one(None, ep.name, main_window, {ep.name: ep})
            log.info(f"Hot-loaded plugin {ep.name} from {dist_name}")
    return None


class AppStoreBackend(QObject):
    """Python backend exposed to the AppStore page via QWebChannel."""

    packages_ready = Signal(str)
    install_finished = Signal(str)
    uninstall_finished = Signal(str)
    _hot_load_requested = Signal(str, str, str, bool)  # dist_name, name, version, was_installed

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._packages: list[dict] = []
        self._hot_load_requested.connect(self._do_hot_load)

    @Slot(str, str, str, bool)
    def _do_hot_load(self, dist_name: str, name: str, version: str, was_installed: bool) -> None:
        """Hot-load *dist_name* on the GUI thread, then report the outcome.

        Runs after the install itself (see ``install_package``'s worker
        thread, which only saves the package and hands off here) so
        ``install_finished`` can carry whether the compat gate actually let
        it load (I1) instead of reporting a gated install as a plain
        success.
        """
        if was_installed:
            # The previous version is still imported; loading again would register it twice.
            self.install_finished.emit(json.dumps({"name": name, "ok": True, "version": version,
                                                   "loaded": True, "restart_required": True}))
            return
        reason = _try_load_plugin(dist_name)
        payload = {"name": name, "ok": True, "version": version, "loaded": reason is None,
                   "restart_required": False}
        if reason is not None:
            payload["reason"] = reason
        self.install_finished.emit(json.dumps(payload))

    @Slot()
    def restart_sciqlop(self) -> None:
        from SciQLop.sciqlop_app import restart_sciqlop
        restart_sciqlop()

    @Slot()
    def fetch_packages(self) -> None:
        def _fetch():
            try:
                self._packages = _filter_packages(_fetch_index(DEFAULT_STORE_URL))
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

    def _install_one(self, name: str) -> None:
        """Install or update *name*; runs on a worker thread."""
        from SciQLop.components.plugins.backend.settings import canonical_package_name

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
            dist_name = _package_name_from_pip(pip_spec) or canonical_package_name(name)
            was_installed = _installed_version(dist_name) is not None
            if was_installed and (workspace := _staging_workspace()):
                _stage_update(workspace, pip_spec, dist_name)
                self.install_finished.emit(json.dumps({
                    "name": name, "ok": True, "version": latest["version"],
                    "loaded": True, "restart_required": True}))
                return
            result = guarded_install([pip_spec])
            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, "uv pip install", result.stdout, result.stderr)
            _save_installed_package(pip_spec, dist_name)
            # install_finished is emitted by _do_hot_load, on the GUI
            # thread, once the hot-load attempt itself is known -- not
            # here, or a gated wheel would be reported ok:true before
            # the compat gate ever ran (I1).
            self._hot_load_requested.emit(dist_name, name, latest["version"], was_installed)
        except Exception as e:
            detail = error_detail(e)
            log.error(f"Failed to install {name}: {detail}")
            self.install_finished.emit(json.dumps({"name": name, "ok": False, "error": detail}))

    @Slot(str)
    def install_package(self, name: str) -> None:
        threading.Thread(target=self._install_one, args=(name,), daemon=True).start()

    @Slot(str)
    def update_packages(self, names_json: str) -> None:
        """Update several packages one after another, so a package that fails
        to resolve does not block the others; each reports install_finished."""
        names = json.loads(names_json)

        def _update_all():
            for name in names:
                self._install_one(name)

        threading.Thread(target=_update_all, daemon=True).start()

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
                subprocess.run(_uv_uninstall_cmd(dist_name), check=True, capture_output=True, text=True)
                _remove_installed_package(dist_name)
                self.uninstall_finished.emit(json.dumps({"name": name, "ok": True, "restart_required": True}))
            except Exception as e:
                detail = error_detail(e)
                log.error(f"Failed to uninstall {name}: {detail}")
                self.uninstall_finished.emit(json.dumps({"name": name, "ok": False, "error": detail}))

        threading.Thread(target=_uninstall, daemon=True).start()
