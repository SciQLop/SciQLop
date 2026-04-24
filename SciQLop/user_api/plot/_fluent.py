from __future__ import annotations

from typing import Any

from .enums import ScaleType
from ._panel import PlotPanel, create_plot_panel, plot_panel


class PanelBuilder:
    """Fluent API for constructing plot panels declaratively.

    Usage::

        panel = (fluent.new_panel()
            .plot("speasy//amda//b_gse")
            .plot("speasy//amda//v_gse")
            .y_range(-50, 50)
            .subplot()
                .plot("speasy//amda//density")
                .log_y()
            .time_range("2020-01-01", "2020-01-02"))
    """

    def __init__(self, panel: PlotPanel):
        self._panel = panel
        self._current_plot = None
        self._current_plot_index = -1

    @property
    def panel(self) -> PlotPanel:
        return self._panel

    def _require_current_plot(self):
        if self._current_plot is None:
            raise RuntimeError("No plot yet — call .plot() first")
        return self._current_plot

    def subplot(self) -> PanelBuilder:
        """Start a new subplot (axes) in the panel. Subsequent .plot() calls add graphs to this subplot."""
        self._current_plot = None
        return self

    def plot(self, *args, **kwargs) -> PanelBuilder:
        """Add a graph to the current subplot. Accepts the same arguments as PlotPanel.plot().

        If no subplot exists yet, one is created implicitly. Multiple .plot() calls
        without an intervening .subplot() overlay graphs on the same axes.
        """
        if self._current_plot is None:
            self._current_plot_index += 1
        result = self._panel.plot(*args, plot_index=self._current_plot_index, **kwargs)
        if result is not None:
            self._current_plot, _ = result
        return self

    def histogram2d(self, *args, **kwargs) -> PanelBuilder:
        """Add a 2D density histogram. Accepts the same arguments as PlotPanel.histogram2d().

        Creates a new subplot. Pass ``(x, y)`` arrays for static data or a
        callable ``f(start, stop) -> (x, y)`` for live updates on time-range changes.
        """
        self._current_plot_index += 1
        kwargs.setdefault("plot_index", self._current_plot_index)
        result = self._panel.histogram2d(*args, **kwargs)
        if result is not None:
            self._current_plot, _ = result
        return self

    def layer(self, func, **kwargs) -> PanelBuilder:
        """Attach an annotation layer to the current subplot.

        The layer callback ``f(start, stop, **knobs) -> list[Marker|Span|HLine]``
        is called on time-range changes and renders annotations on the subplot.
        """
        if self._current_plot is None:
            raise RuntimeError("No plot yet — call .plot() first to create a subplot")
        self._panel.add_layer(func, plot_index=self._current_plot_index, **kwargs)
        return self

    def y_range(self, lo: float, hi: float) -> PanelBuilder:
        """Set the Y-axis range of the current subplot."""
        self._require_current_plot().set_y_range(lo, hi)
        return self

    def log_y(self) -> PanelBuilder:
        """Set the current subplot's Y-axis to logarithmic scale."""
        self._require_current_plot().y_scale_type = ScaleType.Logarithmic
        return self

    def linear_y(self) -> PanelBuilder:
        """Set the current subplot's Y-axis to linear scale."""
        self._require_current_plot().y_scale_type = ScaleType.Linear
        return self

    def time_range(self, start, stop) -> PanelBuilder:
        """Set the time range for the entire panel. Accepts any datetime-like values."""
        from SciQLop.core import TimeRange
        self._panel.time_range = TimeRange(start, stop)
        return self


def new_panel() -> PanelBuilder:
    """Create a new plot panel and return a fluent builder for it."""
    return PanelBuilder(create_plot_panel())


def panel(name: str) -> PanelBuilder:
    """Get an existing plot panel by name and return a fluent builder for it."""
    existing = plot_panel(name)
    if existing is None:
        raise ValueError(f"No panel named '{name}'")
    return PanelBuilder(existing)
