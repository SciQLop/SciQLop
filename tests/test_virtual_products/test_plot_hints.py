"""ISTP plot hints flow automatically from a virtual product whose callback
returns a SpeasyVariable. Mirrors what speasy_provider does for inventory
products — the user_api VP wrappers must not be the odd one out."""
from datetime import datetime

import numpy as np
import pytest
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis, VariableAxis


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def _time_axis(n=4):
    t0 = np.datetime64("2024-01-01T00:00:00", "ns")
    return VariableTimeAxis(values=t0 + np.arange(n) * np.timedelta64(1, "s"))


def _scalar_variable(name="Vsw", unit="km/s", meta=None):
    container_meta = dict(meta or {})
    if unit is not None:
        container_meta.setdefault("UNITS", unit)
    return SpeasyVariable(
        axes=[_time_axis()],
        values=DataContainer(values=np.arange(4, dtype=float).reshape(-1, 1),
                             meta=container_meta, name=name, is_time_dependent=True),
        columns=[name],
    )


def _spectrogram_variable(z_meta=None, freq_meta=None):
    n_t, n_f = 4, 3
    time = _time_axis(n_t)
    freq = VariableAxis(values=np.array([10.0, 20.0, 30.0]),
                        meta=freq_meta or {}, name="frequency", is_time_dependent=False)
    z = DataContainer(values=np.ones((n_t, n_f)), meta=z_meta or {},
                      name="PSD", is_time_dependent=True)
    return SpeasyVariable(axes=[time, freq], values=z)


def _make(cls, callback, **kw):
    from SciQLop.user_api.virtual_products import (
        VirtualScalar, VirtualVector, VirtualSpectrogram,
    )
    path = f"vp/test/{id(callback):x}"
    if cls is VirtualScalar:
        return VirtualScalar(path, callback, label=kw.get("label", "x"))
    if cls is VirtualVector:
        return VirtualVector(path, callback, labels=kw.get("labels", ["bx", "by", "bz"]))
    if cls is VirtualSpectrogram:
        return VirtualSpectrogram(path, callback)
    raise ValueError(cls)


def _hints(vp, variable):
    return vp._impl.plot_hints_from_variable(None, variable)


def test_scalar_vp_returning_speasy_variable_picks_name_and_unit():
    def cb(start: float, stop: float) -> SpeasyVariable:
        return _scalar_variable()

    from SciQLop.user_api.virtual_products import VirtualScalar
    vp = _make(VirtualScalar, cb)
    h = _hints(vp, _scalar_variable(name="Vsw", unit="km/s"))
    assert h.y.label == "Vsw"
    assert h.y.unit == "km/s"
    assert h.y.composed_label() == "Vsw [km/s]"


def test_scalar_vp_meta_istp_attrs_take_precedence():
    from SciQLop.user_api.virtual_products import VirtualScalar
    vp = _make(VirtualScalar, lambda s, e: None)
    var = _scalar_variable(
        name="Vsw", unit="km/s",
        meta={"LABLAXIS": "Solar wind speed", "UNITS": "km s^-1",
              "SCALETYP": "log", "VALIDMIN": 0.0, "VALIDMAX": 2000.0},
    )
    h = _hints(vp, var)
    assert h.y.label == "Solar wind speed"
    assert h.y.unit == "km s^-1"
    assert h.y.scale == "log"
    assert h.y.valid_range == (0.0, 2000.0)


def test_spectrogram_vp_routes_main_axis_to_z_and_depend1_to_y2():
    from SciQLop.user_api.virtual_products import VirtualSpectrogram
    vp = _make(VirtualSpectrogram, lambda s, e: None)
    var = _spectrogram_variable(
        z_meta={"LABLAXIS": "PSD", "UNITS": "nT^2/Hz", "SCALETYP": "log"},
        freq_meta={"LABLAXIS": "f", "UNITS": "Hz", "SCALETYP": "log"},
    )
    h = _hints(vp, var)
    assert h.display_type == "spectrogram"
    assert h.z.label == "PSD"
    assert h.z.unit == "nT^2/Hz"
    assert h.z.scale == "log"
    assert h.y2.label == "f"
    assert h.y2.unit == "Hz"
    assert h.y2.scale == "log"


def test_vector_vp_component_labels_passed_through():
    from SciQLop.user_api.virtual_products import VirtualVector
    vp = _make(VirtualVector, lambda s, e: None,
               labels=["bx", "by", "bz"])
    var = SpeasyVariable(
        axes=[_time_axis()],
        values=DataContainer(values=np.zeros((4, 3)),
                             meta={"LABLAXIS": "B", "UNITS": "nT"},
                             name="B", is_time_dependent=True),
        columns=["bx", "by", "bz"],
    )
    h = _hints(vp, var)
    assert h.y.label == "B"
    assert h.y.unit == "nT"
    assert h.component_labels == ["bx", "by", "bz"]


def test_non_speasy_return_yields_empty_hints():
    from SciQLop.user_api.virtual_products import VirtualScalar
    vp = _make(VirtualScalar, lambda s, e: None)
    h = _hints(vp, (np.arange(4, dtype="float64"), np.zeros(4)))
    assert h.y.label is None
    assert h.y.unit is None
    assert h.display_type is None
