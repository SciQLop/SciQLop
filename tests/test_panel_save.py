"""PlotPanel.save: format from the extension, optional size and scale."""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import pytest


def test_explicit_size_sets_the_image_size(plot_panel, tmp_path):
    from PIL import Image
    plot_panel.save(str(tmp_path / "ql.png"), width=640, height=360)
    assert Image.open(tmp_path / "ql.png").size == (640, 360)


def test_default_export_matches_the_screen_resolution(plot_panel, tmp_path, monkeypatch):
    """On a HiDPI screen the panel shows 2 pixels per logical one; scale=1
    exported it at half the resolution seen on screen."""
    from PIL import Image
    impl = plot_panel._get_impl_or_raise()
    monkeypatch.setattr(impl, "devicePixelRatioF", lambda: 2.0)
    plot_panel.save(str(tmp_path / "ql.png"))
    assert Image.open(tmp_path / "ql.png").size == (2 * impl.width(), 2 * impl.height())


def test_scale_is_refused_for_pdf(plot_panel, tmp_path):
    """save_pdf has no scale: silently dropping it would hand back a PDF
    at a size the caller did not ask for."""
    with pytest.raises(ValueError, match="raster"):
        plot_panel.save(str(tmp_path / "ql.pdf"), scale=2.0)


def test_unknown_extension_is_refused(plot_panel, tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        plot_panel.save(str(tmp_path / "ql.svg"))


def _rendered_pdf(path, width, height):
    from PySide6.QtCore import QSize
    from PySide6.QtPdf import QPdfDocument
    document = QPdfDocument()
    assert document.load(str(path)) == QPdfDocument.Error.None_
    assert document.pageCount() == 1
    return document.render(0, QSize(width, height))


def _curve_pixels(image):
    """Pixels in a vivid colour: the curve, not the grey axes and text nor the dull background."""
    import numpy as np
    from PIL import Image
    rgb = np.asarray(Image.open(image).convert("RGB")).astype(int)
    return int((rgb.max(axis=-1) - rgb.min(axis=-1) > 80).sum())


def test_pdf_holds_the_plotted_curve(plot_panel, tmp_path, qtbot):
    """The PDF writer forwarded scale=None, which SciQLopPlots' save refuses: no PDF was written."""
    import numpy as np
    x = np.linspace(1.7e9, 1.7e9 + 3600, 2000)
    plot_panel.plot_data(x, 10 * np.sin(np.linspace(0, 20, 2000)))
    plot_panel.time_range = (x[0], x[-1])
    qtbot.wait(200)
    plot_panel.save(str(tmp_path / "ql.pdf"), width=800, height=600)
    plot_panel.save(str(tmp_path / "ql.png"), width=800, height=600)
    _rendered_pdf(tmp_path / "ql.pdf", 800, 600).save(str(tmp_path / "pdf.png"))
    on_screen = _curve_pixels(tmp_path / "ql.png")
    assert on_screen > 1000
    assert _curve_pixels(tmp_path / "pdf.png") > on_screen / 2
