import os
import signal
import threading
import time

from SciQLop.components.profiling import hang_dump


def test_dump_now_writes_a_fresh_timestamped_file_with_reason_and_threads(tmp_path):
    marker = threading.Event()
    t = threading.Thread(target=marker.wait, name="dump-now-marker-thread", daemon=True)
    t.start()
    try:
        path = hang_dump.dump_now("unit-test", directory=tmp_path)
        assert path.is_file()
        assert path.parent == tmp_path
        content = path.read_text()
        assert "unit-test" in content
        assert "dump-now-marker-thread" in content
    finally:
        marker.set()
        t.join()


def test_dump_now_creates_a_new_file_per_call(tmp_path):
    path1 = hang_dump.dump_now("first", directory=tmp_path)
    path2 = hang_dump.dump_now("second", directory=tmp_path)
    assert path1 != path2
    assert path1.is_file()
    assert path2.is_file()


def test_install_signal_dump_writes_on_sigusr1(tmp_path):
    marker = threading.Event()
    t = threading.Thread(target=marker.wait, name="sigusr1-marker-thread", daemon=True)
    t.start()
    try:
        log_path = hang_dump.install_signal_dump(tmp_path)
        try:
            os.kill(os.getpid(), signal.SIGUSR1)
            deadline = time.monotonic() + 5
            content = ""
            while time.monotonic() < deadline:
                if log_path.is_file():
                    content = log_path.read_text()
                    if content:
                        break
                time.sleep(0.05)
            # faulthandler labels threads by native ident only, not by
            # threading.Thread.name -- see install_signal_dump's docstring.
            assert f"{t.ident:016x}" in content
        finally:
            hang_dump.uninstall_signal_dump()
    finally:
        marker.set()
        t.join()


def test_install_signal_dump_is_a_no_op_without_sigusr1(tmp_path, monkeypatch):
    # Windows has no SIGUSR1 and no faulthandler.register(); debug mode must
    # still start there.
    monkeypatch.delattr(signal, "SIGUSR1")
    assert hang_dump.install_signal_dump(tmp_path) is None
    hang_dump.uninstall_signal_dump()
    assert not (tmp_path / "signal_dumps.log").exists()
