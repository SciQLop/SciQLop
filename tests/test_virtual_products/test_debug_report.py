"""`%%vp --debug` text report: what the cell output says about a VP run.

The debug panel's overlay is only visible on screen; agents driving SciQLop
and notebook users reading cell outputs need the same facts as text.
"""
import numpy as np
from speasy.core.data_containers import DataContainer
from speasy.products import SpeasyVariable, VariableTimeAxis

from SciQLop.user_api.virtual_products.report import debug_report
from SciQLop.user_api.virtual_products.validation import Diagnostic

START, STOP = 1760077119.0, 1760163519.0


def _variable(values, unit="km/s", columns=None):
    values = np.asarray(values, dtype=float)
    if values.ndim == 1:
        values = values[:, None]
    t0 = np.datetime64(int(START * 1e9), "ns")
    times = t0 + np.arange(len(values)) * np.timedelta64(60, "s")
    return SpeasyVariable(axes=[VariableTimeAxis(values=times)],
                          values=DataContainer(values=values, meta={"UNITS": unit}, name="v"),
                          columns=columns or [f"c{i}" for i in range(values.shape[1])])


def test_success_reports_inputs_result_and_checks():
    va = _variable(np.ones((30, 3)), columns=["vx", "vy", "vz"])
    result = _variable(np.linspace(1.0, 3.0, 30))
    text = debug_report("dv", START, STOP, inputs={"va": va}, data=result, elapsed=0.02)
    assert "dv" in text and "2025-10-10T06:18:39" in text
    assert "va:" in text and "(30, 3)" in text and "km/s" in text and "vx" in text
    assert "result:" in text and "(30, 1)" in text
    assert "min 1" in text and "median 2" in text and "max 3" in text
    assert "checks: ok" in text


def test_nan_share_is_reported():
    result = _variable([1.0, np.nan, 2.0, np.nan])
    assert "NaN 50%" in debug_report("f", START, STOP, inputs={}, data=result)


def test_all_nan_result_says_so_instead_of_statistics():
    result = _variable([np.nan, np.nan])
    text = debug_report("f", START, STOP, inputs={}, data=result)
    assert "all NaN" in text and "median" not in text


def test_error_reports_the_exception_and_no_result():
    try:
        raise ValueError("boom")
    except ValueError as e:
        error = e
    text = debug_report("f", START, STOP, inputs={}, error=error)
    assert "error: ValueError: boom" in text
    assert "result:" not in text


def test_traceback_keeps_the_user_frame_called_from_sciqlop_code():
    """The user's own frame came right after a SciQLop frame and was taken for
    that frame's source line, so the traceback showed no frame at all."""
    from pathlib import Path
    import SciQLop
    from SciQLop.user_api.virtual_products.validation import _filter_traceback
    magic = Path(SciQLop.__file__).parent / "user_api" / "virtual_products" / "magic.py"
    site = "/home/u/prog/SciQLop/.venv/lib/python3.14/site-packages/speasy/products/variable.py"
    text = "\n".join([
        "Traceback (most recent call last):",
        f'  File "{magic}", line 239, in vp_magic',
        "    cached_data = func(start, stop, **deps)",
        '  File "<cell>", line 3, in dv',
        "    return va - vp[:10]",
        f'  File "{site}", line 300, in __sub__',
        "    return self.__array_ufunc__(...)",
        "ValueError: operands could not be broadcast together",
    ])
    filtered = _filter_traceback(text)
    assert str(magic) not in filtered and "cached_data = func" not in filtered
    assert '"<cell>", line 3, in dv' in filtered and "return va - vp[:10]" in filtered
    assert site in filtered  # a checkout path containing "SciQLop/" is not SciQLop code
    assert filtered.endswith("ValueError: operands could not be broadcast together")


def test_diagnostics_replace_the_ok_line():
    result = _variable([1.0, 2.0])
    text = debug_report("f", START, STOP, inputs={}, data=result,
                        diagnostics=[Diagnostic("warning", "Data covers only 10% of range")])
    assert "warning: Data covers only 10% of range" in text
    assert "checks: ok" not in text


def test_tuple_result_and_missing_input_are_described():
    x = np.linspace(START, STOP, 5)
    text = debug_report("f", START, STOP, inputs={"b": None}, data=(x, np.arange(5.0)))
    assert "b: None" in text
    assert "result:" in text and "(5,)" in text
