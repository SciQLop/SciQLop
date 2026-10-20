import numpy as np
import pytest

from SciQLop.components.comparison.backend.difference import (
    ComparisonMismatch, colormap_relation, line_relation, mask_fill, relate, resample)


def test_resample_is_nan_outside_source_span():
    out = resample(np.array([10.0, 20.0]), np.array([1.0, 3.0]), np.array([5.0, 15.0, 25.0]))
    assert np.isnan(out[0]) and out[1] == 2.0 and np.isnan(out[2])


def test_resample_nearest():
    assert resample(np.array([0.0, 10.0]), np.array([1.0, 2.0]), np.array([4.0, 6.0]), "nearest").tolist() == [1.0, 2.0]


def test_resample_nearest_is_nan_outside_source_span():
    out = resample(np.array([10.0, 20.0]), np.array([1.0, 3.0]), np.array([5.0, 25.0]), "nearest")
    assert np.isnan(out).all()


def test_resample_columns_and_empty_source():
    out = resample(np.array([0.0, 2.0]), np.array([[0.0, 10.0], [2.0, 20.0]]), np.array([1.0]))
    assert out.tolist() == [[1.0, 15.0]]
    assert np.isnan(resample(np.array([]), np.array([]), np.array([1.0, 2.0]))).all()


def test_line_relation_difference_on_a_grid():
    t = np.array([0.0, 1.0, 2.0])
    _, d = line_relation([t, np.array([[3.0], [3.0], [3.0]])], [t, np.array([[1.0], [2.0], [3.0]])], "difference", "linear")
    assert d[:, 0].tolist() == [2.0, 1.0, 0.0]


def test_line_relation_nan_where_b_does_not_cover_a():
    ta, tb = np.array([0.0, 1.0, 2.0]), np.array([1.0, 2.0])
    _, d = line_relation([ta, np.ones(3)], [tb, np.ones(2)], "difference", "linear")
    assert np.isnan(d[0]) and d[1:].tolist() == [0.0, 0.0]


def test_component_mismatch_raises():
    t = np.array([0.0, 1.0])
    with pytest.raises(ComparisonMismatch, match="components"):
        line_relation([t, np.ones((2, 3))], [t, np.ones((2, 1))], "difference", "linear")


def test_log_ratio_of_nonpositive_is_nan():
    assert np.isnan(relate(np.array([1.0]), np.array([0.0]), "log_ratio")[0])


def test_ratio_by_zero_is_nan_not_inf():
    assert np.isnan(relate(np.array([1.0]), np.array([0.0]), "ratio")[0])


def test_unknown_operation_lists_the_valid_ones():
    with pytest.raises(ValueError, match="difference.*ratio.*log_ratio"):
        relate(np.ones(1), np.ones(1), "sum")


def test_mask_fill_hides_istp_fill():
    out = mask_fill(np.array([1.0, -1e31, 2.0, -999.0]), -999.0)
    assert out[0] == 1.0 and np.isnan(out[1]) and np.isnan(out[3])


def test_colormap_relation_on_a_grid():
    t = np.array([0.0, 1.0]); y = np.array([1.0, 2.0])
    _, y_out, d = colormap_relation([t, y, np.full((2, 2), 4.0)], [t, y, np.full((2, 2), 2.0)], "ratio", "linear")
    assert y_out.tolist() == [1.0, 2.0] and (d == 2.0).all()


def test_colormap_bins_mismatch_raises():
    t = np.array([0.0, 1.0]); z = np.ones((2, 2))
    with pytest.raises(ComparisonMismatch, match="bins"):
        colormap_relation([t, np.array([1.0, 2.0]), z], [t, np.array([1.0, 3.0]), z], "log_ratio", "linear")


def test_colormap_time_varying_bins_must_be_constant():
    t = np.array([0.0, 1.0]); z = np.ones((2, 2))
    moving = np.array([[1.0, 2.0], [1.0, 3.0]])
    with pytest.raises(ComparisonMismatch, match="bins"):
        colormap_relation([t, moving, z], [t, moving, z], "difference", "linear")


def test_line_relation_1d_against_single_column_keeps_a_shape():
    t = np.array([0.0, 1.0, 2.0])
    _, d = line_relation([t, np.array([3.0, 4.0, 5.0])], [t, np.array([[1.0], [1.0], [1.0]])], "difference", "linear")
    assert d.shape == (3,) and d.tolist() == [2.0, 3.0, 4.0]


def test_bins_with_nan_rows_still_match():
    import numpy as np
    from SciQLop.components.comparison.backend.difference import colormap_relation
    t = np.array([0.0, 1.0])
    y = np.array([[1.0, np.nan], [1.0, np.nan]])
    z = np.ones((2, 2))
    out = colormap_relation([t, y, z], [t, y, 2 * z], "difference", "linear")
    assert np.allclose(out[2], -1.0)


def test_resample_from_an_empty_time_axis_is_all_nan():
    from SciQLop.components.comparison.backend.difference import resample
    out = resample(np.array([]), np.array([1.0, 2.0]), np.array([1.0, 3.0]))
    assert out.shape == (2,) and np.isnan(out).all()
    out = resample(np.array([]), np.ones((2, 3)), np.array([1.0]))
    assert out.shape == (1, 3) and np.isnan(out).all()
