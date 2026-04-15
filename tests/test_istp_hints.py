"""Pure-Python tests for the ISTP → PlotHints adapter.

No Qt, no SciQLopPlots — these exercise the declarative translation only.
"""
from SciQLop.core.istp_hints import istp_metadata_to_hints
from SciQLop.core.plot_hints import PlotHints


def test_empty_meta():
    h = istp_metadata_to_hints({})
    assert h == PlotHints()


def test_none_meta():
    assert istp_metadata_to_hints(None) == PlotHints()


def test_scalar_line_basic():
    h = istp_metadata_to_hints({
        "UNITS": "nT",
        "SCALETYP": "linear",
        "FIELDNAM": "Bt",
    })
    assert h.display_type is None
    assert h.y.unit == "nT"
    assert h.y.scale == "linear"
    assert h.y.label == "Bt"
    assert h.y.composed_label() == "Bt [nT]"
    assert h.z == PlotHints().z


def test_lablaxis_primary_label():
    h = istp_metadata_to_hints({"UNITS": "nT", "LABLAXIS": "|B|"})
    assert h.y.label == "|B|"


def test_log_scale_variants():
    assert istp_metadata_to_hints({"SCALETYP": "log"}).y.scale == "log"
    assert istp_metadata_to_hints({"SCALETYP": "LinearScale"}).y.scale == "linear"
    assert istp_metadata_to_hints({"SCALETYP": "nope"}).y.scale is None


def test_spectrogram_routes_to_z():
    h = istp_metadata_to_hints({
        "DISPLAY_TYPE": "spectrogram",
        "UNITS": "1/(cm^2 s sr eV)",
        "SCALETYP": "log",
        "FIELDNAM": "flux",
    })
    assert h.display_type == "spectrogram"
    assert h.y.unit is None
    assert h.z.unit == "1/(cm^2 s sr eV)"
    assert h.z.scale == "log"
    assert h.z.label == "flux"


def test_display_type_line_alias():
    assert istp_metadata_to_hints({"DISPLAY_TYPE": "time_series"}).display_type == "line"
    assert istp_metadata_to_hints({"DISPLAY_TYPE": "timeseries"}).display_type == "line"


def test_valid_range():
    h = istp_metadata_to_hints({"VALIDMIN": 0.0, "VALIDMAX": 100.0})
    assert h.y.valid_range == (0.0, 100.0)


def test_valid_range_list_form():
    h = istp_metadata_to_hints({"VALIDMIN": [-1e31], "VALIDMAX": [100.0]})
    assert h.y.valid_range == (-1e31, 100.0)


def test_fillval_scalar():
    assert istp_metadata_to_hints({"FILLVAL": -1e31}).fill_value == -1e31


def test_fillval_list():
    assert istp_metadata_to_hints({"FILLVAL": [-1e31]}).fill_value == -1e31


def test_component_labels_labl_ptr_list():
    h = istp_metadata_to_hints({"LABL_PTR_1": ["Bx", "By", "Bz"]})
    assert h.component_labels == ["Bx", "By", "Bz"]


def test_component_labels_labl_ptr_python_literal():
    h = istp_metadata_to_hints({"LABL_PTR_1": "['Bx','By','Bz']"})
    assert h.component_labels == ["Bx", "By", "Bz"]


def test_component_labels_labl_ptr_comma_string():
    h = istp_metadata_to_hints({"LABL_PTR_1": "Bx,By,Bz"})
    assert h.component_labels == ["Bx", "By", "Bz"]


def test_component_labels_from_lablaxis_bracketed():
    h = istp_metadata_to_hints({"LABLAXIS": "[Bx,By,Bz]"})
    assert h.component_labels == ["Bx", "By", "Bz"]


def test_depend_1_populates_y2():
    h = istp_metadata_to_hints({
        "DISPLAY_TYPE": "spectrogram",
        "UNITS": "counts",
        "_depend_1": {
            "UNITS": "eV",
            "SCALETYP": "log",
            "LABLAXIS": "Energy",
        },
    })
    assert h.y2.unit == "eV"
    assert h.y2.scale == "log"
    assert h.y2.label == "Energy"
    assert h.y2.composed_label() == "Energy [eV]"


def test_depend_1_missing_is_empty_y2():
    h = istp_metadata_to_hints({"UNITS": "nT"})
    assert h.y2.unit is None
    assert h.y2.label is None


def test_units_without_label():
    h = istp_metadata_to_hints({"UNITS": "nT"})
    assert h.y.composed_label() == "[nT]"


def test_missing_validmin_only():
    h = istp_metadata_to_hints({"VALIDMIN": 0.0})
    assert h.y.valid_range is None
