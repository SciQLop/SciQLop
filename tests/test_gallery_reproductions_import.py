"""Smoke test: the gallery-reproduction script must stay importable.

Importing it under pytest catches syntax errors, renamed APIs, and missing
symbols without fetching real data or opening windows.
"""


def test_gallery_reproductions_imports():
    from SciQLop.examples import gallery_reproductions as gallery

    assert hasattr(gallery, "hero_mms_magnetopause_crossing")
    assert hasattr(gallery, "projection_trajectory")
    assert hasattr(gallery, "radio_dynamic_spectrum_before_after")
    assert hasattr(gallery, "waterfall_spectral")
    assert hasattr(gallery, "histogram2d_distribution")
    assert hasattr(gallery, "annotation_layers")
    assert hasattr(gallery, "knobs_parameterized_product")
    assert hasattr(gallery, "catalog_overlay_panel")
    assert hasattr(gallery, "graphic_primitives_boundary")
    assert hasattr(gallery, "theme_grid_screenshot")
