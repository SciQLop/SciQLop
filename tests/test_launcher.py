# tests/test_launcher.py
import os
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path
from SciQLop.sciqlop_launcher import (
    parse_args, resolve_workspace_dir, _read_switch_target,
    check_xcb_cursor, _most_recently_used_workspace,
    EXIT_RESTART, EXIT_SWITCH_WORKSPACE, READY_FILE_ENV,
)
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

MODULE = "SciQLop.sciqlop_launcher"


def test_parse_args_default():
    args = parse_args([])
    assert args.workspace is None
    assert args.sciqlop_file is None


def test_parse_args_workspace_name():
    args = parse_args(["--workspace", "my-study"])
    assert args.workspace == "my-study"


def test_parse_args_workspace_short():
    args = parse_args(["-w", "my-study"])
    assert args.workspace == "my-study"


def test_parse_args_sciqlop_file():
    args = parse_args(["study.sciqlop"])
    assert args.sciqlop_file == "study.sciqlop"


@patch(f"{MODULE}.SciQLopWorkspacesSettings", create=True)
def test_resolve_default_workspace(MockSettings):
    MockSettings.return_value.workspaces_dir = "/fake/workspaces"
    MockSettings.return_value.reopen_last_workspace = False
    # We need to inject the mock into the function's import
    with patch.dict("sys.modules", {
        "SciQLop.components.workspaces": MagicMock(),
        "SciQLop.components.workspaces.backend": MagicMock(),
        "SciQLop.components.workspaces.backend.settings": MagicMock(
            SciQLopWorkspacesSettings=MockSettings
        ),
    }):
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=None)
    assert d == Path("/fake/workspaces/default")


@patch(f"{MODULE}.SciQLopWorkspacesSettings", create=True)
def test_resolve_named_workspace(MockSettings):
    MockSettings.return_value.workspaces_dir = "/fake/workspaces"
    with patch.dict("sys.modules", {
        "SciQLop.components.workspaces": MagicMock(),
        "SciQLop.components.workspaces.backend": MagicMock(),
        "SciQLop.components.workspaces.backend.settings": MagicMock(
            SciQLopWorkspacesSettings=MockSettings
        ),
    }):
        d = resolve_workspace_dir(workspace_name="my-study", sciqlop_file=None)
    assert d == Path("/fake/workspaces/my-study")


@patch(f"{MODULE}.SciQLopWorkspacesSettings", create=True)
def test_resolve_absolute_path(MockSettings):
    MockSettings.return_value.workspaces_dir = "/fake/workspaces"
    with patch.dict("sys.modules", {
        "SciQLop.components.workspaces": MagicMock(),
        "SciQLop.components.workspaces.backend": MagicMock(),
        "SciQLop.components.workspaces.backend.settings": MagicMock(
            SciQLopWorkspacesSettings=MockSettings
        ),
    }):
        d = resolve_workspace_dir(workspace_name="/tmp/my-ws", sciqlop_file=None)
    assert d == Path("/tmp/my-ws")


def test_resolve_sciqlop_file():
    mock_settings_cls = MagicMock()
    with patch.dict("sys.modules", {
        "SciQLop.components.workspaces": MagicMock(),
        "SciQLop.components.workspaces.backend": MagicMock(),
        "SciQLop.components.workspaces.backend.settings": MagicMock(
            SciQLopWorkspacesSettings=mock_settings_cls
        ),
    }):
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file="/path/to/workspace.sciqlop")
    assert d == Path("/path/to")


def test_resolve_sciqlop_archive(tmp_path):
    """Opening a .sciqlop-archive extracts and returns the workspace dir."""
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    from SciQLop.components.workspaces.backend.workspace_archive import export_workspace

    # Create a source workspace and archive it
    src = tmp_path / "src"
    src.mkdir()
    WorkspaceManifest(name="Archived").save(src / "workspace.sciqlop")
    archive = tmp_path / "test.sciqlop-archive"
    export_workspace(src, archive)

    mock_settings_cls = MagicMock()
    mock_settings_cls.return_value.workspaces_dir = str(tmp_path / "workspaces")
    with patch.dict("sys.modules", {
        "SciQLop.components.workspaces": MagicMock(),
        "SciQLop.components.workspaces.backend": MagicMock(),
        "SciQLop.components.workspaces.backend.settings": MagicMock(
            SciQLopWorkspacesSettings=mock_settings_cls
        ),
    }):
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=str(archive))
    assert d.name == "test"
    assert (d / "workspace.sciqlop").exists()


