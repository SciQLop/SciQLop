"""Regression tests for the per-plot PlotHints registry eviction logic.

The registry is keyed by C++ pointer addresses — when a plot is destroyed
*without* firing its `destroyed` signal (e.g. during interpreter shutdown
or when the plot has no signal at all), a fresh plot allocated at the
same address would otherwise inherit stale hints from the dead one.
The lookup path defends against this by evicting any entry whose
`_plot` Python wrapper reports `shiboken6.isValid(...) == False`.
"""
from .fixtures import *  # noqa: F401,F403  — provides qapp_cls

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tsp(qapp):
    """Lazy import — `time_sync_panel` requires a QApplication at import time
    because SciQLop.core.models registers a QApplication-static singleton."""
    from SciQLop.components.plotting.ui import time_sync_panel
    time_sync_panel._PLOT_REGISTRIES.clear()
    yield time_sync_panel
    time_sync_panel._PLOT_REGISTRIES.clear()


def _fake_plot(key: int):
    return MagicMock(name=f"plot@{key}")


def test_stale_registry_evicted_on_next_access(tsp):
    plot_a = _fake_plot(0xAAAA)
    plot_b = _fake_plot(0xAAAA)

    with patch.object(tsp, "_plot_key", side_effect=lambda p: 0xAAAA):
        with patch("shiboken6.isValid", return_value=True):
            reg_a = tsp._get_or_create_registry(plot_a)
            assert reg_a is not None
            assert tsp._PLOT_REGISTRIES[0xAAAA] is reg_a

        with patch("shiboken6.isValid", return_value=False):
            reg_b = tsp._get_or_create_registry(plot_b)

    assert reg_b is not None
    assert reg_b is not reg_a
    assert tsp._PLOT_REGISTRIES[0xAAAA] is reg_b


def test_live_registry_reused(tsp):
    plot = _fake_plot(0xBBBB)

    with patch.object(tsp, "_plot_key", side_effect=lambda p: 0xBBBB), \
            patch("shiboken6.isValid", return_value=True):
        first = tsp._get_or_create_registry(plot)
        second = tsp._get_or_create_registry(plot)

    assert first is second


def test_unkeyable_plot_returns_throwaway_registry(tsp):
    """When a plot has no usable C++ pointer (e.g. a non-Shiboken object),
    `_plot_key` falls back to `id(plot)` rather than `None`, but the
    function must still tolerate `key is None` — the fallback path
    returns a fresh registry that is intentionally not stored."""
    plot = _fake_plot(0xCCCC)

    with patch.object(tsp, "_plot_key", return_value=None):
        reg = tsp._get_or_create_registry(plot)

    assert reg is not None
    assert reg not in tsp._PLOT_REGISTRIES.values()
