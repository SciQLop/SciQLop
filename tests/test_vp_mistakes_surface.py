"""A virtual product that cannot be drawn says why, on its plot.

Before: an exception in a product callback only reached the log, and several
mistakes (a DataFrame, time in milliseconds, a colour mismatch) silently became
"no data". Either way the user saw an empty plot.
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import itertools

import numpy as np
import pandas as pd
import pytest

START, STOP = "2020-01-01T00:00", "2020-01-01T06:00"
_ids = itertools.count()


def _xs(start, stop):
    return np.linspace(start, stop, 100)


def _plot_vp(plot_panel, callback, **kwargs):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    vp = create_virtual_product(f"mistakes//vp{next(_ids)}", callback, VirtualProductType.Scalar,
                                labels=["v"], **kwargs)
    plot_panel.time_range = (START, STOP)
    plot, graph = plot_panel.plot(vp)
    return plot._get_impl_or_raise(), graph._get_impl_or_raise()


def _overlay_text_after_fetch(qtbot, plot):
    qtbot.waitUntil(lambda: plot.overlay().text() != "", timeout=5000)
    return plot.overlay().text()


def raises(start: float, stop: float):
    raise RuntimeError("upstream archive unreachable")


def dataframe(start: float, stop: float):
    return pd.DataFrame({"v": np.ones(100)}, index=pd.to_datetime(_xs(start, stop), unit="s"))


def milliseconds(start: float, stop: float):
    return _xs(start, stop) * 1000.0, np.ones(100)


def plain_but_declared_colored(start: float, stop: float):
    return _xs(start, stop), np.ones(100)


@pytest.mark.parametrize("callback, kwargs, expected", [
    (raises, {}, "upstream archive unreachable"),
    (dataframe, {}, "DataFrame"),
    (milliseconds, {}, "none inside the requested range"),
    (plain_but_declared_colored, {"colored": True}, "Colored"),
])
def test_a_broken_virtual_product_says_why_on_its_plot(plot_panel, qtbot, callback, kwargs, expected):
    plot, _ = _plot_vp(plot_panel, callback, **kwargs)
    assert expected in _overlay_text_after_fetch(qtbot, plot)


def test_a_list_is_accepted_like_a_tuple(plot_panel, qtbot):
    def as_list(start: float, stop: float):
        return [_xs(start, stop), np.ones(100)]

    _, graph = _plot_vp(plot_panel, as_list)
    def n_points():
        data = graph.data()
        return len(data[0]) if data and data[0] is not None else 0

    qtbot.waitUntil(lambda: n_points() == 100, timeout=5000)


def test_no_data_is_said_plainly_and_is_not_an_error(plot_panel, qtbot):
    from SciQLopPlots import OverlayLevel

    def nothing(start: float, stop: float):
        return None

    plot, _ = _plot_vp(plot_panel, nothing)
    text = _overlay_text_after_fetch(qtbot, plot)
    assert text.startswith("No data for ") and text.endswith(" in this time range.")
    assert plot.overlay().level() == OverlayLevel.Warning


@pytest.fixture
def no_data_notice():
    from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings
    before = PlotBackendSettings().no_data_notice

    def choose(value):
        with PlotBackendSettings() as settings:
            settings.no_data_notice = value

    yield choose
    choose(before)


def _nothing(start: float, stop: float):
    return None


def test_the_no_data_line_can_be_turned_off(plot_panel, qtbot, no_data_notice):
    no_data_notice("Off")
    plot, _ = _plot_vp(plot_panel, _nothing)
    qtbot.wait(1000)
    assert plot.overlay().text() == ""


def test_the_no_data_line_hides_itself_and_stays_away_while_the_gap_lasts(plot_panel, qtbot, monkeypatch):
    import SciQLop.components.plotting.ui.time_sync_panel as panel_module
    monkeypatch.setattr(panel_module, "_NO_DATA_NOTE_MS", 300)
    plot, _ = _plot_vp(plot_panel, _nothing)
    _overlay_text_after_fetch(qtbot, plot)
    qtbot.waitUntil(lambda: plot.overlay().text() == "", timeout=5000)
    plot_panel.time_range = ("2020-01-02T00:00", "2020-01-02T06:00")
    qtbot.wait(1000)
    assert plot.overlay().text() == ""


def test_the_no_data_line_can_stay_until_data_comes(plot_panel, qtbot, monkeypatch, no_data_notice):
    import SciQLop.components.plotting.ui.time_sync_panel as panel_module
    monkeypatch.setattr(panel_module, "_NO_DATA_NOTE_MS", 300)
    no_data_notice("Until data comes")
    plot, _ = _plot_vp(plot_panel, _nothing)
    _overlay_text_after_fetch(qtbot, plot)
    qtbot.wait(1000)
    assert plot.overlay().text() != ""


def test_the_no_data_line_comes_back_for_the_next_gap(qtbot, plot_panel):
    from SciQLop.components.plotting.ui.time_sync_panel import _PlotErrorReporter
    plot, _ = _plot_vp(plot_panel, lambda start, stop: (_xs(start, stop), np.ones(100)))
    reporter = _PlotErrorReporter("p")
    reporter.attach(plot)
    text = plot.overlay().text
    reporter.report_no_data()
    qtbot.waitUntil(lambda: "No data for p" in text(), timeout=5000)
    reporter._hide_no_data_note()
    reporter.report_no_data()
    qtbot.wait(300)
    assert text() == ""
    reporter.clear()
    reporter.report_no_data()
    qtbot.waitUntil(lambda: "No data for p" in text(), timeout=5000)


def test_the_no_data_line_goes_away_when_data_comes(plot_panel, qtbot):
    answers = iter([None])

    def late(start: float, stop: float):
        return next(answers, (_xs(start, stop), np.ones(100)))

    plot, _ = _plot_vp(plot_panel, late)
    _overlay_text_after_fetch(qtbot, plot)
    plot_panel.time_range = ("2020-01-02T00:00", "2020-01-02T06:00")
    qtbot.waitUntil(lambda: plot.overlay().text() == "", timeout=5000)


def test_a_failed_download_is_said_plainly_on_the_plot(plot_panel, qtbot):
    import urllib3
    from urllib3.exceptions import MaxRetryError, NewConnectionError

    def unreachable(start: float, stop: float):
        raise MaxRetryError(urllib3.HTTPSConnectionPool("amda.irap.omp.eu"), "/x",
                            NewConnectionError(None, "refused"))

    plot, _ = _plot_vp(plot_panel, unreachable)
    text = _overlay_text_after_fetch(qtbot, plot)
    assert "amda.irap.omp.eu could not be reached" in text and "Max retries" not in text


def test_a_failing_callback_on_a_projection_says_why_on_its_first_pane(plot_panel, qtbot):
    from SciQLopPlots import GraphType, PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import _CallbackErrorOverlay
    z = np.zeros(1)
    proj, _ = plot_panel._get_impl_or_raise().plot([z, z, z, z], plot_type=PlotType.Projections,
                                                   graph_type=GraphType.ParametricCurve, labels=["", "", ""])
    reporter = _CallbackErrorOverlay(raises)
    reporter.attach(proj)
    reporter(0.0, 1.0)
    qtbot.waitUntil(lambda: "upstream archive unreachable" in proj.subplot(0).overlay().text(), timeout=5000)


@pytest.mark.parametrize("attach_first", [True, False])
def test_an_error_is_shown_whether_it_arrives_before_or_after_attach(plot_panel, qtbot, attach_first):
    from SciQLop.components.plotting.ui.time_sync_panel import _PlotErrorReporter
    plot, _ = _plot_vp(plot_panel, lambda start, stop: None)
    reporter = _PlotErrorReporter("late")
    steps = [lambda: reporter.attach(plot), lambda: reporter.report("boom")]
    for step in (steps if attach_first else steps[::-1]):
        step()
    qtbot.waitUntil(lambda: "late: boom" in plot.overlay().text(), timeout=5000)



def test_two_products_on_one_plot_each_keep_their_message(plot_panel, qtbot):
    from SciQLopPlots import OverlayLevel
    from SciQLop.components.plotting.ui.time_sync_panel import _PlotErrorReporter
    plot, _ = _plot_vp(plot_panel, lambda start, stop: (_xs(start, stop), np.ones(100)))
    broken, empty = _PlotErrorReporter("broken"), _PlotErrorReporter("empty")
    for reporter in (broken, empty):
        reporter.attach(plot)
    text = plot.overlay().text
    broken.report("boom")
    empty.report_no_data()
    qtbot.waitUntil(lambda: "broken: boom" in text() and "No data for empty" in text(), timeout=5000)
    assert plot.overlay().level() == OverlayLevel.Error
    broken.clear()
    qtbot.waitUntil(lambda: "boom" not in text(), timeout=5000)
    assert "No data for empty" in text() and plot.overlay().level() == OverlayLevel.Warning
    empty.clear()
    qtbot.waitUntil(lambda: text() == "", timeout=5000)


def test_removing_a_product_removes_its_line(plot_panel, qtbot):
    plot, graph = _plot_vp(plot_panel, lambda start, stop: None)
    _overlay_text_after_fetch(qtbot, plot)
    graph.deleteLater()
    qtbot.waitUntil(lambda: plot.overlay().text() == "", timeout=5000)
