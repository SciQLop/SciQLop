"""Screenshot helpers for SciQLop."""
from __future__ import annotations

__all__ = ["capture_window", "capture_panel"]

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
    pixmap = get_main_window().grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not pixmap.save(str(path)):
        raise OSError(f"failed to save screenshot to {path!r}")
    return path


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
