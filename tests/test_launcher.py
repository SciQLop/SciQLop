# tests/test_launcher.py
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
from SciQLop.sciqlop_launcher import (
    parse_args, resolve_workspace_dir, _read_switch_target,
    check_xcb_cursor,
    EXIT_RESTART, EXIT_SWITCH_WORKSPACE, READY_FILE_ENV,
)

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
