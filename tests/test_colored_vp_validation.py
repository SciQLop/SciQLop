import numpy as np

from SciQLop.user_api.data_types import Colored
from SciQLop.user_api.virtual_products.validation import validate_with_data


def _errors(result):
    return [d.message for d in result.diagnostics if d.level == "error"]


def test_valid_colored_vector_has_no_errors():
    t = np.linspace(0.0, 10.0, 5)
    r = validate_with_data(Colored((t, np.zeros((5, 3))), color=t), "vector", None)
    assert _errors(r) == []
    assert isinstance(r.data, Colored)


def test_colour_of_the_wrong_length_is_an_error():
    t = np.linspace(0.0, 10.0, 5)
    r = validate_with_data(Colored((t, np.zeros((5, 3))), color=np.zeros(3)), "vector", None)
    assert any("colour" in m for m in _errors(r))


def test_two_dimensional_colour_is_an_error():
    t = np.linspace(0.0, 10.0, 5)
    r = validate_with_data(Colored((t, np.zeros((5, 3))), color=np.zeros((5, 2))), "vector", None)
    assert any("colour" in m for m in _errors(r))


def test_inner_data_is_still_checked():
    t = np.linspace(0.0, 10.0, 5)
    r = validate_with_data(Colored((t, np.zeros((5, 2))), color=t), "vector", None)
    assert any("components" in m for m in _errors(r))


def test_debug_panel_data_info_reads_through_colored():
    from SciQLop.user_api.virtual_products.debug import _extract_data_info
    t = np.linspace(0.0, 10.0, 5)
    assert _extract_data_info(Colored((t, np.zeros((5, 3))), color=t)) == (5, (5, 3), "float64")
