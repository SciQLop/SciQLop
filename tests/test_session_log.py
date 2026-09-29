"""Dated session logs, the crash marker, and always-on crash traces.

See docs/superpowers/specs/2026-09-29-crash-report-agent-design.md.
"""
import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime

import pytest

from SciQLop.core import session_log as sl


def test_session_log_name_is_dated_and_carries_the_pid():
    name = sl.session_log_name(datetime(2026, 9, 29, 7, 5, 3), 4242)
    assert name == "sciqlop-20260929-070503-4242.log"


def test_new_session_log_creates_the_logs_directory(tmp_path):
    logs = tmp_path / "logs"
    path = sl.new_session_log(logs, now=datetime(2026, 9, 29), pid=1)
    assert path.parent == logs
    assert path.is_file()


def test_rotation_keeps_the_ten_newest_logs(tmp_path):
    paths = [sl.new_session_log(tmp_path, now=datetime(2026, 9, day), pid=1)
             for day in range(1, 12)]
    remaining = sorted(tmp_path.glob("sciqlop-*.log"))
    assert remaining == paths[1:]


def test_rotation_ignores_unrelated_files(tmp_path):
    (tmp_path / "notes.txt").write_text("keep me")
    for day in range(1, 13):
        sl.new_session_log(tmp_path, now=datetime(2026, 9, day), pid=1)
    assert (tmp_path / "notes.txt").exists()


def test_session_log_uses_the_path_the_native_launcher_chose(tmp_path, monkeypatch):
    chosen = tmp_path / "from-cpp.log"
    monkeypatch.setenv(sl.SESSION_LOG_ENV, str(chosen))
    sl.session_log.cache_clear()
    try:
        assert sl.session_log() == chosen
    finally:
        sl.session_log.cache_clear()


def test_session_log_is_one_file_per_process(tmp_path, monkeypatch):
    monkeypatch.delenv(sl.SESSION_LOG_ENV, raising=False)
    monkeypatch.setattr(sl, "launcher_data_dir", lambda: tmp_path)
    sl.session_log.cache_clear()
    try:
        first = sl.session_log()
        assert sl.session_log() == first
        assert first.parent == tmp_path / "logs"
    finally:
        sl.session_log.cache_clear()


@pytest.mark.parametrize("returncode, crashed", [
    (0, False), (1, False), (64, False), (65, False), (245, False),
    (-11, True), (-6, True),
    (0xC0000005, True),  # Windows access violation
    (0xC0000409, True),  # Windows stack buffer overrun / abort
])
def test_is_crash_only_for_abnormal_termination(returncode, crashed):
    assert sl.is_crash(returncode) is crashed


@pytest.mark.parametrize("returncode, text", [
    (0, "exited normally"),
    (3, "exited with code 3"),
    (-11, "crashed (SIGSEGV, signal 11)"),
    (-6, "crashed (SIGABRT, signal 6)"),
    (0xC0000005, "crashed (Windows exception 0xC0000005)"),
])
def test_describe_exit_names_the_signal(returncode, text):
    # GH #139: the same crash read "exited with code 251" in one place and
    # "exited with code -5" in another.
    assert sl.describe_exit(returncode) == text


def test_crash_marker_on_posix_records_the_signal(tmp_path):
    marker = sl.crash_marker(-11, 1234, tmp_path / "x.log", now=datetime(2026, 9, 29, 17, 19, 3))
    assert marker["pid"] == 1234
    assert marker["signal"] == 11
    assert marker["ntstatus"] is None
    assert marker["log"] == str(tmp_path / "x.log")
    assert marker["time"].startswith("2026-09-29T17:19:03")


def test_crash_marker_on_windows_records_the_ntstatus(tmp_path):
    marker = sl.crash_marker(0xC0000005, 1234, tmp_path / "x.log")
    assert marker["signal"] is None
    assert marker["ntstatus"] == "0xC0000005"


def test_take_crash_marker_reads_once(tmp_path):
    log = tmp_path / "x.log"
    log.write_text("boom")
    sl.write_crash_marker(sl.crash_marker(-11, 1, log), directory=tmp_path)
    marker = sl.take_crash_marker(directory=tmp_path)
    assert marker["signal"] == 11
    assert sl.take_crash_marker(directory=tmp_path) is None


def test_take_crash_marker_drops_a_marker_whose_log_rotated_away(tmp_path):
    sl.write_crash_marker(sl.crash_marker(-11, 1, tmp_path / "gone.log"), directory=tmp_path)
    assert sl.take_crash_marker(directory=tmp_path) is None
    assert not (tmp_path / sl.CRASH_MARKER_NAME).exists()


def test_take_crash_marker_survives_a_corrupt_file(tmp_path):
    (tmp_path / sl.CRASH_MARKER_NAME).write_text("{not json")
    assert sl.take_crash_marker(directory=tmp_path) is None
    assert not (tmp_path / sl.CRASH_MARKER_NAME).exists()


def test_record_if_crashed_writes_a_marker_for_a_real_segfault(tmp_path):
    log = tmp_path / "session.log"
    log.write_text("")
    proc = subprocess.Popen([sys.executable, "-c", "import faulthandler; faulthandler._sigsegv()"],
                            stderr=subprocess.DEVNULL)
    proc.wait()
    sl.record_if_crashed(proc, log, directory=tmp_path)
    marker = json.loads((tmp_path / sl.CRASH_MARKER_NAME).read_text())
    assert marker["pid"] == proc.pid
    assert marker["log"] == str(log)


def test_record_if_crashed_ignores_a_handled_exit(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "raise SystemExit(1)"])
    proc.wait()
    sl.record_if_crashed(proc, tmp_path / "session.log", directory=tmp_path)
    assert not (tmp_path / sl.CRASH_MARKER_NAME).exists()


def test_enable_crash_traces_writes_the_python_stack_to_the_session_log(tmp_path):
    log = tmp_path / "session.log"
    script = textwrap.dedent("""
        from SciQLop.core import session_log
        session_log.enable_crash_traces()

        def a_recognizable_function():
            import faulthandler
            faulthandler._sigsegv()

        a_recognizable_function()
    """)
    env = {**os.environ, sl.SESSION_LOG_ENV: str(log)}
    subprocess.run([sys.executable, "-c", script], env=env, stderr=subprocess.DEVNULL)
    content = log.read_text()
    assert "Segmentation fault" in content or "access violation" in content
    assert "a_recognizable_function" in content
