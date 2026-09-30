"""Keyboard shortcuts for profiling: start, stop, open in Perfetto."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


class _FakeTracer:
    def __init__(self):
        self.path = None

    def enable(self, path):
        self.path = path

    def is_enabled(self):
        return self.path is not None

    def disable(self):
        from pathlib import Path
        Path(self.path).write_text("{}")
        self.path = None

    def merge_worker_traces(self, path, workers):
        return 0


@pytest.fixture
def profiling(qtbot, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.profiling import menu as menu_module

    tracer = _FakeTracer()
    opened = []
    for name in ("enable", "is_enabled", "disable", "merge_worker_traces"):
        monkeypatch.setattr(menu_module.tracing, name, getattr(tracer, name))
    monkeypatch.setattr(menu_module, "open_trace_in_perfetto", opened.append)
    monkeypatch.setattr(menu_module, "traces_dir", lambda: tmp_path)
    host = QMainWindow()
    qtbot.addWidget(host)
    menu = menu_module.ProfilingMenu(host)
    return menu, tracer, opened, tmp_path


def _no_dialog(monkeypatch):
    from SciQLop.components.profiling import menu as menu_module

    def _fail(*args, **kwargs):
        raise AssertionError("a shortcut must not open a file dialog")

    monkeypatch.setattr(menu_module.QFileDialog, "getSaveFileName", _fail)


def test_start_stop_and_open_have_shortcuts_that_work_in_every_window(profiling):
    from SciQLop.components.profiling.settings import ProfilingSettings

    menu, *_ = profiling
    settings = ProfilingSettings()
    for action, key in ((menu._start, settings.start_trace_shortcut),
                        (menu._stop, settings.stop_trace_shortcut),
                        (menu._open_last, settings.open_trace_shortcut)):
        assert action.shortcut() == QKeySequence(key)
        assert action.shortcutContext() == Qt.ShortcutContext.ApplicationShortcut


def test_start_records_to_a_dated_file_without_asking(profiling, monkeypatch):
    menu, tracer, _opened, traces = profiling
    _no_dialog(monkeypatch)

    menu._start.trigger()

    assert tracer.is_enabled()
    assert tracer.path.startswith(str(traces))
    assert tracer.path.endswith(".json")
    assert not menu._start.isEnabled()
    assert menu._stop.isEnabled()


def test_stop_then_open_shows_the_trace_just_recorded(profiling, monkeypatch):
    menu, tracer, opened, _traces = profiling
    _no_dialog(monkeypatch)

    menu._start.trigger()
    recorded = tracer.path
    menu._stop.trigger()
    assert menu._open_last.isEnabled()
    menu._open_last.trigger()

    assert not tracer.is_enabled()
    assert opened == [recorded]


def _trace(directory, day, workers=0):
    stem = f"sciqlop-trace-202609{day:02d}-120000"
    (directory / f"{stem}.json").write_text("{}")
    for n in range(workers):
        (directory / f"{stem}.worker-{n}.json").write_text("{}")
    return stem


def test_prune_traces_keeps_the_newest_with_their_worker_files(tmp_path):
    from SciQLop.components.profiling.menu import prune_traces

    stems = [_trace(tmp_path, day, workers=1) for day in range(1, 6)]
    (tmp_path / "my-own-trace.json").write_text("{}")

    prune_traces(tmp_path, keep=3)

    remaining = sorted(p.name for p in tmp_path.iterdir())
    kept = stems[2:]
    assert remaining == sorted(["my-own-trace.json"]
                               + [f"{s}.json" for s in kept]
                               + [f"{s}.worker-0.json" for s in kept])


def test_stopping_rotates_the_traces_folder_to_the_setting(profiling, monkeypatch):
    from SciQLop.components.profiling.settings import ProfilingSettings

    menu, _tracer, _opened, traces = profiling
    _no_dialog(monkeypatch)
    for day in range(1, 6):
        _trace(traces, day)
    saved = ProfilingSettings().traces_to_keep
    with ProfilingSettings() as settings:
        settings.traces_to_keep = 2
    try:
        menu._start.trigger()
        menu._stop.trigger()
    finally:
        with ProfilingSettings() as settings:
            settings.traces_to_keep = saved

    remaining = sorted(p.name for p in traces.glob("*.json"))
    assert len(remaining) == 2
    assert remaining[0] == "sciqlop-trace-20260905-120000.json"


def test_open_without_any_trace_asks_for_a_file(profiling, monkeypatch):
    from SciQLop.components.profiling import menu as menu_module

    menu, _tracer, opened, tmp_path = profiling
    picked = tmp_path / "old.json"
    picked.write_text("{}")
    monkeypatch.setattr(menu_module.QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(picked), ""))

    assert menu._open_last.isEnabled()
    menu._open_last.trigger()

    assert opened == [str(picked)]


def test_show_traces_folder_opens_it_in_the_file_browser(profiling, monkeypatch):
    from SciQLop.components.profiling import menu as menu_module

    menu, _tracer, _opened, traces = profiling
    urls = []
    monkeypatch.setattr(menu_module.QDesktopServices, "openUrl", urls.append)

    menu._show_folder.trigger()

    assert [u.toLocalFile() for u in urls] == [str(traces)]
