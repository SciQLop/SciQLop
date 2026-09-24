import numpy as np
import pytest

from SciQLop.user_api.data_types import Colored


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


class _Recorder:
    """Stands in for a SciQLopLogger (a QObject that caplog cannot see)."""

    def __init__(self):
        self.errors = []

    def error(self, msg, *args, **kwargs):
        self.errors.append(msg % args if args else msg)

    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture
def errors(monkeypatch):
    from SciQLop.components.plotting.backend import data_provider, easy_provider
    rec = _Recorder()
    monkeypatch.setattr(data_provider, "log", rec)
    monkeypatch.setattr(easy_provider, "log", rec)
    return rec.errors


def _vector(callback, colored=True):
    from SciQLop.components.plotting.backend.easy_provider import EasyVector
    from SciQLop.components.plotting.backend.color_axis import ColorAxis
    return EasyVector(path=f"vp/{id(callback):x}", get_data_callback=callback,
                      components_names=["x", "y", "z"], metadata={},
                      color_axis=ColorAxis(label="|B|") if colored else None)


def _fetch(p):
    return p._get_data("node", 0.0, 10.0)


def test_colored_result_becomes_a_data_color_dict():
    t = np.linspace(0.0, 10.0, 5)
    xyz = np.random.rand(5, 3)
    c = np.arange(5.0)
    out = _fetch(_vector(lambda start, stop: Colored((t, xyz), color=c)))
    assert set(out) == {"data", "color"}
    assert np.allclose(out["data"][0], t)  # time goes through datetime64 and back
    assert np.array_equal(out["data"][1], xyz)
    assert np.array_equal(out["color"], c)


def test_unsorted_time_permutes_the_colour_with_the_data():
    t = np.array([3.0, 1.0, 2.0])
    xyz = np.array([[3, 3, 3], [1, 1, 1], [2, 2, 2]], dtype=float)
    c = np.array([30.0, 10.0, 20.0])
    out = _fetch(_vector(lambda start, stop: Colored((t, xyz), color=c)))
    assert np.allclose(out["data"][0], [1.0, 2.0, 3.0])
    assert np.array_equal(out["data"][1][:, 0], [1.0, 2.0, 3.0])
    assert np.array_equal(out["color"], [10.0, 20.0, 30.0])


def test_wrong_colour_length_is_rejected_with_an_error(errors):
    t = np.linspace(0.0, 10.0, 5)
    p = _vector(lambda start, stop: Colored((t, np.zeros((5, 3))), color=np.zeros(4)))
    assert _fetch(p) == []
    assert any("colour" in e for e in errors)


def test_coloured_vp_returning_plain_data_is_an_error(errors):
    t = np.linspace(0.0, 10.0, 5)
    p = _vector(lambda start, stop: (t, np.zeros((5, 3))))
    assert _fetch(p) == []
    assert any("Colored" in e for e in errors)


def test_plain_vp_returning_colored_is_an_error(errors):
    t = np.linspace(0.0, 10.0, 5)
    p = _vector(lambda start, stop: Colored((t, np.zeros((5, 3))), color=t), colored=False)
    assert _fetch(p) == []
    assert any("colored=True" in e for e in errors)


@pytest.mark.parametrize("color", [
    np.arange(5.0).reshape(5, 1),
    np.arange(5),
    np.arange(5).astype("datetime64[s]"),
])
def test_colour_dtypes_and_column_shape_become_float64(color):
    t = np.linspace(0.0, 10.0, 5)
    out = _fetch(_vector(lambda start, stop: Colored((t, np.zeros((5, 3))), color=color)))
    assert out["color"].dtype == np.float64 and out["color"].shape == (5,)
    assert np.array_equal(out["color"], np.arange(5.0))


def test_plain_vector_returning_three_arrays_is_unchanged():
    """Regression guard for the rejected 'three buffers mean colour' rule."""
    t = np.linspace(0.0, 10.0, 5)
    payload = (t, np.zeros(5), np.ones(5))
    out = _fetch(_vector(lambda start, stop: payload, colored=False))
    assert isinstance(out, tuple) and len(out) == 3


def test_color_axis_is_exposed_by_the_provider():
    p = _vector(lambda start, stop: None)
    assert p.color_axis("node").label == "|B|"
    assert _vector(lambda start, stop: None, colored=False).color_axis("node") is None
