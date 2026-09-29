import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def _make_spectrogram(callback):
    from SciQLop.components.plotting.backend.easy_provider import EasySpectrogram
    return EasySpectrogram(path="vp/test_spec", get_data_callback=callback, metadata={})


def test_no_data_returns_empty_arrays_without_error_log(monkeypatch):
    """A callback returning None (no data in range) is a routine outcome, not
    a bug — it must not be logged at ERROR level via an unpack exception."""
    from SciQLop.components.plotting.ui import time_sync_panel
    from SciQLop.components.plotting.ui.time_sync_panel import _specgram_callback

    errors = []
    monkeypatch.setattr(time_sync_panel.log, "error", lambda *a, **k: errors.append(a))

    def f(start: float, stop: float):
        return None

    p = _make_spectrogram(f)
    cb = _specgram_callback(provider=p, node=None)

    x, y, z = cb(0.0, 1.0)

    assert x.size == 0 and y.size == 0 and z.size == 0
    assert errors == []


def test_fetch_raising_is_still_logged_and_returns_empty_arrays(monkeypatch):
    """If `_fetch` itself raises (e.g. provider._get_data blows up before it
    gets a chance to convert the error to []), it must still be surfaced at
    ERROR level — distinct from the routine "no data" case."""
    from SciQLop.components.plotting.ui import time_sync_panel
    from SciQLop.components.plotting.ui.time_sync_panel import _specgram_callback

    errors = []
    monkeypatch.setattr(time_sync_panel.log, "error", lambda *a, **k: errors.append(a))

    class _RaisingProvider:
        def _get_data(self, node, start, stop, on_variable=None, knobs=None):
            raise RuntimeError("boom")

    cb = _specgram_callback(provider=_RaisingProvider(), node=None)

    x, y, z = cb(0.0, 1.0)

    assert x.size == 0 and y.size == 0 and z.size == 0
    assert len(errors) == 1


def test_real_data_still_flows_through(monkeypatch):
    from SciQLop.components.plotting.ui import time_sync_panel
    from SciQLop.components.plotting.ui.time_sync_panel import _specgram_callback

    errors = []
    monkeypatch.setattr(time_sync_panel.log, "error", lambda *a, **k: errors.append(a))

    def f(start: float, stop: float):
        x = np.linspace(start, stop, 4)
        y = np.array([1.0, 2.0, 3.0])
        z = np.zeros((4, 3))
        return x, y, z

    p = _make_spectrogram(f)
    cb = _specgram_callback(provider=p, node=None)

    x, y, z = cb(0.0, 1.0)

    assert x.shape == (4,)
    assert y.shape == (3,)
    assert z.shape == (4, 3)
    assert errors == []


def _spectrogram_without_y_axis(n_rows: int, n_channels: int = 3):
    """What some AMDA spectrogram products return: time plus 2D values, no
    second axis (GH #144)."""
    from speasy.core import epoch_to_datetime64
    from speasy.core.data_containers import DataContainer
    from speasy.products import SpeasyVariable, VariableTimeAxis

    epoch = np.arange(n_rows, dtype=np.float64)
    values = np.arange(n_rows * n_channels, dtype=np.float64).reshape(n_rows, n_channels) + 1.0
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(epoch))],
                          values=DataContainer(values=values, name="flux"))


def _collect_errors(monkeypatch):
    from SciQLop.components.plotting.ui import time_sync_panel
    errors = []
    monkeypatch.setattr(time_sync_panel.log, "error", lambda *a, **k: errors.append(a))
    return errors


def test_spectrogram_without_y_axis_uses_the_channel_index(monkeypatch):
    from SciQLop.components.plotting.ui.time_sync_panel import _specgram_callback

    errors = _collect_errors(monkeypatch)
    cb = _specgram_callback(provider=_make_spectrogram(lambda start, stop: _spectrogram_without_y_axis(5)),
                            node=None)

    x, y, z = cb(0.0, 10.0)

    assert x.shape == (5,)
    assert list(y) == [0.0, 1.0, 2.0]
    assert z.shape == (5, 3)
    assert cb.last_error is None
    assert errors == []


def test_a_two_array_result_uses_the_channel_index(monkeypatch):
    from SciQLop.components.plotting.ui.time_sync_panel import _specgram_callback

    errors = _collect_errors(monkeypatch)

    def f(start: float, stop: float):
        return np.linspace(start, stop, 4), np.ones((4, 2))

    x, y, z = _specgram_callback(provider=_make_spectrogram(f), node=None)(0.0, 1.0)

    assert list(y) == [0.0, 1.0]
    assert z.shape == (4, 2)
    assert errors == []


def test_an_empty_window_is_no_data_not_an_error(monkeypatch):
    from SciQLop.components.plotting.ui.time_sync_panel import _specgram_callback

    errors = _collect_errors(monkeypatch)
    cb = _specgram_callback(provider=_make_spectrogram(lambda start, stop: _spectrogram_without_y_axis(0)),
                            node=None)

    x, y, z = cb(0.0, 1.0)

    assert x.size == 0 and z.size == 0
    assert cb.last_error is None
    assert errors == []
