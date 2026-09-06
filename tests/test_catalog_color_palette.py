from .fixtures import *
import pytest


def test_color_for_uuid_returns_qcolor(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    color = color_for_catalog("test-uuid-1234")
    from PySide6.QtGui import QColor
    assert isinstance(color, QColor)
    assert color.alpha() > 0


def test_color_is_consistent(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    c1 = color_for_catalog("uuid-abc")
    c2 = color_for_catalog("uuid-abc")
    assert c1 == c2


def test_color_is_stable_across_hash_seeds(qapp):
    """color_for_catalog must not depend on PYTHONHASHSEED."""
    import subprocess, sys, os
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    script = (
        "from SciQLop.components.catalogs.backend.color_palette import color_for_catalog; "
        f"c = color_for_catalog('{uuid}'); "
        "print(c.red(), c.green(), c.blue())"
    )
    results = set()
    for seed in ("0", "42", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.check_output(
            [sys.executable, "-c", script], env=env, text=True
        ).strip()
        results.add(out)
    assert len(results) == 1, f"Color varies with PYTHONHASHSEED: {results}"


def test_different_uuids_can_differ(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    colors = {color_for_catalog(f"uuid-{i}").name() for i in range(12)}
    # at least several distinct colors from 12 different UUIDs
    assert len(colors) >= 6


def test_palette_does_not_pair_pure_red_and_green(qapp):
    """The original 12-color set (tab10-derived) included a near-pure red
    (214,39,40) and a near-pure green (44,160,44) -- the classic red-green
    colorblind confusion pair, with ~40% odds two of four hash-assigned
    catalogs would land on them. Replaced with Paul Tol's colorblind-safe
    'muted' qualitative palette (2026-09-06 review)."""
    from SciQLop.components.catalogs.backend.color_palette import _PALETTE

    def is_pure_red(c):
        return c.red() > 180 and c.green() < 80 and c.blue() < 80

    def is_pure_green(c):
        return c.green() > 130 and c.red() < 80 and c.blue() < 80

    reds = [c for c in _PALETTE if is_pure_red(c)]
    greens = [c for c in _PALETTE if is_pure_green(c)]
    assert not (reds and greens), \
        f"palette still pairs a pure red {reds} with a pure green {greens}"


def test_catalog_swatch_icon_is_not_null(qapp):
    from SciQLop.components.catalogs.backend.color_palette import catalog_swatch_icon
    icon = catalog_swatch_icon("uuid-swatch-1")
    assert not icon.isNull()


def test_catalog_swatch_icon_renders_the_catalog_color(qapp):
    """Rendered pixels, not object/cache identity: the swatch is a QIconEngine
    (deliberately uncached, see color_palette.py) so two calls for the same
    uuid are different QIcon instances by design -- what must be identical
    is what they actually paint."""
    from PySide6.QtCore import QSize
    from SciQLop.components.catalogs.backend.color_palette import (
        catalog_swatch_icon, color_for_catalog,
    )

    uuid = "uuid-swatch-2"
    icon = catalog_swatch_icon(uuid)
    pixmap = icon.pixmap(QSize(16, 16))
    center = pixmap.toImage().pixelColor(8, 8)

    expected = color_for_catalog(uuid)
    assert (center.red(), center.green(), center.blue()) == (expected.red(), expected.green(), expected.blue())
    assert center.alpha() == 255  # opaque swatch, unlike the plot overlay's alpha-80 fill


def test_catalog_swatch_icon_is_high_dpi_aware(qapp):
    """Rendering through paint() (no baked fixed-size pixmap) means the
    engine draws at whatever device resolution is requested -- a 2x request
    must not just look like the 1x pixmap stretched."""
    from PySide6.QtCore import QSize
    from SciQLop.components.catalogs.backend.color_palette import catalog_swatch_icon

    icon = catalog_swatch_icon("uuid-swatch-dpi")
    small = icon.pixmap(QSize(16, 16))
    large = icon.pixmap(QSize(32, 32))
    assert small.size() == QSize(16, 16)
    assert large.size() == QSize(32, 32)
    # A stretched 16px pixmap would have a visibly larger relative margin;
    # the 2x render's opaque disc should cover materially more than 4x the
    # opaque pixel count of the 1x render only if it was drawn fresh at
    # that resolution rather than upscaled from a fixed small pixmap.
    def opaque_pixels(pm):
        img = pm.toImage()
        return sum(
            1 for y in range(img.height()) for x in range(img.width())
            if img.pixelColor(x, y).alpha() > 0
        )
    small_opaque = opaque_pixels(small)
    large_opaque = opaque_pixels(large)
    ratio = large_opaque / small_opaque
    assert 3.5 <= ratio <= 4.5, f"expected ~4x opaque pixels at 2x size, got {ratio:.2f}x"
