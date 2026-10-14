import json
from pathlib import Path

import numpy as np
import pytest

from SciQLop.components.scenes import frames
from SciQLop.components.scenes.frames import FrameError, normalise_frame, rotation

DATA = Path(__file__).parent / "data"
DAY = np.datetime64("2015-10-16", "s").astype("int64")


@pytest.fixture
def recorded_3dview(monkeypatch):
    calls = []

    def fake(path, **params):
        calls.append(params)
        day = params["start"][:10].replace("-", "")
        return json.loads((DATA / f"gse_gsm_{day}.json").read_text())

    monkeypatch.setattr(frames, "_fetch_json", fake)
    frames._day_rotations.cache_clear()
    yield calls
    frames._day_rotations.cache_clear()


def test_unknown_equal_frames_are_refused(recorded_3dview):
    with pytest.raises(FrameError, match="FOO"):
        rotation("FOO", "FOO", np.array([0.0]))


def test_malformed_3dview_reply_raises_frame_error(monkeypatch):
    monkeypatch.setattr(frames, "_fetch_json", lambda path, **params: {})
    frames._day_rotations.cache_clear()
    try:
        with pytest.raises(FrameError, match="GSE.*GSM"):
            rotation("GSE", "GSM", np.array([float(DAY)]))
    finally:
        frames._day_rotations.cache_clear()


def test_empty_times_give_no_rotations_and_no_fetch(recorded_3dview):
    assert len(rotation("GSE", "GSM", np.array([]))) == 0 and recorded_3dview == []


def test_scalar_time_is_accepted(recorded_3dview):
    assert len(rotation("GSE", "GSM", float(DAY))) == 1


def test_equal_frames_are_identity_without_network(recorded_3dview):
    r = rotation("GSM", "GSM", np.array([0.0, 1.0]))
    assert np.allclose(r.as_matrix(), np.eye(3)) and recorded_3dview == []


def test_gse_to_gsm_rotates_about_x(recorded_3dview):
    r = rotation("GSE", "GSM", DAY + np.array([0.0, 3600.0]))
    assert np.allclose(r.apply([1.0, 0.0, 0.0]), [1.0, 0.0, 0.0], atol=1e-5)
    tilt = np.degrees(np.arctan2(r.as_matrix()[:, 1, 2], r.as_matrix()[:, 1, 1]))
    assert np.allclose(tilt, [12.65, 13.81], atol=0.05)  # matrices recorded 2026-10-13


def test_interpolated_rotations_stay_orthonormal(recorded_3dview):
    m = rotation("GSE", "GSM", DAY + np.linspace(0, 86000, 997)).as_matrix()
    assert np.allclose(m @ m.transpose(0, 2, 1), np.eye(3), atol=1e-9)


def test_rotation_spans_two_days(recorded_3dview):
    r = rotation("GSE", "GSM", DAY + np.array([86000.0, 87000.0]))
    assert len(r) == 2 and len(recorded_3dview) == 2


def test_frames_centred_on_different_bodies_are_refused():
    with pytest.raises(FrameError, match="MSO.*Mars.*MEME.*Mercury"):
        rotation("MSO", "MEME", np.array([0.0]))


def test_unreachable_3dview_raises_frame_error(monkeypatch):
    def down(path, **params):
        raise OSError("connection refused")

    monkeypatch.setattr(frames, "_fetch_json", down)
    frames._day_rotations.cache_clear()
    try:
        with pytest.raises(FrameError, match="GSE.*GSM.*connection refused"):
            rotation("GSE", "GSM", np.array([float(DAY)]))
    finally:
        frames._day_rotations.cache_clear()


@pytest.mark.parametrize("raw, frame", [("GSE>Geocentric Solar Ecliptic", "GSE"), (" gsm ", "GSM"), ("MESO", "MESO")])
def test_frame_names_from_metadata_are_normalised(raw, frame):
    assert normalise_frame(raw) == frame


def test_unknown_frame_is_refused():
    with pytest.raises(FrameError, match="RTN"):
        normalise_frame("RTN")
    with pytest.raises(FrameError, match="RTN"):
        rotation("RTN", "GSM", np.array([0.0]))


def test_transform_matrices_serve_cross_centre_pairs_that_rotation_refuses(recorded_3dview):
    times, matrices = frames.transform_matrices("GSE", "HEEQ", float(DAY), float(DAY + 3600), 600)
    assert times.dtype == np.dtype("datetime64[ns]") and matrices.shape == (len(times), 3, 3)
    assert recorded_3dview[0]["sampling"] == 600
    with pytest.raises(FrameError, match="GSE.*Earth.*HEEQ.*Sun"):
        rotation("GSE", "HEEQ", np.array([float(DAY)]))


def test_transform_matrices_errors_name_both_frames(monkeypatch):
    def down(path, **params):
        raise OSError("connection refused")

    monkeypatch.setattr(frames, "_fetch_json", down)
    with pytest.raises(FrameError, match="GSE.*HEEQ.*connection refused"):
        frames.transform_matrices("GSE", "HEEQ", 0.0, 1.0, 600)
