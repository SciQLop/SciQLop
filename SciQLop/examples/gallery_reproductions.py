"""Reproducible snippets for the SciQLop website gallery.

Each function configures a PlotPanel for one gallery shot. The functions are
not executed on import; call them from a notebook, script, or the SciQLop
Jupyter console.

Real speasy product paths are shown in comments where the gallery shot uses
live data. Replace the synthetic data with those products to reproduce the
shots against real archives.
"""
from __future__ import annotations

import numpy as np

from SciQLop.user_api.plot import LineTermination, PlotPanel
from SciQLop.user_api.plot.enums import BinStrategy, GraphType
from SciQLop.user_api.plot._graphic_primitives import (
    CurvedLine,
    HorizontalSpan,
    RectangularSpan,
    Text,
)
from SciQLop.user_api.catalogs import add_catalog_overlay
from SciQLop.user_api.themes import apply_theme


def _synthetic_time_series(n: int = 200):
    """Return a synthetic (time, value) pair for demos."""
    t = np.linspace(0, 100, n)
    y = np.sin(t / 10.0) + 0.2 * np.random.randn(n)
    return t, y


def hero_mms_magnetopause_crossing(panel: PlotPanel) -> None:
    """Hero shot: stacked energy spectrogram + B vector + density + velocity + temperature.

    Real data suggestion:
        speasy//cda//MMS//MMS1//DIS//MMS1_FPI_FAST_L2_DIS-MOMS//mms1_dis_energyspectr_omni_fast
        speasy//cda//MMS//MMS1//FGM//MMS1_FGM_SRVY_L2//mms1_fgm_b_gse_srvy_l2
    """
    panel.clear()
    # Synthetic stand-ins for the five stacked plots
    for _ in range(5):
        t, y = _synthetic_time_series()
        panel.plot(t, y)


def projection_trajectory(panel: PlotPanel) -> None:
    """Projection plot with a time-colored parametric curve and linked crosshairs."""
    panel.clear()
    t = np.linspace(0, 1, 300)
    x = np.cos(2 * np.pi * t)
    y = np.sin(2 * np.pi * t)
    z = np.linspace(-1, 1, 300)
    # Create an XY/projection plot via the omnibus dispatcher
    plot, _ = panel.plot(x, y, graph_type=GraphType.ParametricCurve)
    if hasattr(plot, "plot_time_colored_curve"):
        # A projection plot draws one panel per pair of dimensions, so it needs
        # as many dimensions as it has panels -- three, as the panel builds them.
        plot.plot_time_colored_curve(x, y, t, z=z, name="orbit", colormap="viridis")


def radio_dynamic_spectrum_before_after(panel: PlotPanel) -> None:
    """Radio dynamic spectrum, before and after background_subtract.

    Real data suggestion:
        speasy//archive//RadioJove or e-Callisto-style archives.
    """
    panel.clear()
    t = np.linspace(0, 10, 100)
    f = np.linspace(10, 50, 40)
    z = np.random.rand(len(f), len(t)) + np.sin(f[:, None] / 10)
    panel.waterfall(t, f, z, name="raw dynamic spectrum")


def waterfall_spectral(panel: PlotPanel) -> None:
    """Waterfall plot with offsets/gain set so the stack reads clearly."""
    panel.clear()
    x = np.linspace(0, 10, 100)
    y = np.linspace(0, 5, 20)
    z = np.sin(x) * np.exp(-y[:, None])
    wf = panel.waterfall(x, y, z, name="spectral stack")
    wf.offsets = float(np.mean(np.diff(y)))
    wf.gain = 1.5


def histogram2d_distribution(panel: PlotPanel) -> None:
    """2D histogram with log bins and a color gradient."""
    panel.clear()
    x = np.random.lognormal(0, 0.5, 2000)
    y = np.random.lognormal(0, 0.5, 2000)
    panel.histogram2d(
        x, y,
        x_bins=50,
        y_bins=50,
        x_bin_strategy=BinStrategy.Log,
        y_bin_strategy=BinStrategy.Log,
        name="flux vs energy",
    )


def annotation_layers(panel: PlotPanel) -> None:
    """Annotation layer drawing spans/markers over data (threshold crossings)."""
    panel.clear()
    t, y = _synthetic_time_series()
    panel.plot(t, y, name="signal")
    # Add a detector layer as a horizontal span for illustration
    HorizontalSpan(panel.plots[0], y1=-0.5, y2=0.5, color="rgba(50, 150, 200, 0.2)")


def knobs_parameterized_product(panel: PlotPanel) -> None:
    """Plot with a parameterized virtual product and draggable threshold line."""
    panel.clear()
    t, y = _synthetic_time_series()
    panel.plot(t, y, name="data")
    # A movable horizontal line stands in for the knob-driven threshold
    HorizontalSpan(panel.plots[0], y1=0.0, y2=0.1, color="rgba(231, 76, 60, 0.4)")


def catalog_overlay_panel(panel: PlotPanel) -> None:
    """Several color-coded catalog event overlays spanning multiple plots."""
    panel.clear()
    for _ in range(3):
        t, y = _synthetic_time_series()
        panel.plot(t, y)
    # Catalog overlays attach to the panel manager; use a local catalog path
    # if one exists, otherwise the function documents the API usage.
    try:
        add_catalog_overlay(panel, "My Catalogs//events", override_color="red")
    except Exception:
        pass  # catalog may not exist in all test environments


def graphic_primitives_boundary(panel: PlotPanel) -> None:
    """Annotated event: curved arrow + text labels at a boundary crossing."""
    panel.clear()
    t, y = _synthetic_time_series()
    plot, _ = panel.plot(t, y, name="magnetic field")
    CurvedLine(
        plot,
        start=(20.0, 0.5),
        stop=(40.0, 1.5),
        stop_termination=LineTermination.Arrow,
    )
    Text(plot, "boundary crossing", x=45.0, y=1.6)
    RectangularSpan(plot, x1=18.0, y1=-2.0, x2=42.0, y2=2.0, color="rgba(200, 50, 50, 0.15)")


def theme_grid_screenshot(panel: PlotPanel) -> None:
    """Capture the same panel in four palettes (light, dark, neutral, space).

    Run this function, screenshot, then switch themes and repeat.
    """
    panel.clear()
    t, y = _synthetic_time_series()
    panel.plot(t, y, name="signal")
    apply_theme("dark")


if __name__ == "__main__":
    from SciQLop.user_api.plot import create_plot_panel

    panel = create_plot_panel()
    hero_mms_magnetopause_crossing(panel)
