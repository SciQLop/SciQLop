"""Tests for the workspace lab-assets self-heal.

Reproduces the field breakage: real ``jupyterlab`` and ``jupyterlab-js`` own
the same ``share/jupyter/lab`` paths; uninstalling one (an upgrade, a manifest
change, a sync prune) deletes files the other's RECORD still claims, and
leaves orphan empty dirs that 500 the lab settings API.
"""

from pathlib import Path
from unittest.mock import patch

from SciQLop.components.workspaces.backend.lab_assets import repair_lab_assets

MODULE = "SciQLop.components.workspaces.backend.lab_assets"

_RECORD_DATA_FILES = [
    "../../../share/jupyter/lab/static/main.0a8b.js",
    "../../../share/jupyter/lab/static/1096.dd4c.js",
    "../../../share/jupyter/lab/schemas/@jupyterlab/apputils-extension/package.json.orig",
    "../../../share/jupyter/lab/themes/@jupyterlab/theme-light-extension/index.css",
]


def make_venv(tmp_path: Path, *, version: str = "4.5.5") -> Path:
    venv = tmp_path / ".venv"
    site = venv / "lib" / "python3.13" / "site-packages"
    dist_info = site / f"jupyterlab_js-{version}.dist-info"
    dist_info.mkdir(parents=True)
    lines = [f"{rel},sha256=x,1" for rel in _RECORD_DATA_FILES]
    lines.append("jupyterlab_js/__init__.py,sha256=x,1")
    (dist_info / "RECORD").write_text("\n".join(lines) + "\n")
    for rel in _RECORD_DATA_FILES:
        target = (site / rel).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
    (site / "jupyterlab_js").mkdir()
    (site / "jupyterlab_js" / "__init__.py").write_text("")
    return venv


class TestIntactVenv:
    def test_no_reinstall_when_all_files_present(self, tmp_path):
        venv = make_venv(tmp_path)
        with patch(f"{MODULE}._run_uv") as run:
            assert repair_lab_assets(venv) is False
        run.assert_not_called()


class TestGuttedDataFiles:
    def test_reinstalls_when_record_files_missing(self, tmp_path):
        venv = make_venv(tmp_path)
        (venv / "share/jupyter/lab/static/1096.dd4c.js").unlink()
        with patch(f"{MODULE}._run_uv") as run, \
                patch(f"{MODULE}.uv_command", side_effect=lambda *a: ["uv", *a]) as cmd:
            assert repair_lab_assets(venv) is True
        run.assert_called_once()
        args = cmd.call_args.args
        assert "--force-reinstall" in args
        assert "--no-deps" in args
        assert "jupyterlab-js==4.5.5" in args
        assert str(venv / "bin" / "python") in args

    def test_reinstall_failure_does_not_raise(self, tmp_path):
        venv = make_venv(tmp_path)
        (venv / "share/jupyter/lab/static/main.0a8b.js").unlink()
        with patch(f"{MODULE}._run_uv", side_effect=RuntimeError("offline")):
            repair_lab_assets(venv)  # must not propagate — launcher path


class TestOrphanEmptyDirs:
    def test_prunes_empty_schema_and_extension_dirs(self, tmp_path):
        venv = make_venv(tmp_path)
        orphan_schema = venv / "share/jupyter/lab/schemas/@jupyter-notebook/tree-extension"
        orphan_ext = venv / "share/jupyter/labextensions/jupyter-matplotlib/static"
        orphan_schema.mkdir(parents=True)
        orphan_ext.mkdir(parents=True)
        with patch(f"{MODULE}._run_uv"):
            assert repair_lab_assets(venv) is True
        assert not orphan_schema.exists()
        assert not (venv / "share/jupyter/labextensions/jupyter-matplotlib").exists()

    def test_keeps_populated_dirs(self, tmp_path):
        venv = make_venv(tmp_path)
        healthy = venv / "share/jupyter/labextensions/@jupyter-widgets/jupyterlab-manager"
        healthy.mkdir(parents=True)
        (healthy / "package.json").write_text("{}")
        with patch(f"{MODULE}._run_uv"):
            repair_lab_assets(venv)
        assert (healthy / "package.json").exists()


class TestNoDistInfo:
    def test_noop_without_jupyterlab_js(self, tmp_path):
        venv = tmp_path / ".venv"
        (venv / "lib" / "python3.13" / "site-packages").mkdir(parents=True)
        with patch(f"{MODULE}._run_uv") as run:
            assert repair_lab_assets(venv) is False
        run.assert_not_called()

    def test_noop_on_missing_venv(self, tmp_path):
        assert repair_lab_assets(tmp_path / "nope") is False


class TestWindowsLayout:
    def test_finds_dist_info_under_capital_lib(self, tmp_path):
        venv = tmp_path / ".venv"
        site = venv / "Lib" / "site-packages"
        dist_info = site / "jupyterlab_js-4.5.5.dist-info"
        dist_info.mkdir(parents=True)
        rel = "../../share/jupyter/lab/static/main.js"
        (dist_info / "RECORD").write_text(f"{rel},sha256=x,1\n")
        with patch(f"{MODULE}._run_uv") as run, \
                patch(f"{MODULE}.uv_command", side_effect=lambda *a: ["uv", *a]):
            assert repair_lab_assets(venv) is True
        run.assert_called_once()
