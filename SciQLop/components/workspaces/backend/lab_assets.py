"""Self-heal for the embedded JupyterLab's data files in workspace venvs.

Historically workspace venvs installed both the real ``jupyterlab`` package
and ``jupyterlab-js`` (via jupyqt → jupyverse). Both ship the same files
under ``share/jupyter/lab``, and uv's uninstall removes every path in the
removed dist's RECORD without refcounting — so removing or upgrading either
one guts the other's data files and leaves orphan empty directories that
make the lab settings API return 500. This module detects both kinds of
damage after a workspace sync and repairs them.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from pathlib import Path

from SciQLop.components.workspaces.backend.uv import uv_command
from SciQLop.components.workspaces.backend.workspace_venv import _run_uv

log = logging.getLogger(__name__)

_DIST_INFO_RE = re.compile(r"jupyterlab_js-(?P<version>[^-]+)\.dist-info$")


def _site_packages_dirs(venv_dir: Path) -> list[Path]:
    return [
        p for p in (
            *venv_dir.glob("lib/python*/site-packages"),
            venv_dir / "Lib" / "site-packages",
        )
        if p.is_dir()
    ]


def _find_jupyterlab_js_dist_info(venv_dir: Path) -> Path | None:
    for site in _site_packages_dirs(venv_dir):
        for entry in site.glob("jupyterlab_js-*.dist-info"):
            if _DIST_INFO_RE.match(entry.name):
                return entry
    return None


def _missing_data_files(dist_info: Path) -> list[Path]:
    site = dist_info.parent
    missing = []
    for line in (dist_info / "RECORD").read_text().splitlines():
        rel = line.split(",", 1)[0]
        if "share/jupyter/" not in rel:
            continue
        target = (site / rel).resolve()
        if not target.exists():
            missing.append(target)
    return missing


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _reinstall_jupyterlab_js(venv_dir: Path, version: str,
                             on_output: Callable[[str], None] | None) -> bool:
    cmd = uv_command(
        "pip", "install",
        "--python", str(_venv_python(venv_dir)),
        "--force-reinstall", "--no-deps",
        f"jupyterlab-js=={version}",
    )
    try:
        _run_uv(cmd, on_output)
    except Exception as exc:
        log.warning("jupyterlab-js repair failed (offline?): %s", exc)
        if on_output is not None:
            on_output(f"JupyterLab assets repair failed: {exc}")
        return False
    return True


def _prune_empty_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    removed = []
    dirs = sorted((p for p in root.rglob("*") if p.is_dir()),
                  key=lambda p: len(p.parts), reverse=True)
    for d in dirs:
        try:
            d.rmdir()
        except OSError:
            continue
        removed.append(d)
    return removed


def repair_lab_assets(venv_dir: Path | str,
                      on_output: Callable[[str], None] | None = None) -> bool:
    """Verify and repair the venv's JupyterLab data files. Never raises.

    Returns True when any repair action was taken.
    """
    venv_dir = Path(venv_dir)
    repaired = False

    dist_info = _find_jupyterlab_js_dist_info(venv_dir)
    if dist_info is not None:
        missing = _missing_data_files(dist_info)
        if missing:
            version = _DIST_INFO_RE.match(dist_info.name)["version"]
            msg = (f"JupyterLab assets damaged ({len(missing)} files missing) — "
                   f"reinstalling jupyterlab-js {version}")
            log.warning(msg)
            if on_output is not None:
                on_output(msg)
            repaired = _reinstall_jupyterlab_js(venv_dir, version, on_output) or repaired

    orphans = _prune_empty_dirs(venv_dir / "share" / "jupyter")
    if orphans:
        log.info("Pruned %d orphan empty dirs under share/jupyter", len(orphans))
        repaired = True

    return repaired
