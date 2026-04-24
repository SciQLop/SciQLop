import pytest


def test_extract_function():
    from SciQLop.user_api.layers.magic import _extract_function
    code = """
def find_peaks(start: float, stop: float, threshold: float = 0.5):
    return []
"""
    ns = {}
    func = _extract_function(code, ns)
    assert func.__name__ == "find_peaks"
    assert func(0.0, 1.0) == []


def test_extract_function_no_def_raises():
    from SciQLop.user_api.layers.magic import _extract_function
    with pytest.raises(ValueError, match="No function"):
        _extract_function("x = 1", {})


def test_parse_args_empty():
    from SciQLop.user_api.layers.magic import _parse_args
    args = _parse_args("")
    assert args.path is None
    assert args.debug is False


def test_parse_args_with_path():
    from SciQLop.user_api.layers.magic import _parse_args
    args = _parse_args("--path detectors/peaks")
    assert args.path == "detectors/peaks"


def test_parse_args_debug():
    from SciQLop.user_api.layers.magic import _parse_args
    args = _parse_args("--debug")
    assert args.debug is True
