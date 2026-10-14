"""Frame conversions through 3DView rotation matrices.

https://3dview.irap.omp.eu/pages/restServices.html
"""
import functools
import json
import urllib.parse
import urllib.request
from datetime import timedelta
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp
from speasy.core.cache import CacheCall

THREEDVIEW_URL = "https://3dview.irap.omp.eu/webresources"
_SAMPLING_S = 600
# 3DView answers a week about as fast as a day (0.97 s vs 0.68 s), a month in 4 s, 90 days in 24 s (2026-10-14).
_FRAGMENT_S = 7 * 86400
_MATRICES_RETENTION = timedelta(days=7)   # ~70 kB per week of one frame pair
_FRAMES_FILE = Path(__file__).parent / "resources" / "threedview_frames.json"


class FrameError(ValueError):
    pass


def _fetch_json(path: str, **params) -> dict:
    """simplify: talks to 3DView directly; switch to speasy once speasy#406 is released."""
    url = f"{THREEDVIEW_URL}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


@functools.cache
def frame_centres() -> dict[str, str]:
    """Frame name → body it is centred on, from a bundled snapshot of 3DView's get_frames."""
    frames = json.loads(_FRAMES_FILE.read_text())["frames"]
    return {f["name"]: f["center"] for f in frames}


def normalise_frame(name: str) -> str:
    frame = name.split(">", 1)[0].strip().upper()
    if frame not in frame_centres():
        raise FrameError(f"3DView does not know the frame {name!r}")
    return frame


def _check_same_centre(from_frame: str, to_frame: str) -> None:
    # Rotation-only matrices across centres are valid for directions (a B vector GSE→HEEQ), not for positions.
    centres = frame_centres()
    unknown = [f for f in (from_frame, to_frame) if f not in centres]
    if unknown:
        raise FrameError(f"3DView does not know the frame {unknown[0]!r}")
    if centres[from_frame] != centres[to_frame]:
        raise FrameError(f"{from_frame} is centred on {centres[from_frame]} and {to_frame} on "
                         f"{centres[to_frame]}: 3DView matrices are rotations only")


def _iso(epoch_s: float) -> str:
    return str(np.datetime64(round(epoch_s * 1000), "ms"))


def _parse_matrices(values: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    times = np.array([np.datetime64(v["time"].rstrip("Z"), "ns") for v in values], dtype="datetime64[ns]")
    return times, np.array([v["matrix"] for v in values], dtype=float)


def transform_matrices(from_frame: str, to_frame: str, start: float, stop: float,
                       sampling: float) -> tuple[np.ndarray, np.ndarray]:
    """Raw 3DView rotation matrices (times datetime64[ns], matrices (n,3,3)) over [start, stop] epoch seconds."""
    try:
        data = _fetch_json("get_transform_matrices", format="json", fromframe=from_frame, toframe=to_frame,
                           start=_iso(start), stop=_iso(stop), sampling=int(sampling))
    except Exception as e:
        raise FrameError(f"could not get {from_frame} → {to_frame} matrices from 3DView: {e}") from e
    try:
        return _parse_matrices(data["values"])
    except (KeyError, TypeError, ValueError, IndexError) as e:
        raise FrameError(f"malformed {from_frame} → {to_frame} matrices from 3DView: {e!r}") from e


@CacheCall(cache_retention=_MATRICES_RETENTION, is_pure=True)
def _fragment_matrices(from_frame: str, to_frame: str, fragment: int) -> tuple[np.ndarray, np.ndarray]:
    start = fragment * _FRAGMENT_S
    return transform_matrices(from_frame, to_frame, start, start + _FRAGMENT_S, _SAMPLING_S)


@functools.lru_cache(maxsize=64)
def _fragment_rotations(from_frame: str, to_frame: str, fragment: int) -> tuple[np.ndarray, Rotation]:
    times, matrices = _fragment_matrices(from_frame, to_frame, fragment)
    return times.astype("int64") / 1e9, Rotation.from_matrix(matrices)


def _stitched(from_frame: str, to_frame: str, times: np.ndarray) -> tuple[np.ndarray, Rotation]:
    """simplify: one 3DView request per week, in sequence; each week is then kept on disk. A first
    look at a one-year span still makes 53 requests (~50 s). Upgrade path: for long spans, one
    request at a coarser sampling (multiple of 600 s)."""
    fragments = np.unique(np.floor(times / _FRAGMENT_S).astype(int))
    parts = [_fragment_rotations(from_frame, to_frame, int(f)) for f in fragments]
    stamps = np.concatenate([p[0] for p in parts])
    rots = Rotation.concatenate([p[1] for p in parts])
    stamps, first = np.unique(stamps, return_index=True)  # consecutive fragments share their boundary sample
    return stamps, rots[first]


def rotation(from_frame: str, to_frame: str, times: np.ndarray) -> Rotation:
    """Rotations taking vectors from *from_frame* to *to_frame* at *times* (epoch seconds)."""
    times = np.atleast_1d(np.asarray(times, dtype=float))
    _check_same_centre(from_frame, to_frame)
    if from_frame == to_frame or len(times) == 0:
        return Rotation.identity(len(times))
    stamps, rots = _stitched(from_frame, to_frame, times)
    return Slerp(stamps, rots)(np.clip(times, stamps[0], stamps[-1]))
