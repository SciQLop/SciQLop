# tests/test_launcher.py
import os
import sys
import time
import tomllib
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

from SciQLop.sciqlop_launcher import (
    parse_args, resolve_workspace_dir, _read_switch_target,
    check_xcb_cursor, _most_recently_used_workspace,
    EXIT_RESTART, EXIT_SWITCH_WORKSPACE, READY_FILE_ENV, SWITCH_HANDOFF_FILE_ENV,
    _switch_handoff_path, main,
)
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

MODULE = "SciQLop.sciqlop_launcher"


def _wait_for(predicate, timeout=2.0):
    """Poll until predicate() is true, for asserting on background-thread work
    (the log/echo drain threads in _spawn_app_logged) without a blind sleep."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


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


def test_parse_args_sciqlop_version_ignored():
    args = parse_args(["--sciqlop-version", "1.2.3"])
    assert args.workspace is None


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


def test_prepare_workspace_dev_pip_install_uses_native_tls(tmp_path):
    """L-w6: the venv create/sync paths already pass --native-tls (to trust a
    corporate MITM proxy's root CA); the dev pip-install path must too."""
    from SciQLop.sciqlop_launcher import _prepare_workspace_dev

    captured = {}

    def fake_run_uv(cmd, on_output=None, **kw):
        captured["cmd"] = cmd

    with patch("SciQLop.components.plugins.plugin_deps.collect_plugin_dependencies",
               return_value=["matplotlib>=3.8"]), \
         patch("SciQLop.components.workspaces.backend.workspace_setup.get_globally_enabled_plugins",
               return_value=[]), \
         patch("SciQLop.components.workspaces.backend.workspace_setup.get_plugin_folders",
               return_value=[]), \
         patch("SciQLop.components.workspaces.backend.workspace_migration.migrate_workspace"), \
         patch("SciQLop.components.workspaces.backend.workspace_venv._run_uv", fake_run_uv):
        _prepare_workspace_dev(tmp_path)

    assert "--native-tls" in captured["cmd"]


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


# --- H5: _qt_available must also check for a usable display on Linux ---

@patch(f"{MODULE}.platform.system", return_value="Linux")
def test_qt_available_false_when_pyside6_missing(mock_sys, monkeypatch):
    from SciQLop.sciqlop_launcher import _qt_available
    monkeypatch.setitem(sys.modules, "PySide6", None)
    assert _qt_available() is False


@patch(f"{MODULE}.platform.system", return_value="Linux")
def test_qt_available_false_when_headless_linux(mock_sys, monkeypatch):
    from SciQLop.sciqlop_launcher import _qt_available
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    assert _qt_available() is False


@patch(f"{MODULE}.platform.system", return_value="Linux")
def test_qt_available_true_linux_with_display(mock_sys, monkeypatch):
    from SciQLop.sciqlop_launcher import _qt_available
    monkeypatch.setenv("DISPLAY", ":0")
    assert _qt_available() is True


@patch(f"{MODULE}.platform.system", return_value="Linux")
def test_qt_available_true_linux_with_qt_qpa_platform_only(mock_sys, monkeypatch):
    from SciQLop.sciqlop_launcher import _qt_available
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert _qt_available() is True


@patch(f"{MODULE}.platform.system", return_value="Windows")
def test_qt_available_true_non_linux_without_display_env(mock_sys, monkeypatch):
    from SciQLop.sciqlop_launcher import _qt_available
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    assert _qt_available() is True


class _BrokenPySide6Finder:
    """L-p3: simulates a PySide6 install with missing shared libraries — the
    import raises OSError, not ImportError."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "PySide6" or fullname.startswith("PySide6."):
            raise OSError("libQt6Core.so.6: cannot open shared object file")
        return None


@patch(f"{MODULE}.platform.system", return_value="Linux")
def test_qt_available_false_when_pyside6_has_broken_shared_libs(mock_sys, monkeypatch):
    from SciQLop.sciqlop_launcher import _qt_available

    for name in [n for n in sys.modules if n == "PySide6" or n.startswith("PySide6.")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    finder = _BrokenPySide6Finder()
    sys.meta_path.insert(0, finder)
    try:
        assert _qt_available() is False
    finally:
        sys.meta_path.remove(finder)


# --- M15: an externally-provided ready file must force the console path ---

def test_choose_run_session_forces_console_when_ready_file_env_set(monkeypatch):
    from SciQLop.sciqlop_launcher import _choose_run_session, _run_on_console
    monkeypatch.setenv(READY_FILE_ENV, "/tmp/some-ready-file")
    with patch(f"{MODULE}._qt_available", return_value=True):
        assert _choose_run_session() is _run_on_console


def test_choose_run_session_uses_startup_window_when_qt_available(monkeypatch):
    from SciQLop.sciqlop_launcher import _choose_run_session, _run_with_startup_window
    monkeypatch.delenv(READY_FILE_ENV, raising=False)
    with patch(f"{MODULE}._qt_available", return_value=True):
        assert _choose_run_session() is _run_with_startup_window


def test_choose_run_session_falls_back_to_console_when_qt_unavailable(monkeypatch):
    from SciQLop.sciqlop_launcher import _choose_run_session, _run_on_console
    monkeypatch.delenv(READY_FILE_ENV, raising=False)
    with patch(f"{MODULE}._qt_available", return_value=False):
        assert _choose_run_session() is _run_on_console


# --- M9 / C3: workspace resolution failure must reach the console error
# surface (stderr + last-launch.log), and the return tuple's workspace_dir
# must be None ---

def test_run_on_console_resolution_failure_returns_1_and_logs(monkeypatch, tmp_path, capsys):
    from SciQLop.sciqlop_launcher import _run_on_console

    def _boom(workspace_name, sciqlop_file):
        raise RuntimeError("resolution exploded")

    log_path = tmp_path / "last-launch.log"
    monkeypatch.setattr(f"{MODULE}._apply_proxy_settings", lambda: None)
    monkeypatch.setattr(f"{MODULE}.resolve_workspace_dir", _boom)
    monkeypatch.setattr(f"{MODULE}._last_launch_log_path", lambda: log_path)

    exit_code, workspace_dir = _run_on_console(None, None)

    assert exit_code == 1
    assert workspace_dir is None
    captured = capsys.readouterr()
    assert "Workspace preparation failed" in captured.err
    assert "resolution exploded" in captured.err
    assert log_path.exists()
    assert "resolution exploded" in log_path.read_text()


def test_run_with_startup_window_resolution_failure_shows_error_and_returns_1(monkeypatch, qapp):
    """Mirrors the console-path test above: a resolver that raises must show
    the traceback in the startup window and return (1, None), instead of the
    exception escaping resolve_workspace_dir() unhandled (M9).

    StartupWindow is mocked out (there's nothing to visually verify here), and
    QApplication is mocked too so the except branch's real app.exec() call
    can't block the test — it's a MagicMock, so exec() just returns.
    """
    from SciQLop.sciqlop_launcher import _run_with_startup_window

    def _boom(workspace_name, sciqlop_file):
        raise RuntimeError("resolution exploded")

    fake_window = MagicMock()
    fake_app = MagicMock()
    fake_qapplication_cls = MagicMock()
    fake_qapplication_cls.instance.return_value = fake_app

    monkeypatch.setattr(f"{MODULE}._apply_proxy_settings", lambda: None)
    monkeypatch.setattr(f"{MODULE}.resolve_workspace_dir", _boom)
    monkeypatch.setattr(
        "SciQLop.components.startup.startup_window.StartupWindow",
        MagicMock(return_value=fake_window),
    )
    monkeypatch.setattr("PySide6.QtWidgets.QApplication", fake_qapplication_cls)

    exit_code, workspace_dir = _run_with_startup_window(None, None)

    assert exit_code == 1
    assert workspace_dir is None
    fake_window.show_error.assert_called_once()
    shown_message = fake_window.show_error.call_args[0][0]
    assert "resolution exploded" in shown_message
    fake_app.exec.assert_called_once()


# --- L12: resolve_workspace_dir must expand ~ ---

def test_resolve_workspace_dir_expands_user_in_workspaces_root(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    with _settings_module("~/sciqlop-workspaces", reopen=False):
        d = resolve_workspace_dir(workspace_name=None, sciqlop_file=None)
    assert d == tmp_path / "sciqlop-workspaces" / "default"


def test_resolve_workspace_dir_expands_user_in_workspace_name(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    with _settings_module(tmp_path / "workspaces", reopen=False):
        d = resolve_workspace_dir(workspace_name="~/x", sciqlop_file=None)
    assert d == tmp_path / "x"


# --- C3: _spawn_app_logged (Popen + drain-threads + last-launch.log) ---

class _FakePopen:
    """Stand-in for subprocess.Popen: fixed stdout/stderr lines, no real process."""

    def __init__(self, *args, **kwargs):
        self.stdout = ["hello out\n"]
        self.stderr = ["hello err\n"]
        self.returncode = 0

    def poll(self):
        return self.returncode

    def wait(self):
        return self.returncode


def test_spawn_app_logged_writes_log_and_captures_stderr(tmp_path, monkeypatch):
    from SciQLop.sciqlop_launcher import _spawn_app_logged

    log_path = tmp_path / "last-launch.log"
    monkeypatch.setattr(f"{MODULE}._last_launch_log_path", lambda: log_path)
    monkeypatch.setattr(f"{MODULE}.subprocess.Popen", _FakePopen)

    proc, stderr_lines, returned_log_path = _spawn_app_logged(Path("/usr/bin/python3"), {})

    assert returned_log_path == log_path
    assert _wait_for(lambda: log_path.exists() and "[err]" in log_path.read_text())
    assert stderr_lines == ["hello err\n"]
    content = log_path.read_text()
    assert "[out] hello out" in content
    assert "[err] hello err" in content


def test_spawn_app_logged_echoes_to_console_when_requested(tmp_path, monkeypatch, capsys):
    from SciQLop.sciqlop_launcher import _spawn_app_logged

    log_path = tmp_path / "last-launch.log"
    monkeypatch.setattr(f"{MODULE}._last_launch_log_path", lambda: log_path)
    monkeypatch.setattr(f"{MODULE}.subprocess.Popen", _FakePopen)

    _spawn_app_logged(Path("/usr/bin/python3"), {}, echo=True)

    assert _wait_for(lambda: log_path.exists() and "[err]" in log_path.read_text())
    captured = capsys.readouterr()
    assert "hello out" in captured.out
    assert "hello err" in captured.err


def test_spawn_app_logged_does_not_echo_by_default(tmp_path, monkeypatch, capsys):
    from SciQLop.sciqlop_launcher import _spawn_app_logged

    log_path = tmp_path / "last-launch.log"
    monkeypatch.setattr(f"{MODULE}._last_launch_log_path", lambda: log_path)
    monkeypatch.setattr(f"{MODULE}.subprocess.Popen", _FakePopen)

    _spawn_app_logged(Path("/usr/bin/python3"), {})

    assert _wait_for(lambda: log_path.exists() and "[err]" in log_path.read_text())
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_spawn_app_logged_passes_utf8_encoding_to_popen(tmp_path, monkeypatch):
    """L-p4: subprocess stdout/stderr must decode as UTF-8 with replacement,
    not the platform default, or a child process emitting non-ASCII output
    on a C-locale host can crash the drain threads."""
    from SciQLop.sciqlop_launcher import _spawn_app_logged

    log_path = tmp_path / "last-launch.log"
    monkeypatch.setattr(f"{MODULE}._last_launch_log_path", lambda: log_path)
    captured = {}

    class _CapturingPopen(_FakePopen):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(f"{MODULE}.subprocess.Popen", _CapturingPopen)

    _spawn_app_logged(Path("/usr/bin/python3"), {})

    assert captured.get("encoding") == "utf-8"
    assert captured.get("errors") == "replace"


def test_spawn_app_logged_closes_log_file_if_popen_raises(tmp_path, monkeypatch):
    """L-p4: a Popen failure (e.g. the workspace interpreter vanished) must
    not leak the already-opened last-launch.log file handle."""
    from SciQLop.sciqlop_launcher import _spawn_app_logged

    log_path = tmp_path / "last-launch.log"
    monkeypatch.setattr(f"{MODULE}._last_launch_log_path", lambda: log_path)
    fake_file = MagicMock()
    monkeypatch.setattr(f"{MODULE}.open", lambda *a, **k: fake_file, raising=False)

    def raising_popen(*a, **kw):
        raise FileNotFoundError("no such interpreter")

    monkeypatch.setattr(f"{MODULE}.subprocess.Popen", raising_popen)

    with pytest.raises(FileNotFoundError):
        _spawn_app_logged(Path("/usr/bin/python3"), {})

    fake_file.close.assert_called_once()


# --- C3: _run_on_console uses _spawn_app_logged, echoes, and reports a
# non-zero exit with a pointer to the log file ---

class _FakeFailingPopen(_FakePopen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.returncode = 3


def test_run_on_console_reports_nonzero_exit_with_log_pointer(monkeypatch, tmp_path, capsys):
    from SciQLop.sciqlop_launcher import _run_on_console

    workspace_dir = tmp_path / "ws"
    log_path = tmp_path / "last-launch.log"
    monkeypatch.setattr(f"{MODULE}._apply_proxy_settings", lambda: None)
    monkeypatch.setattr(f"{MODULE}.resolve_workspace_dir", lambda *a, **k: workspace_dir)
    monkeypatch.setattr(f"{MODULE}._is_editable_install", lambda: True)
    monkeypatch.setattr(f"{MODULE}._prepare_workspace_dev", lambda *a, **k: None)
    monkeypatch.setattr(f"{MODULE}.check_xcb_cursor", lambda: None)
    monkeypatch.setattr(f"{MODULE}._last_launch_log_path", lambda: log_path)
    monkeypatch.setattr(f"{MODULE}.subprocess.Popen", _FakeFailingPopen)

    exit_code, returned_workspace = _run_on_console(None, None)
    _wait_for(lambda: log_path.exists() and "[err]" in log_path.read_text())
    captured = capsys.readouterr()

    assert exit_code == 3
    assert returned_workspace == workspace_dir
    assert "hello out" in captured.out
    assert "hello err" in captured.err
    assert f"SciQLop exited with code 3. Full output: {log_path}" in captured.err


# --- C3: pyproject.toml exposes a console entry point alongside the GUI one ---

def test_pyproject_has_console_script(pytestconfig):
    pyproject = pytestconfig.rootpath / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text())
    assert data["project"]["scripts"]["sciqlop-console"] == "SciQLop.app:main"
    assert data["project"]["gui-scripts"]["sciqlop"] == "SciQLop.app:main"


# --- native-launcher mode: main() must run one session, not loop, when the
# native C++ launcher (SCIQLOP_STARTUP_READY_FILE already set) owns the
# restart/switch round loop itself. ---

def test_switch_handoff_path_reads_from_env_var(monkeypatch, tmp_path):
    handoff = tmp_path / "next-workspace"
    monkeypatch.setenv(SWITCH_HANDOFF_FILE_ENV, str(handoff))
    assert _switch_handoff_path() == handoff


def test_switch_handoff_path_raises_clear_error_when_env_var_missing(monkeypatch):
    monkeypatch.delenv(SWITCH_HANDOFF_FILE_ENV, raising=False)
    with pytest.raises(RuntimeError, match=SWITCH_HANDOFF_FILE_ENV):
        _switch_handoff_path()


def test_main_native_mode_restart_calls_run_session_once(monkeypatch, tmp_path):
    monkeypatch.setenv(READY_FILE_ENV, "/tmp/some-ready-file")
    calls = []

    def fake_run(workspace_name, sciqlop_file):
        calls.append((workspace_name, sciqlop_file))
        return EXIT_RESTART, tmp_path

    monkeypatch.setattr(f"{MODULE}._choose_run_session", lambda: fake_run)

    assert main([]) == EXIT_RESTART
    assert calls == [(None, None)]  # exactly one call — no internal loop


def test_main_native_mode_switch_with_target_writes_handoff(monkeypatch, tmp_path):
    monkeypatch.setenv(READY_FILE_ENV, "/tmp/some-ready-file")
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    (workspace_dir / ".sciqlop_switch_target").write_text("other-workspace\n")
    handoff = tmp_path / "next-workspace"
    monkeypatch.setenv(SWITCH_HANDOFF_FILE_ENV, str(handoff))
    monkeypatch.setattr(f"{MODULE}._choose_run_session",
                         lambda: (lambda w, f: (EXIT_SWITCH_WORKSPACE, workspace_dir)))

    assert main([]) == EXIT_SWITCH_WORKSPACE
    assert handoff.read_text() == "other-workspace\n"
    assert not (workspace_dir / ".sciqlop_switch_target").exists()  # consumed


def test_main_native_mode_switch_without_target_writes_no_handoff(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv(READY_FILE_ENV, "/tmp/some-ready-file")
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    handoff = tmp_path / "next-workspace"
    monkeypatch.setenv(SWITCH_HANDOFF_FILE_ENV, str(handoff))
    monkeypatch.setattr(f"{MODULE}._choose_run_session",
                         lambda: (lambda w, f: (EXIT_SWITCH_WORKSPACE, workspace_dir)))

    assert main([]) == EXIT_SWITCH_WORKSPACE
    assert not handoff.exists()
    assert "no target found" in capsys.readouterr().err


# --- non-native mode: main()'s own loop must be untouched by the above. ---

def test_main_non_native_mode_loops_through_a_restart(monkeypatch):
    monkeypatch.delenv(READY_FILE_ENV, raising=False)
    calls = []

    def fake_run(workspace_name, sciqlop_file):
        calls.append(workspace_name)
        return (EXIT_RESTART if len(calls) == 1 else 0), None

    monkeypatch.setattr(f"{MODULE}._choose_run_session", lambda: fake_run)

    assert main([]) == 0
    assert calls == [None, None]  # looped internally, unlike native mode


def test_main_non_native_mode_loops_through_a_switch_with_target(monkeypatch, tmp_path):
    monkeypatch.delenv(READY_FILE_ENV, raising=False)
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    (workspace_dir / ".sciqlop_switch_target").write_text("other\n")
    calls = []

    def fake_run(workspace_name, sciqlop_file):
        calls.append(workspace_name)
        if len(calls) == 1:
            return EXIT_SWITCH_WORKSPACE, workspace_dir
        return 0, None

    monkeypatch.setattr(f"{MODULE}._choose_run_session", lambda: fake_run)

    assert main([]) == 0
    assert calls == [None, "other"]


def test_main_non_native_mode_switch_without_target_returns_65(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv(READY_FILE_ENV, raising=False)
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    monkeypatch.setattr(f"{MODULE}._choose_run_session",
                         lambda: (lambda w, f: (EXIT_SWITCH_WORKSPACE, workspace_dir)))

    assert main([]) == EXIT_SWITCH_WORKSPACE
    assert "no target found" in capsys.readouterr().err
