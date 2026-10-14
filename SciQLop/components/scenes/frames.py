"""Frame conversions through 3DView rotation matrices.

https://3dview.irap.omp.eu/pages/restServices.html
"""
import functools
import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

THREEDVIEW_URL = "https://3dview.irap.omp.eu/webresources"
_SAMPLING_S = 600
_DAY_S = 86400
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
    centres = frame_centres()
    unknown = [f for f in (from_frame, to_frame) if f not in centres]
    if unknown:
        raise FrameError(f"3DView does not know the frame {unknown[0]!r}")
    if centres[from_frame] != centres[to_frame]:
        raise FrameError(f"{from_frame} is centred on {centres[from_frame]} and {to_frame} on "
                         f"{centres[to_frame]}: 3DView matrices are rotations only")


def _iso(epoch_s: int) -> str:
    return str(np.datetime64(int(epoch_s), "s")) + ".000"


@functools.lru_cache(maxsize=128)
def _day_rotations(from_frame: str, to_frame: str, day: int) -> tuple[np.ndarray, Rotation]:
    start = day * _DAY_S
    try:
        data = _fetch_json("get_transform_matrices", format="json", fromframe=from_frame, toframe=to_frame,
                           start=_iso(start), stop=_iso(start + _DAY_S), sampling=_SAMPLING_S)
    except Exception as e:
        raise FrameError(f"could not get {from_frame} → {to_frame} matrices from 3DView: {e}") from e
    try:
        return _parse_matrices(data["values"])
    except (KeyError, TypeError, ValueError, IndexError) as e:
        raise FrameError(f"malformed {from_frame} → {to_frame} matrices from 3DView: {e!r}") from e


def _parse_matrices(values: list[dict]) -> tuple[np.ndarray, Rotation]:
    times = np.array([np.datetime64(v["time"].rstrip("Z"), "ns") for v in values]).astype("int64") / 1e9
    return times, Rotation.from_matrix(np.array([v["matrix"] for v in values], dtype=float))


def _stitched(from_frame: str, to_frame: str, times: np.ndarray) -> tuple[np.ndarray, Rotation]:
    """simplify: one 3DView request per day, in sequence, with a 128-day cache. A one-year view
    makes hundreds of requests per pane and the next range change refetches them. Upgrade path:
    above a few days, one request for the whole span at a coarser sampling (multiple of 600 s)."""
    days = np.unique(np.floor(times / _DAY_S).astype(int))
    parts = [_day_rotations(from_frame, to_frame, int(d)) for d in days]
    stamps = np.concatenate([p[0] for p in parts])
    rots = Rotation.concatenate([p[1] for p in parts])
    stamps, first = np.unique(stamps, return_index=True)  # consecutive days share their midnight sample
    return stamps, rots[first]


def rotation(from_frame: str, to_frame: str, times: np.ndarray) -> Rotation:
    """Rotations taking vectors from *from_frame* to *to_frame* at *times* (epoch seconds)."""
    times = np.atleast_1d(np.asarray(times, dtype=float))
    _check_same_centre(from_frame, to_frame)
    if from_frame == to_frame or len(times) == 0:
        return Rotation.identity(len(times))
    stamps, rots = _stitched(from_frame, to_frame, times)
    return Slerp(stamps, rots)(np.clip(times, stamps[0], stamps[-1]))
