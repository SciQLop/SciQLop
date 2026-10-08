"""`sciqlop --batch script.py [args...]`: run a script inside SciQLop, no window.

The launcher hands the request to the app process through the SCIQLOP_BATCH
environment variable; the app builds its main window hidden, runs the script
from the caller's directory and exits with the script's exit code.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from SciQLop.core.batch import BATCH_ENV, BatchRequest, run_batch_script


def _without_faulthandler_noise(stderr: str) -> str:
    lines = [line for line in stderr.splitlines()
             if not line.lstrip().startswith(("Binary file", "Extension modules"))]
    return "\n".join(lines[-80:])


def _write_script(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body))
    return path


def test_parse_args_collects_the_script_and_its_arguments():
    from SciQLop.sciqlop_launcher import parse_args

    args = parse_args(["-w", "ql", "--batch", "make_ql.py", "2020-01-01", "--days", "3"])

    assert args.workspace == "ql"
    assert args.batch == ["make_ql.py", "2020-01-01", "--days", "3"]


def test_launcher_runs_one_console_session_and_returns_the_script_exit_code(monkeypatch, tmp_path):
    from SciQLop import sciqlop_launcher

    # setenv, not delenv: delenv of an unset variable records nothing to undo,
    # and main() writes the request into os.environ for the app process.
    monkeypatch.setenv(BATCH_ENV, "")
    monkeypatch.setenv("SCIQLOP_LAUNCHER_VERSION", "")
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    monkeypatch.delenv(sciqlop_launcher.READY_FILE_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    sessions = []

    def fake_console(workspace_name, sciqlop_file, reset_environment=False):
        sessions.append((workspace_name, BatchRequest.from_env(os.environ)))
        return 3, None

    monkeypatch.setattr(sciqlop_launcher, "_run_on_console", fake_console)

    assert sciqlop_launcher.main(["-w", "ql", "--batch", "make_ql.py", "x"]) == 3
    assert sessions == [("ql", BatchRequest(script=str(tmp_path / "make_ql.py"),
                                            args=["x"], cwd=str(tmp_path)))]


def _session_env(monkeypatch, tmp_path, argv):
    """os.environ as the app process would inherit it, for launcher argv."""
    from SciQLop import sciqlop_launcher

    for name in (BATCH_ENV, "SCIQLOP_NO_WEBENGINE", "QT_QPA_PLATFORM", "SCIQLOP_LAUNCHER_VERSION"):
        monkeypatch.setenv(name, "")  # setenv records the value to restore
        monkeypatch.delenv(name)
    monkeypatch.delenv(sciqlop_launcher.READY_FILE_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    seen = []

    def fake_session(*args, **kwargs):
        seen.append(dict(os.environ))
        return 0, None

    monkeypatch.setattr(sciqlop_launcher, "_run_on_console", fake_session)
    monkeypatch.setattr(sciqlop_launcher, "_choose_run_session", lambda: fake_session)
    sciqlop_launcher.main(argv)
    return seen[0]


def test_no_webengine_flag_reaches_the_app_process(monkeypatch, tmp_path):
    env = _session_env(monkeypatch, tmp_path, ["--no-webengine"])

    assert env["SCIQLOP_NO_WEBENGINE"] == "1"


def test_without_the_flag_webengine_stays_on(monkeypatch, tmp_path):
    env = _session_env(monkeypatch, tmp_path, [])

    assert "SCIQLOP_NO_WEBENGINE" not in env


def test_batch_runs_without_webengine(monkeypatch, tmp_path):
    env = _session_env(monkeypatch, tmp_path, ["--batch", "s.py"])

    assert env["SCIQLOP_NO_WEBENGINE"] == "1"
    assert env["QT_QPA_PLATFORM"] == "offscreen"


def test_request_survives_the_environment_round_trip():
    request = BatchRequest(script="/a/b.py", args=["--day", "été"], cwd="/c")

    assert BatchRequest.from_env({BATCH_ENV: request.to_env()}) == request
    assert BatchRequest.from_env({}) is None


def test_script_runs_from_the_caller_directory_with_its_arguments(tmp_path, monkeypatch):
    monkeypatch.chdir("/")
    script = _write_script(tmp_path / "s.py", """
        import sys
        open("argv.txt", "w").write(" ".join(sys.argv))
    """)

    code = run_batch_script(BatchRequest(script=str(script), args=["a", "b"], cwd=str(tmp_path)))

    assert code == 0
    assert (tmp_path / "argv.txt").read_text() == f"{script} a b"


@pytest.mark.parametrize("body, expected", [
    ("raise RuntimeError('boom')", 1),
    ("import sys; sys.exit(3)", 3),
    ("import sys; sys.exit()", 0),
    ("import sys; sys.exit('fatal: no data')", 1),
])
def test_exit_code_follows_the_script(tmp_path, monkeypatch, body, expected):
    monkeypatch.chdir(tmp_path)
    script = _write_script(tmp_path / "s.py", body)

    assert run_batch_script(BatchRequest(script=str(script), args=[], cwd=str(tmp_path))) == expected


def test_batch_session_exports_a_panel_without_a_display(tmp_path):
    script = _write_script(tmp_path / "quicklook.py", """
        import numpy as np
        from SciQLop.user_api.plot import create_plot_panel

        def sine(start, stop):
            x = np.arange(start, stop, 10.0)
            return x, np.sin(x / 300.)

        panel = create_plot_panel()
        panel.plot_function(sine)
        panel.time_range = ("2020-01-01", "2020-01-01T02:00")
        panel.settle(timeout=30)
        panel.save("quicklook.png")
    """)
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM")}
    env[BATCH_ENV] = BatchRequest(script=str(script), args=[], cwd=str(tmp_path)).to_env()
    env["QT_QPA_PLATFORM"] = "offscreen"

    proc = subprocess.run([sys.executable, "-m", "SciQLop.sciqlop_app"], env=env,
                          capture_output=True, text=True, timeout=180)

    assert proc.returncode == 0, _without_faulthandler_noise(proc.stderr)
    assert (tmp_path / "quicklook.png").stat().st_size > 0


def test_closing_the_main_window_closes_plugins_and_exits_cleanly(tmp_path):
    """The in-process suite tears windows down without closeEvent, so plugin
    close() and the async close path only ever ran in production."""
    marker = tmp_path / "plugin_closed"
    script = _write_script(tmp_path / "quit.py", f"""
        import os
        import time
        from PySide6.QtWidgets import QApplication
        from SciQLop.components.plugins import loaded_plugins
        from SciQLop.user_api.gui import get_main_window

        class _Plugin:
            async def close(self):
                open({str(marker)!r}, "w").close()

        loaded_plugins.quit_probe = _Plugin()
        window = get_main_window()
        window.close()
        deadline = time.monotonic() + 30
        while not os.path.exists({str(marker)!r}):
            if time.monotonic() > deadline:
                raise SystemExit("plugin close() never ran")
            QApplication.processEvents()
            time.sleep(0.01)
    """)
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM")}
    env[BATCH_ENV] = BatchRequest(script=str(script), args=[], cwd=str(tmp_path)).to_env()
    env["QT_QPA_PLATFORM"] = "offscreen"

    proc = subprocess.run([sys.executable, "-m", "SciQLop.sciqlop_app"], env=env,
                          capture_output=True, text=True, timeout=180)

    assert proc.returncode == 0, _without_faulthandler_noise(proc.stderr)
    assert marker.exists()
