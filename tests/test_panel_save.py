"""PlotPanel.save: format from the extension, optional size and scale."""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import pytest


def test_explicit_size_sets_the_image_size(plot_panel, tmp_path):
    from PIL import Image
    plot_panel.save(str(tmp_path / "ql.png"), width=640, height=360)
    assert Image.open(tmp_path / "ql.png").size == (640, 360)


def test_scale_is_refused_for_pdf(plot_panel, tmp_path):
    """save_pdf has no scale: silently dropping it would hand back a PDF
    at a size the caller did not ask for."""
    with pytest.raises(ValueError, match="raster"):
        plot_panel.save(str(tmp_path / "ql.pdf"), scale=2.0)


def test_unknown_extension_is_refused(plot_panel, tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        plot_panel.save(str(tmp_path / "ql.svg"))
