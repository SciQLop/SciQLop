"""Screenshot helpers for SciQLop."""
from __future__ import annotations

__all__ = ["capture_window", "capture_panel"]

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from SciQLop.user_api._annotations import experimental_api
from SciQLop.user_api.gui import get_main_window
from SciQLop.user_api.threading import on_main_thread

if TYPE_CHECKING:
    from SciQLop.user_api.plot import PlotPanel


@experimental_api()
@on_main_thread
def capture_window(path: str | Path) -> Path:
    """Capture the full SciQLop main window and save it to ``path``.

    The image format is inferred from the file extension; ``.png`` is the
    recommended format.
    """
    path = Path(path)
    window = get_main_window()
    pixmap = window.grab()
    _paint_plots_over(pixmap, window)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path)):
        raise OSError(f"failed to save screenshot to {path!r}")
    return path


def _paint_plots_over(pixmap, window) -> None:
    """grab() reads plots back through QRhi, which a headless platform
    (offscreen) lacks: they come out blank. Their own export renders in
    software, so it works everywhere and matches ``panel.save()``."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtGui import QImage, QPainter
    painter = QPainter(pixmap)
    with tempfile.TemporaryDirectory() as tmp:
        for i, plot in enumerate(_visible_plots(window)):
            file = os.path.join(tmp, f"{i}.png")
            plot.save_png(file, 0, 0, pixmap.devicePixelRatio())
            origin = plot.mapTo(window, QPoint(0, 0))
            painter.save()
            painter.setClipRegion(plot.visibleRegion().translated(origin))
            painter.drawImage(QRect(origin, plot.size()), QImage(file))
            painter.restore()
    painter.end()


def _visible_plots(window) -> list:
    from SciQLopPlots import SciQLopPlotInterface
    plots = [p for p in window.findChildren(SciQLopPlotInterface)
             if window.isAncestorOf(p) and p.isVisible() and not p.visibleRegion().isEmpty()]
    return [p for p in plots if not _inside_another_plot(p)]


def _inside_another_plot(plot) -> bool:
    from SciQLopPlots import SciQLopPlotInterface
    parent = plot.parentWidget()
    while parent is not None:
        if isinstance(parent, SciQLopPlotInterface):
            return True
        parent = parent.parentWidget()
    return False


@experimental_api()
@on_main_thread
def capture_panel(panel: "PlotPanel", path: str | Path) -> Path:
    """Capture a plot panel and save it to ``path``.

    Supported extensions: .png, .pdf, .jpg, .jpeg, .bmp.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    panel.save(str(path))
    return path
