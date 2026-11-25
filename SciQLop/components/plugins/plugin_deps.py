"""Collect python_dependencies from enabled plugins across plugin folders."""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def _is_bundled(folder: Path) -> bool:
    """The bundled plugins' deps come with sciqlop[all] of the workspace's own SciQLop. Read here, they
    would be the launcher's copy, maybe older: a stale launcher wrote cocat-rs 0.11 into a workspace
    whose SciQLop needed 0.12 (tests/test_bundled_plugin_pins.py keeps [all] and plugin.json equal)."""
    from SciQLop.components.plugins.backend import folders
    return folder.resolve() == Path(folders.bundled_plugins_folder()).resolve()


def collect_plugin_dependencies(
    plugin_folders: list[Path | str],
    enabled_plugins: list[str],
    workspace_plugins_add: list[str] | None = None,
    workspace_plugins_remove: list[str] | None = None,
) -> list[str]:
    """Collect python_dependencies from enabled plugins, applying workspace overrides.

    Args:
        plugin_folders: Directories to scan for plugin subdirectories.
        enabled_plugins: Base list of enabled plugin names.
        workspace_plugins_add: Additional plugins to enable (workspace override).
        workspace_plugins_remove: Plugins to disable (workspace override).

    Returns:
        Flat list of dependency requirement strings from all effective plugins.
    """
    # Compute effective plugin set
    effective = list(enabled_plugins)
    if workspace_plugins_add:
        for p in workspace_plugins_add:
            if p not in effective:
                effective.append(p)
    if workspace_plugins_remove:
        effective = [p for p in effective if p not in workspace_plugins_remove]

    all_deps: list[str] = []

    for folder in plugin_folders:
        folder = Path(folder)
        if not folder.is_dir() or _is_bundled(folder):
            continue
        for plugin_name in effective:
            plugin_json_path = folder / plugin_name / "plugin.json"
            if not plugin_json_path.is_file():
                continue
            try:
                with open(plugin_json_path, "r") as f:
                    data = json.load(f)
                deps = data.get("python_dependencies", [])
                if isinstance(deps, list):
                    all_deps.extend(deps)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Skipping %s: %s", plugin_json_path, e)
                continue

    return all_deps
