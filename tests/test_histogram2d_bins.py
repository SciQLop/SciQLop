from .fixtures import *  # qapp_cls, sciqlop_resources, main_window, plot_panel
import numpy as np
import pytest
from SciQLop.user_api.plot.enums import BinStrategy


@pytest.fixture
def data():
    rng = np.random.default_rng(42)
    x = rng.lognormal(0, 1, 1000)
    y = rng.normal(0, 1, 1000)
    return x, y


def test_log_bins_are_monotonic(data, plot_panel):
    x, y = data
    _, hist = plot_panel.histogram2d(x, y, x_bins=20, x_bin_strategy=BinStrategy.Log)
    edges = hist.x_bin_edges
    assert np.all(np.diff(edges) > 0)
    assert edges[0] > 0


def test_explicit_edges_are_rejected(data, plot_panel):
    x, y = data
    edges = np.linspace(x.min(), x.max(), 11)
    with pytest.raises(NotImplementedError):
        plot_panel.histogram2d(x, y, x_bins=edges, x_bin_strategy=BinStrategy.Log)


def test_symlog_is_rejected_with_negatives(data, plot_panel):
    x, y = data
    x_with_neg = np.concatenate([x, -x])
    with pytest.raises(NotImplementedError):
        plot_panel.histogram2d(x_with_neg, y, x_bins=20, x_bin_strategy=BinStrategy.SymLog)
