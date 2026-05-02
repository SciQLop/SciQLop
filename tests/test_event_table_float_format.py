"""Tests for the float formatting in the event table display."""
from .fixtures import *


def test_format_zero(qapp):
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    assert _format_meta_value(0.0) == "0"


def test_format_normal_range_uses_general_format(qapp):
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    assert _format_meta_value(1.5) == "1.5"
    assert _format_meta_value(123.456) == "123.456"
    assert _format_meta_value(0.5) == "0.5"


def test_format_very_small_uses_scientific(qapp):
    """The bug the user flagged: values like 1.23456e-8 must NOT round to 0."""
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    s = _format_meta_value(1.23456e-8)
    assert "e" in s
    assert s != "0"
    # Check the mantissa is recognizable
    assert s.startswith("1.234")


def test_format_just_below_threshold_uses_scientific(qapp):
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    s = _format_meta_value(0.0001)  # 1e-4 < 1e-3 threshold → scientific
    assert "e" in s


def test_format_above_threshold_uses_general(qapp):
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    s = _format_meta_value(0.01)  # 1e-2 ≥ 1e-3 → general
    assert "e" not in s


def test_format_very_large_uses_scientific(qapp):
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    s = _format_meta_value(1.23e8)  # ≥ 1e6 threshold → scientific
    assert "e" in s


def test_format_negative_small(qapp):
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    s = _format_meta_value(-1.5e-9)
    assert "e" in s
    assert s.startswith("-")


def test_int_unaffected(qapp):
    """Integers are not floats — they go through the generic branch."""
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    assert _format_meta_value(42) == "42"
    assert _format_meta_value(0) == "0"
