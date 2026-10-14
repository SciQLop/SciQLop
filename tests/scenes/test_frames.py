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
    return calls


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
    with pytest.raises(FrameError, match="GSE.*GSM.*connection refused"):
        rotation("GSE", "GSM", np.array([float(DAY)]))


@pytest.mark.parametrize("raw, frame", [("GSE>Geocentric Solar Ecliptic", "GSE"), (" gsm ", "GSM"), ("MESO", "MESO")])
def test_frame_names_from_metadata_are_normalised(raw, frame):
    assert normalise_frame(raw) == frame


def test_unknown_frame_is_refused():
    with pytest.raises(FrameError, match="RTN"):
        normalise_frame("RTN")
    with pytest.raises(FrameError, match="RTN"):
        rotation("RTN", "GSM", np.array([0.0]))
