"""``debug=True`` validates each result against what the product declares.

Before: the provider ran its validator with no product type and no labels, so
shape checks never fired; datetime-annotated callbacks handed the validator
datetimes it compared with float timestamps; and every finding, a raised
exception included, only reached the log while the plot stayed empty.
"""
from datetime import datetime

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def _debug_vector(callback):
    from SciQLop.components.plotting.backend.easy_provider import EasyVector
    return EasyVector(path=f"vp/{id(callback):x}", get_data_callback=callback,
                      components_names=["x", "y", "z"], metadata={}, debug=True)


def _fetch(p):
    return p._get_data("node", 0.0, 10.0)


def test_a_vector_with_too_few_columns_is_reported():
    p = _debug_vector(lambda start, stop: (np.linspace(start, stop, 5), np.zeros((5, 2))))
    with pytest.raises(ValueError, match=r"vector \(3 components\)"):
        _fetch(p)


def test_a_datetime_annotated_callback_validates_cleanly():
    def cb(start: datetime, stop: datetime):
        return np.linspace(0.0, 10.0, 5), np.zeros((5, 3))
    assert _fetch(_debug_vector(cb)) is not None


def test_a_raising_callback_reaches_the_caller():
    def cb(start: float, stop: float):
        raise RuntimeError("archive unreachable")
    with pytest.raises(RuntimeError, match="archive unreachable"):
        _fetch(_debug_vector(cb))
