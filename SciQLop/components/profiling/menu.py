"""Tools > Profiling submenu — start/stop the runtime tracer at runtime.

The status entry mirrors `SciQLop.core.tracing.is_enabled()`, so a trace
started via the SCIQLOP_TRACE env var (handled by SciQLopPlots' static init)
is reflected correctly even though we never called enable() ourselves.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox, QWidget

from SciQLop.core import tracing
from .perfetto import open_trace_in_perfetto
from .speasy_tracing import install as install_speasy_tracing


class ProfilingMenu(QObject):
    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        install_speasy_tracing()
        self.menu = QMenu("Profiling", host)
        self._start = self.menu.addAction("Start trace…", self._on_start)
        self._stop = self.menu.addAction("Stop trace", self._on_stop)
        self.menu.addSeparator()
        self._open_last = self.menu.addAction(
            "Open last trace in Perfetto", self._on_open_last)
        self._open_last.setToolTip(
            "Reopens the most recently captured trace in Perfetto.")
        self._open_pick = self.menu.addAction(
            "Open trace in Perfetto…", self._on_open_pick)
        self._open_pick.setToolTip(
            "Loads a trace file into https://ui.perfetto.dev/ in your default browser. "
            "The trace is served from localhost and never uploaded — Perfetto runs "
            "entirely client-side.")
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
        tracing.disable()
        self._current_path = None
        self._refresh()

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
