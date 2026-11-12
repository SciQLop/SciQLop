"""Tests for _variable_as_istp_meta — SpeasyVariable → ISTP meta fallback."""
from types import SimpleNamespace

from SciQLop.core.speasy_hints import variable_as_istp_meta as _variable_as_istp_meta


def _axis(name=None, unit=None, meta=None):
    return SimpleNamespace(name=name, unit=unit, meta=meta or {})


def _var(**kw):
    defaults = dict(
        meta={}, name=None, unit=None, columns=None,
        valid_range=None, fill_value=None, axes=[_axis(name="time", unit="ns")],
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_empty_meta_uses_fallbacks():
    v = _var(name="imf", unit="nT", columns=["bx", "by", "bz"])
    meta = _variable_as_istp_meta(v)
    assert meta["UNITS"] == "nT"
    assert meta["LABLAXIS"] == "imf"
    assert meta["FIELDNAM"] == "imf"
    assert meta["LABL_PTR_1"] == ["bx", "by", "bz"]


def test_existing_meta_wins_over_fallbacks():
    v = _var(
        meta={"UNITS": "T", "LABLAXIS": "from_istp"},
        name="imf", unit="nT",
    )
    meta = _variable_as_istp_meta(v)
    assert meta["UNITS"] == "T"
    assert meta["LABLAXIS"] == "from_istp"
    assert meta["FIELDNAM"] == "imf"


def test_valid_range_list_tuples_flattened():
    v = _var(valid_range=([-1e31], [1e31]))
    meta = _variable_as_istp_meta(v)
    assert meta["VALIDMIN"] == -1e31
    assert meta["VALIDMAX"] == 1e31


def test_nan_fill_value_skipped():
    v = _var(fill_value=[float("nan")])
    assert "FILLVAL" not in _variable_as_istp_meta(v)


def test_scalar_fill_value_kept():
    v = _var(fill_value=-1e31)
    assert _variable_as_istp_meta(v)["FILLVAL"] == -1e31


def test_depend_1_built_from_axes():
    v = _var(
        axes=[
            _axis(name="time", unit="ns"),
            _axis(name="energy", unit="eV", meta={"SCALETYP": "log"}),
        ],
    )
    meta = _variable_as_istp_meta(v)
    d1 = meta["_depend_1"]
    assert d1["UNITS"] == "eV"
    assert d1["LABLAXIS"] == "energy"
    assert d1["SCALETYP"] == "log"


def test_depend_1_meta_wins_over_axis_attrs():
    v = _var(
        axes=[
            _axis(name="time", unit="ns"),
            _axis(name="ignored", unit="ignored", meta={"UNITS": "keV", "LABLAXIS": "E"}),
        ],
    )
    d1 = _variable_as_istp_meta(v)["_depend_1"]
    assert d1["UNITS"] == "keV"
    assert d1["LABLAXIS"] == "E"


def test_no_depend_1_when_single_axis():
    v = _var(axes=[_axis(name="time", unit="ns")])
    assert "_depend_1" not in _variable_as_istp_meta(v)


def test_jsonable_meta_converts_numpy_scalars_and_arrays():
    import numpy as np
    from SciQLop.core.speasy_hints import jsonable_meta

    out = jsonable_meta({
        "FILLVAL": np.float64(-1e31),
        "VALIDMIN": np.int32(3),
        "LABL_PTR_1": np.array(["bx", "by", "bz"]),
        "_depend_1": {"UNITS": np.str_("Hz"), "EDGES": np.array([1.0, 2.0])},
    })
    assert out["FILLVAL"] == -1e31 and isinstance(out["FILLVAL"], float)
    assert out["VALIDMIN"] == 3 and isinstance(out["VALIDMIN"], int)
    assert out["LABL_PTR_1"] == ["bx", "by", "bz"]
    assert out["_depend_1"]["UNITS"] == "Hz" and isinstance(out["_depend_1"]["UNITS"], str)
    assert out["_depend_1"]["EDGES"] == [1.0, 2.0]


def test_jsonable_meta_caps_long_sequences():
    import numpy as np
    from SciQLop.core.speasy_hints import jsonable_meta

    out = jsonable_meta({"BIG": np.arange(1000)})
    assert len(out["BIG"]) <= 257  # capped + sentinel
    assert isinstance(out["BIG"][-1], str) and "more" in out["BIG"][-1]


def test_jsonable_meta_is_qvariant_round_trippable(qtbot):
    """The sanitized dict must survive a real QVariantMap round-trip via the
    graph meta_data slot (Shiboken dict↔QVariantMap), since that's where it
    lands in production."""
    import numpy as np
    from SciQLop.core.speasy_hints import jsonable_meta
    from SciQLopPlots import SciQLopPlot

    plot = SciQLopPlot()
    qtbot.addWidget(plot)
    g = plot.plot(np.array([0.0, 1.0, 2.0]), np.array([0.0, 1.0, 2.0]))
    graph = g[1] if hasattr(g, "__iter__") else g
    payload = jsonable_meta({"UNITS": np.str_("nT"), "FILLVAL": np.float64(-1e31),
                             "LABL_PTR_1": np.array(["bx", "by"])})
    graph.set_metadata({"kind": "speasy", "data_meta": payload})
    back = graph.metadata()["data_meta"]
    assert back["UNITS"] == "nT"
    assert back["FILLVAL"] == -1e31
    assert list(back["LABL_PTR_1"]) == ["bx", "by"]
