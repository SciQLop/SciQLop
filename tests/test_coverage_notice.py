"""A product dropped on a panel whose window lies wholly outside the product's
coverage gets a notice offering to jump to its first (or last) data, keeping
the window length -- as the Speasy proxy's plot page does."""
from types import SimpleNamespace

import pytest

from tests.fixtures import *  # noqa: F401,F403

DAY = 86400.0
COVERAGE = (100 * DAY, 200 * DAY)


def _range(start, stop):
    from SciQLop.core import TimeRange
    return TimeRange(start, stop)


@pytest.mark.parametrize("window, expected", [
    ((250 * DAY, 252 * DAY), ("after", (198 * DAY, 200 * DAY))),
    ((10 * DAY, 11 * DAY), ("before", (100 * DAY, 101 * DAY))),
    ((150 * DAY, 151 * DAY), None),
    ((90 * DAY, 110 * DAY), None),
])
def test_out_of_coverage_offers_the_nearest_edge_with_the_same_length(window, expected):
    from SciQLop.components.plotting.ui.coverage_notice import out_of_coverage

    out = out_of_coverage(_range(*COVERAGE), _range(*window))

    if expected is None:
        assert out is None
    else:
        side, jump = out
        assert (side, (jump.start(), jump.stop())) == (expected[0], expected[1])


def test_unknown_coverage_offers_nothing():
    from SciQLop.components.plotting.ui.coverage_notice import out_of_coverage

    assert out_of_coverage(None, _range(0, DAY)) is None


def _fake_speasy(monkeypatch, start, stop):
    from datetime import datetime, timezone
    from SciQLop.plugins.speasy_provider import speasy_provider

    index = object()
    dt = SimpleNamespace(start_time=datetime.fromtimestamp(start, timezone.utc),
                         stop_time=datetime.fromtimestamp(stop, timezone.utc))
    fake = SimpleNamespace(
        inventories=SimpleNamespace(flat_inventories=SimpleNamespace(
            amda=SimpleNamespace(parameters={"p": index}))),
        amda=SimpleNamespace(parameter_range=lambda i: dt if i is index else None))
    monkeypatch.setattr(speasy_provider, "spz", fake)


def test_speasy_coverage_comes_from_the_inventory(monkeypatch):
    from SciQLop.plugins.speasy_provider.speasy_provider import speasy_coverage

    _fake_speasy(monkeypatch, *COVERAGE)

    coverage = speasy_coverage("amda/p")
    assert (coverage.start(), coverage.stop()) == COVERAGE
    assert speasy_coverage("amda/unknown") is None


def test_speasy_empty_coverage_is_unknown(monkeypatch):
    from SciQLop.plugins.speasy_provider.speasy_provider import speasy_coverage

    _fake_speasy(monkeypatch, 0, 0)

    assert speasy_coverage("amda/p") is None


@pytest.fixture
def product_with_coverage(qtbot, main_window, test_plugin, monkeypatch):
    from SciQLopPlots import ProductsModel
    from SciQLop.components.plotting.backend.data_provider import providers

    path = ["TestPlugin", "TestMultiComponent"]
    node = ProductsModel.node(path)
    assert node is not None
    monkeypatch.setattr(providers[node.provider()], "coverage",
                        lambda _node: _range(*COVERAGE), raising=False)
    return path


def _panel(main_window, window):
    panel = main_window.new_plot_panel()
    panel = getattr(panel, "_impl", panel)
    panel.time_range = _range(*window)
    return panel


def test_dropping_a_product_past_its_data_offers_its_last_data(qtbot, main_window,
                                                              product_with_coverage):
    from SciQLop.components.plotting.ui.coverage_notice import offer_jump_to_data

    panel = _panel(main_window, (250 * DAY, 252 * DAY))
    notice = offer_jump_to_data(panel, product_with_coverage)

    assert notice is not None and notice.isVisible()
    assert notice.jump_button.text() == "Go to last data"
    notice.jump_button.click()

    assert (panel.time_range.start(), panel.time_range.stop()) == (198 * DAY, 200 * DAY)
    qtbot.waitUntil(lambda: not notice.isVisible(), timeout=1000)


def test_no_notice_when_the_window_overlaps_the_data(main_window, product_with_coverage):
    from SciQLop.components.plotting.ui.coverage_notice import offer_jump_to_data

    panel = _panel(main_window, (150 * DAY, 151 * DAY))

    assert offer_jump_to_data(panel, product_with_coverage) is None


def test_moving_the_window_dismisses_the_notice(qtbot, main_window, product_with_coverage):
    from SciQLop.components.plotting.ui.coverage_notice import offer_jump_to_data

    panel = _panel(main_window, (10 * DAY, 11 * DAY))
    notice = offer_jump_to_data(panel, product_with_coverage)
    assert notice.jump_button.text() == "Go to first data"

    panel.time_range = _range(20 * DAY, 21 * DAY)

    qtbot.waitUntil(lambda: not notice.isVisible(), timeout=1000)


def test_the_drop_callback_offers_the_jump(qtbot, main_window, product_with_coverage,
                                          monkeypatch):
    from PySide6.QtCore import QMimeData
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui import time_sync_panel
    from SciQLop.components.plotting.ui.coverage_notice import CoverageNotice

    monkeypatch.setattr(time_sync_panel, "decode_mime", lambda _m: [product_with_coverage])
    panel = _panel(main_window, (250 * DAY, 252 * DAY))
    panel.create_plot(0, PlotType.TimeSeries)
    panel._product_plot_callback.call(panel.plots()[0], QMimeData())

    qtbot.waitUntil(lambda: any(n.isVisible() for n in panel.findChildren(CoverageNotice)),
                    timeout=1000)


@pytest.mark.parametrize("on_plot", [False, True], ids=["panel", "existing-plot"])
def test_every_plot_path_offers_the_jump(qtbot, main_window, product_with_coverage, on_plot):
    """Context menu, command palette, notebooks and agents all go through
    plot_product, not only the drop callback."""
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLop.components.plotting.ui.coverage_notice import CoverageNotice

    panel = _panel(main_window, (250 * DAY, 252 * DAY))
    if on_plot:
        panel.create_plot(0, PlotType.TimeSeries)
    if on_plot:
        plot_product(panel.plots()[0], product_with_coverage)
    else:
        plot_product(panel, product_with_coverage, plot_type=PlotType.TimeSeries)

    qtbot.waitUntil(lambda: any(n.isVisible() for n in panel.findChildren(CoverageNotice)),
                    timeout=1000)
