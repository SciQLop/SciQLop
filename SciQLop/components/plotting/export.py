"""Saving a panel to a file: the core export targets and the one function PlotPanel.save and the menu share."""
from __future__ import annotations

from typing import Optional

from SciQLop.core.export_targets import EXPORT_TARGETS, ExportTarget, known_suffixes, target_for


def _checked(ok: bool, path: str) -> None:
    if not ok:
        raise OSError(f"failed to save {path!r}: check that the directory exists and is writable")


def _raster(method: str):
    def write(panel, path, width, height, scale):
        _checked(getattr(panel._get_impl_or_raise(), method)(path, width, height, scale), path)
    return write


def _pdf(panel, path, width, height, scale):
    _checked(panel._get_impl_or_raise().save_pdf(path, width, height), path)


CORE_TARGETS = (
    ExportTarget("sciqlop.png", "PNG", (".png",), _raster("save_png")),
    ExportTarget("sciqlop.pdf", "PDF", (".pdf",), _pdf, scalable=False),
    ExportTarget("sciqlop.jpg", "JPEG", (".jpg", ".jpeg"), _raster("save_jpg")),
    ExportTarget("sciqlop.bmp", "BMP", (".bmp",), _raster("save_bmp")),
)

for _target in CORE_TARGETS:
    if _target.id not in EXPORT_TARGETS:
        EXPORT_TARGETS.contribute(_target, owner="sciqlop")


def export_panel(panel, path: str, *, width: int = 0, height: int = 0, scale: Optional[float] = None) -> None:
    target = target_for(path)
    if target is None:
        raise ValueError(f"Unsupported format for {path!r}. Use one of: {', '.join(known_suffixes())}")
    if not target.scalable and scale is not None:
        raise ValueError(f"scale only applies to raster formats; give width and height for {target.label}")
    if target.scalable and scale is None:
        scale = panel._get_impl_or_raise().devicePixelRatioF()
    target.write(panel, path, width, height, scale)
