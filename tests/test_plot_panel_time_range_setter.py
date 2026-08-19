"""``panel.time_range = (start, stop)`` end to end.

The pure tests in test_plot_api_catchup_pure cover ``as_time_range`` itself;
these drive the real PlotPanel setter, which used to call ``.start()`` on
whatever it was handed and so raised ``AttributeError: 'tuple' object has no
attribute 'start'`` on the obvious Python spelling.
"""
from datetime import datetime, timezone

import pytest

from SciQLop.core import TimeRange

T0 = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
T1 = T0 + 3600.0


def _panel(name):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.user_api.plot._panel import PlotPanel
    return PlotPanel(TimeSyncPanel(name))


def test_a_tuple_of_epochs(qtbot, qapp):
    panel = _panel("tr-epochs")
    panel.time_range = (T0, T1)
    assert (panel.time_range.start(), panel.time_range.stop()) \
        == pytest.approx((T0, T1))


def test_a_tuple_of_date_strings(qtbot, qapp):
    panel = _panel("tr-strings")
    panel.time_range = ("2020-01-01T00:00:00", "2020-01-01T01:00:00")
    assert (panel.time_range.start(), panel.time_range.stop()) \
        == pytest.approx((T0, T1))


def test_a_tuple_of_datetimes(qtbot, qapp):
    panel = _panel("tr-datetimes")
    panel.time_range = (datetime(2020, 1, 1, tzinfo=timezone.utc),
                        datetime(2020, 1, 1, 1, tzinfo=timezone.utc))
    assert (panel.time_range.start(), panel.time_range.stop()) \
        == pytest.approx((T0, T1))


def test_a_time_range_still_works(qtbot, qapp):
    panel = _panel("tr-timerange")
    panel.time_range = TimeRange(T0, T1)
    assert panel.time_range.stop() == pytest.approx(T1)


def test_a_zero_width_pair_is_still_refused(qtbot, qapp):
    """Coercion must not swallow the guard that catches unparsed dates."""
    panel = _panel("tr-zero-width")
    with pytest.raises(ValueError):
        panel.time_range = (T0, T0)
