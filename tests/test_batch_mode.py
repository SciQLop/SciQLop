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