def test_read_switch_target(tmp_path):
    (tmp_path / ".sciqlop_switch_target").write_text("other-workspace\n")
    target = _read_switch_target(tmp_path)
    assert target == "other-workspace"
    assert not (tmp_path / ".sciqlop_switch_target").exists()


def test_read_switch_target_missing(tmp_path):
    target = _read_switch_target(tmp_path)
    assert target is None


# --- _prepare_on_worker_thread tests ---
#
# The splash froze ("stuck") because workspace preparation ran synchronously on
# the launcher's GUI thread, starving the Qt event loop during uv's silent
# stretches. Prep must run on a worker thread while the GUI loop keeps spinning.


def test_prepare_on_worker_thread_keeps_event_loop_alive(qapp):
    """While a slow prepare_fn runs, a main-thread timer must still fire — proof
    the GUI event loop is not blocked (so the splash keeps repainting)."""
    import time
    from PySide6.QtCore import QTimer
    from SciQLop.sciqlop_launcher import _prepare_on_worker_thread

    probe = []
    QTimer.singleShot(30, lambda: probe.append("fired"))

    def slow_prepare(on_output):
        on_output("resolving packages…")
        time.sleep(0.25)  # blocks the WORKER thread, not the GUI thread
        return Path("/usr/bin/python-from-prep")

    details = []
    py, err = _prepare_on_worker_thread(slow_prepare, Path("/default/py"), details.append)

    assert err is None
    assert py == Path("/usr/bin/python-from-prep")  # result propagated
    assert probe == ["fired"]                       # loop ran during the 0.25s prep
    assert "resolving packages…" in [d.strip() for d in details]  # output delivered


def test_prepare_on_worker_thread_captures_errors(qapp):
    """A crash in prepare_fn is returned as a traceback, not raised, and the
    python path falls back to the default."""
    from SciQLop.sciqlop_launcher import _prepare_on_worker_thread

    def failing_prepare(on_output):
        raise RuntimeError("uv blew up")

    py, err = _prepare_on_worker_thread(failing_prepare, Path("/default/py"), lambda _: None)

    assert py == Path("/default/py")
    assert err is not None and "uv blew up" in err


# --- check_xcb_cursor tests ---

@patch("SciQLop.sciqlop_launcher.platform.system", return_value="Linux")
@patch("SciQLop.sciqlop_launcher.ctypes.cdll.LoadLibrary")
def test_xcb_cursor_returns_none_when_available(mock_load, mock_sys):
    assert check_xcb_cursor() is None


@patch("SciQLop.sciqlop_launcher.platform.system", return_value="Linux")
@patch("SciQLop.sciqlop_launcher.ctypes.cdll.LoadLibrary", side_effect=OSError)
def test_xcb_cursor_returns_warning_when_missing(mock_load, mock_sys):
    result = check_xcb_cursor()
    assert result is not None
    assert "xcb-cursor" in result.lower()


@patch("SciQLop.sciqlop_launcher.platform.system", return_value="Windows")
def test_xcb_cursor_returns_none_on_non_linux(mock_sys):
    assert check_xcb_cursor() is None


# --- _most_recently_used_workspace tests ---


def _make_ws(root, name, used_mtime):
    d = root / name
    d.mkdir(parents=True)
    (d / "workspace.sciqlop").write_text('[workspace]\nname = "%s"\n' % name)
    WorkspaceManifest.touch_last_used(d)
    os.utime(d / ".last_used", (used_mtime, used_mtime))
    return d


