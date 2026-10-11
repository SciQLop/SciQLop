"""A layer's markers are named after the layer in the legend.

Before: they showed up as "Component 0".
"""
import numpy as np
from ..fixtures import *  # noqa: F401,F403
from SciQLop.user_api.layers.types import Marker


def _sine(start: float, stop: float):
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)


def find_peaks(start: float, stop: float):
    return []


def test_layer_markers_are_named_after_the_layer(plot_panel):
    from SciQLop.user_api.layers._renderer import LayerRenderer
    plot, _ = plot_panel.plot_function(_sine)
    renderer = LayerRenderer(plot._get_impl_or_raise(), find_peaks)
    renderer._render_markers([Marker(time=1.0, value=0.5)])
    assert renderer._marker_graph.labels() == ["find_peaks"]
