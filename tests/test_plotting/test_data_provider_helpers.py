"""_is_time_sorted must match the np.diff(time) >= 0 formulation it replaces."""
import numpy as np

from SciQLop.components.plotting.backend.data_provider import _is_time_sorted


def test_strictly_increasing_time_is_sorted():
    t = np.array(['2025-01-01T00:00:00', '2025-01-01T00:00:01',
                  '2025-01-01T00:00:02'], dtype='datetime64[ns]')
    assert _is_time_sorted(t) is True


def test_out_of_order_pair_is_not_sorted():
    t = np.array(['2025-01-01T00:00:00', '2025-01-01T00:00:02',
                  '2025-01-01T00:00:01'], dtype='datetime64[ns]')
    assert _is_time_sorted(t) is False


def test_time_returning_to_an_earlier_point_mid_array_is_not_sorted():
    """Time jumping back mid-array (e.g. a merge seam), not just at the edges."""
    t = np.array(['2025-01-01T00:00:00', '2025-01-01T00:00:01', '2025-01-01T00:00:02',
                  '2025-01-01T00:00:03',
                  '2025-01-01T00:00:01',  # returns to an earlier point here
                  '2025-01-01T00:00:04', '2025-01-01T00:00:05'], dtype='datetime64[ns]')
    assert _is_time_sorted(t) is False


def test_repeated_timestamps_count_as_sorted():
    """Ties are allowed -- non-decreasing, not strictly increasing."""
    t = np.array(['2025-01-01T00:00:00', '2025-01-01T00:00:00',
                  '2025-01-01T00:00:01'], dtype='datetime64[ns]')
    assert _is_time_sorted(t) is True


def test_single_element_is_sorted():
    t = np.array(['2025-01-01T00:00:00'], dtype='datetime64[ns]')
    assert _is_time_sorted(t) is True


def test_empty_is_sorted():
    t = np.array([], dtype='datetime64[ns]')
    assert _is_time_sorted(t) is True


def test_checks_last_axis_like_np_diff_default():
    """np.diff(time) >= 0 (what this replaces) checks the last axis by
    default. Each row here is decreasing (unsorted along the last axis)
    but the columns happen to be increasing -- must match np.diff's answer,
    not silently switch to checking the first axis instead."""
    t = np.array([[0, 3, 2, 1], [10, 13, 12, 11]], dtype='int64').view('datetime64[ns]')
    assert _is_time_sorted(t) is False