def test_most_recent_picks_newest_marker(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    _make_ws(root, "old", used_mtime=1_000_000)
    newest = _make_ws(root, "fresh", used_mtime=2_000_000)
    assert _most_recently_used_workspace(root) == newest


def test_most_recent_ignores_dirs_without_manifest(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    (root / "not-a-ws").mkdir()
    real = _make_ws(root, "real", used_mtime=1_000_000)
    assert _most_recently_used_workspace(root) == real


def test_most_recent_none_when_no_markers(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    d = root / "ws"
    d.mkdir()
    (d / "workspace.sciqlop").write_text('[workspace]\nname = "ws"\n')
    assert _most_recently_used_workspace(root) is None


def test_most_recent_none_when_root_missing(tmp_path):
    assert _most_recently_used_workspace(tmp_path / "does-not-exist") is None


# --- resolve_workspace_dir resume-last-used tests ---


def _settings_module(workspaces_dir, reopen):
    inst = MagicMock()
    inst.workspaces_dir = str(workspaces_dir)
    inst.reopen_last_workspace = reopen
    cls = MagicMock(return_value=inst)
    return patch.dict("sys.modules", {
        "SciQLop.components.workspaces.backend.settings": MagicMock(
            SciQLopWorkspacesSettings=cls
        ),
    })


def test_resolve_resumes_last_when_enabled(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    _make_ws(root, "old", used_mtime=1_000_000)
    newest = _make_ws(root, "fresh", used_mtime=2_000_000)
    with _settings_module(root, reopen=True):
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=None)
    assert d == newest


def test_resolve_default_when_reopen_disabled(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    _make_ws(root, "fresh", used_mtime=2_000_000)
    with _settings_module(root, reopen=False):
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=None)
    assert d == root / "default"


def test_resolve_default_when_no_history(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    with _settings_module(root, reopen=True):
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=None)
    assert d == root / "default"


def test_resolve_explicit_name_overrides_reopen(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    _make_ws(root, "fresh", used_mtime=2_000_000)
    with _settings_module(root, reopen=True):
        d = resolve_workspace_dir(workspace_name="picked", sciqlop_file=None)
    assert d == root / "picked"


def test_resolve_sciqlop_file_overrides_reopen(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    _make_ws(root, "fresh", used_mtime=2_000_000)
    ws_file = tmp_path / "elsewhere" / "workspace.sciqlop"
    ws_file.parent.mkdir()
    ws_file.write_text('[workspace]\nname = "elsewhere"\n')
    with _settings_module(root, reopen=True):
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=str(ws_file))
    assert d == ws_file.parent


# --- _prepare_workspace_dev: host-provided (SciQLop) filtering ---
def test_prepare_workspace_dev_strips_host_sciqlop_from_install(tmp_path):
    """A plugin declaring SciQLop>=0.13.0 must install against a 0.13.0.dev0
    host. The dev pip-install path must drop SciQLop itself (provided by the
    host via --system-site-packages); otherwise uv resolves it from PyPI, finds
    only <=0.12.0, and the whole plugin/workspace install fails."""
    from SciQLop.sciqlop_launcher import _prepare_workspace_dev
    from SciQLop.components.workspaces.backend.workspace_project import (
        _extract_package_name,
    )

    captured = {}

    def fake_run_uv(cmd, on_output=None, **kw):
        captured["cmd"] = cmd

    with patch("SciQLop.components.plugins.plugin_deps.collect_plugin_dependencies",
               return_value=["SciQLop>=0.13.0,<0.14.0", "matplotlib>=3.8"]), \
         patch("SciQLop.components.workspaces.backend.workspace_setup.get_globally_enabled_plugins",
               return_value=[]), \
         patch("SciQLop.components.workspaces.backend.workspace_setup.get_plugin_folders",
               return_value=[]), \
         patch("SciQLop.components.workspaces.backend.workspace_migration.migrate_workspace"), \
         patch("SciQLop.components.workspaces.backend.workspace_venv._run_uv", fake_run_uv):
        _prepare_workspace_dev(tmp_path)

    cmd = captured["cmd"]
    install_args = cmd[cmd.index("install") + 1:]
    assert not any(_extract_package_name(p) == "sciqlop" for p in install_args), cmd
    assert "matplotlib>=3.8" in install_args


def test_prepare_workspace_dev_repairs_lab_assets_on_dev_venv(tmp_path):
    """Unlike the prod path (workspace_setup.prepare_workspace), dev mode never
    creates a workspace .venv — it runs JupyterLab straight out of the dev base
    venv (sys.executable's venv). That venv accumulates the exact same orphan
    empty dirs / gutted jupyterlab-js data files from routine `uv sync` churn
    (see jupyterlab-dual-ownership-breakage), but nothing ever heals it because
    repair_lab_assets() was only wired into the prod prepare_workspace() call.
    Dev mode must call it too, against sys.executable's venv dir."""
    from SciQLop.sciqlop_launcher import _prepare_workspace_dev

    captured = {}

    def fake_repair(venv_dir, on_output=None):
        captured["venv_dir"] = venv_dir

    expected_venv_dir = Path(sys.executable).parent.parent

    with patch("SciQLop.components.plugins.plugin_deps.collect_plugin_dependencies",
               return_value=[]), \
         patch("SciQLop.components.workspaces.backend.workspace_setup.get_globally_enabled_plugins",
               return_value=[]), \
         patch("SciQLop.components.workspaces.backend.workspace_setup.get_plugin_folders",
               return_value=[]), \
         patch("SciQLop.components.workspaces.backend.workspace_migration.migrate_workspace"), \
         patch("SciQLop.components.workspaces.backend.lab_assets.repair_lab_assets", fake_repair):
        _prepare_workspace_dev(tmp_path)

    assert captured.get("venv_dir") == expected_venv_dir
