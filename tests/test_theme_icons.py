"""The themed icon engine must render at the requested device size (crisp on
HiDPI when the source is scalable) and tint to contrast the palette, preserving
anti-aliased alpha — without ever shrinking raster sources."""
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures

_NORMAL = QIcon.Mode.Normal
_OFF = QIcon.State.Off
# A scalable theme icon shipped by SciQLopPlots (qrc registered on import).
_SVG = ":/icons/theme/my_location.svg"


def _logical_size(pm) -> QSize:
    dpr = pm.devicePixelRatio()
    return QSize(round(pm.width() / dpr), round(pm.height() / dpr))


def test_theme_icons_render(qapp, sciqlop_resources):
    from SciQLop.components.theming import theme_icon, theme_adapted_icon, get_icon

    for make in (theme_icon, theme_adapted_icon, get_icon):
        assert not make("delete").pixmap(QSize(24, 24)).isNull()


def test_scalable_source_renders_crisp_on_hidpi(qapp, sciqlop_resources):
    from SciQLop.components.theming import register_icon
    from SciQLop.components.theming.icons import _ThemeIconEngine

    register_icon("t_svg_icon", QIcon(_SVG))
    pm = _ThemeIconEngine("t_svg_icon").scaledPixmap(QSize(24, 24), _NORMAL, _OFF, 2.0)

    assert pm.width() == 48 and pm.height() == 48      # full device resolution
    assert pm.devicePixelRatio() == 2.0
    assert _logical_size(pm) == QSize(24, 24)          # occupies 24 logical px


def test_qicon_routes_hidpi_request_through_engine(qapp, sciqlop_resources):
    """QIcon.pixmap(size, dpr) must reach our scaledPixmap override, else HiDPI
    requests silently fall back to a 1x raster."""
    from SciQLop.components.theming import register_icon
    from SciQLop.components.theming.icons import _ThemeIconEngine

    register_icon("t_svg_icon2", QIcon(_SVG))
    pm = QIcon(_ThemeIconEngine("t_svg_icon2")).pixmap(QSize(24, 24), 2.0)

    assert pm.width() == 48 and pm.devicePixelRatio() == 2.0


def test_raster_source_keeps_logical_size(qapp, sciqlop_resources):
    """A 24x24 PNG can't upscale, but the engine must never *shrink* it: the
    result still occupies the requested logical size."""
    from SciQLop.components.theming.icons import _ThemeIconEngine

    pm = _ThemeIconEngine("delete").scaledPixmap(QSize(24, 24), _NORMAL, _OFF, 2.0)
    assert _logical_size(pm) == QSize(24, 24)


def test_qss_bake_is_extension_agnostic_and_writes_2x(qapp, sciqlop_resources):
    """The QSS bake must derive the name from the file stem (so an SVG source
    bakes ``name.png``, not ``name.svg.png``) and emit @1x + @2x for HiDPI."""
    from SciQLop.components.theming import register_icon
    from SciQLop.components.theming.icons import (
        build_icon_set_for_palette, per_palette_icon_dir,
    )

    register_icon(":/icons/theme/zzz_probe.svg", QIcon(_SVG))
    build_icon_set_for_palette("zzz_probe_palette", "#ffffff")
    out = per_palette_icon_dir("zzz_probe_palette")

    assert (out / "zzz_probe.png").exists()
    assert (out / "zzz_probe@2x.png").exists()
    assert not (out / "zzz_probe.svg.png").exists()   # the old `.png`-split bug
    assert QPixmap(str(out / "zzz_probe.png")).size() == QSize(24, 24)
    assert QPixmap(str(out / "zzz_probe@2x.png")).size() == QSize(48, 48)


def test_tint_recolors_to_palette_contrast(qapp, sciqlop_resources):
    from SciQLop.components.theming.icons import (
        _ThemeIconEngine, opposite_color, _app_base_color,
    )

    expected = opposite_color(_app_base_color())
    pm = _ThemeIconEngine("delete").scaledPixmap(QSize(24, 24), _NORMAL, _OFF, 1.0)
    img = pm.toImage()
    opaque = [
        img.pixelColor(x, y)
        for y in range(img.height()) for x in range(img.width())
        if img.pixelColor(x, y).alpha() > 200
    ]
    assert opaque, "tinted icon has no opaque pixels"
    assert all(c.rgb() == expected.rgb() for c in opaque)
