"""Tools > Profiling submenu — start/stop the runtime tracer at runtime.

The status entry mirrors `SciQLop.core.tracing.is_enabled()`, so a trace
started via the SCIQLOP_TRACE env var (handled by SciQLopPlots' static init)
is reflected correctly even though we never called enable() ourselves.
"""
import os
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QMenu, QMessageBox, QPlainTextEdit, QVBoxLayout, QWidget,
)

from SciQLop.components import sciqlop_logging
from SciQLop.core import tracing
from SciQLop.core.ui.tooltips import rich_tooltip
from .perfetto import open_trace_in_perfetto
from .speasy_tracing import install as install_speasy_tracing
from . import hang_dump
from . import sampler as sampler_module
from .thread_cpu_top import hot_threads

log = sciqlop_logging.getLogger(__name__)


class _HotThreadsDispatcher(QObject):
    """Runs hot_threads() off the GUI thread -- it sleeps for `window_s`,
    which would otherwise freeze the UI for the sampling duration."""
    ready = Signal(str)


class ProfilingMenu(QObject):
    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        install_speasy_tracing()
        self.menu = QMenu("Profiling", host)
        self.menu.setToolTipsVisible(True)
        self.menu.menuAction().setToolTip(rich_tooltip(
            "Profiling",
            "Record and inspect where SciQLop spends its time."))
        self._start = self.menu.addAction("Start trace…", self._on_start)
        self._stop = self.menu.addAction("Stop trace", self._on_stop)
        self._start.setToolTip(rich_tooltip(
            "Start trace",
            "Begin recording a Perfetto performance trace."))
        self._stop.setToolTip(rich_tooltip(
            "Stop trace",
            "Stop recording and save the current trace."))
        self.menu.addSeparator()
        self._hot_threads = None
        self._hot_threads_dispatcher = None
        self._dump_stacks = None
        self._flush_samples = None
        if sciqlop_logging.is_debug_mode():
            self._hot_threads = self.menu.addAction(
                "Show hot OS threads…", self._on_show_hot_threads)
            self._hot_threads.setToolTip(rich_tooltip(
                "Show hot OS threads",
                "Ranks this process's OS threads by CPU time over a short"
                " window — works without a trace running, and without"
                " py-spy/perf/root, by reading /proc directly."))
            self._hot_threads_dispatcher = _HotThreadsDispatcher(self)
            self._hot_threads_dispatcher.ready.connect(self._on_hot_threads_ready)
            self._dump_stacks = self.menu.addAction(
                "Dump thread stacks now", self._on_dump_stacks)
            self._dump_stacks.setToolTip(rich_tooltip(
                "Dump thread stacks now",
                "Writes an all-threads traceback dump to the diagnostics"
                " directory — useful when SciQLop feels slow right now."
                " The same dump can be triggered from outside the app with"
                " kill -USR1 <pid>, no elevated privilege needed."))
            self._flush_samples = self.menu.addAction(
                "Flush sampling history", self._on_flush_samples)
            self._flush_samples.setToolTip(rich_tooltip(
                "Flush sampling history",
                "Writes the last minute or so of periodic all-threads stack"
                " samples to the diagnostics directory — shows what was"
                " running even in code nobody hand-instrumented with a trace"
                " zone. The sampler itself is off by default; enable it in"
                " Settings > Profiling."))
            self.menu.addSeparator()
        self._open_last = self.menu.addAction(
            "Open last trace in Perfetto", self._on_open_last)
        self._open_last.setToolTip(rich_tooltip(
            "Open last trace",
            "Reopens the most recently captured trace in Perfetto."))
        self._open_pick = self.menu.addAction(
            "Open trace in Perfetto…", self._on_open_pick)
        self._open_pick.setToolTip(rich_tooltip(
            "Open trace file",
            "Loads a trace file into https://ui.perfetto.dev/ in your"
            " default browser. The trace is served from localhost and"
            " never uploaded — Perfetto runs entirely client-side."))
        self.menu.addSeparator()
        self._status = self.menu.addAction("Status: idle")
        self._status.setEnabled(False)
        self._current_path: Optional[str] = None
        self._last_path: Optional[str] = None
        self.menu.aboutToShow.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        recording = tracing.is_enabled()
        self._start.setEnabled(not recording)
        self._stop.setEnabled(recording)
        self._open_last.setEnabled(
            self._last_path is not None and Path(self._last_path).is_file()
        )
        if recording:
            label = self._current_path or "(SCIQLOP_TRACE)"
            self._status.setText(f"Recording → {label}")
        else:
            self._status.setText("Status: idle")

    def _on_start(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self._host, "Start runtime trace",
            "sciqlop_trace.json", "Chrome trace JSON (*.json)",
        )
        if not path:
            return
        tracing.enable(path)
        if not tracing.is_enabled():
            QMessageBox.warning(
                self._host, "Profiling",
                "Could not start the runtime tracer. The installed SciQLopPlots "
                "build does not yet ship the Python tracing module.",
            )
            return
        self._current_path = path
        self._last_path = path
        self._refresh()

    def _on_stop(self) -> None:
        path = self._current_path
        tracing.disable()
        if path:
            worker_paths = sorted(str(p) for p in Path(path).parent.glob(
                f"{Path(path).stem}.worker-*{Path(path).suffix}"))
            merged = tracing.merge_worker_traces(path, worker_paths)
            if merged:
                log.info("Merged %d remote-worker trace(s) into %s", merged, path)
        self._current_path = None
        self._refresh()

    def _on_show_hot_threads(self) -> None:
        self._hot_threads.setEnabled(False)
        self._hot_threads.setText("Show hot OS threads… (sampling…)")
        pid = os.getpid()

        def _run():
            threads = hot_threads(pid, window_s=0.5)
            top = threads[:15]
            lines = [f"{'CPU s':>7}  {'py':>3}  NAME (tid)"]
            for t in top:
                lines.append(f"{t.cpu_seconds:>7.2f}  {'Y' if t.is_python else 'n':>3}  {t.name} ({t.tid})")
            self._hot_threads_dispatcher.ready.emit("\n".join(lines))

        threading.Thread(target=_run, daemon=True).start()

    def _on_hot_threads_ready(self, text: str) -> None:
        self._hot_threads.setEnabled(True)
        self._hot_threads.setText("Show hot OS threads…")
        dialog = QDialog(self._host)
        dialog.setWindowTitle("Hot OS threads (0.5s window)")
        view = QPlainTextEdit(text, dialog)
        view.setReadOnly(True)
        view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        layout = QVBoxLayout(dialog)
        layout.addWidget(view)
        dialog.resize(560, 420)
        dialog.exec()

    def _on_dump_stacks(self) -> None:
        path = hang_dump.dump_now("manual")
        QMessageBox.information(self._host, "Profiling",
                                f"Thread stacks dumped to:\n{path}")

    def _on_flush_samples(self) -> None:
        sampler = sampler_module.get_sampler()
        if not sampler.snapshot():
            QMessageBox.information(
                self._host, "Profiling",
                "No samples collected yet -- the sampler is off by default"
                " (Settings > Profiling > sampler_enabled) or just started.")
            return
        path = sampler_module.flush_to_file(sampler, None, "manual")
        QMessageBox.information(self._host, "Profiling",
                                f"Sampling history dumped to:\n{path}")

    def _on_open_last(self) -> None:
        if not self._last_path:
            return
        self._open_path(self._last_path)

    def _on_open_pick(self) -> None:
        default_dir = ""
        if self._last_path and Path(self._last_path).parent.is_dir():
            default_dir = self._last_path
        path, _ = QFileDialog.getOpenFileName(
            self._host, "Open trace in Perfetto",
            default_dir, "Chrome trace JSON (*.json);;All files (*)",
        )
        if path:
            self._open_path(path)

    def _open_path(self, path: str) -> None:
        try:
            open_trace_in_perfetto(path)
            self._last_path = path
        except FileNotFoundError:
            QMessageBox.warning(self._host, "Profiling",
                                f"Trace file not found:\n{path}")
        except Exception as exc:
            QMessageBox.warning(self._host, "Profiling",
                                f"Could not open trace in Perfetto:\n{exc}")
