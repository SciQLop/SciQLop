"""Ephemeris and coordinate-transform lookups via the CDPP 3DView REST API.

Pure logic: the HTTP GET is injected so this module is unit-tested offline.
`_builder.py` wires the real `speasy.core.http.get` client for ephemeris;
transform matrices come from `scenes.frames`, the single 3DView matrix client.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import numpy as np
import pandas as pd

from speasy.core import http
from speasy.core.cache import CacheCall
from speasy.core.data_containers import DataContainer, VariableTimeAxis
from speasy.products.variable import SpeasyVariable

from SciQLop.components.scenes import frames

from .fetch import _var_line

BASE_URL = "https://3dview.irap.omp.eu/webresources"
DEFAULT_FROM_FRAME, DEFAULT_TO_FRAME, DEFAULT_SAMPLING_S = "J2000", "ECLIPJ2000", 3600
_BODIES_AND_FRAMES_RETENTION = 7 * 24 * 3600  # 1 week — body/frame lists change rarely


def _to_epoch(x) -> float:
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    return pd.Timestamp(str(x)).timestamp()


def _epoch_to_3dview(t: float) -> str:
    return pd.Timestamp(t, unit="s", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def _iso_to_ns(t: str) -> np.datetime64:
    return np.datetime64(t[:-1] if t.endswith("Z") else t, "ns")


def _check_overwrite(name: str, shell_ns: Dict[str, Any], overwrite: bool) -> Optional[Dict[str, Any]]:
    if not overwrite and name in shell_ns:
        existing = type(shell_ns[name]).__name__
        return {"content": [{"type": "text",
                "text": f"name `{name}` already bound (type {existing}); pass overwrite=True"}]}
    return None


def _time_range_params(start, stop, sampling) -> Dict[str, str]:
    params = {"format": "json",
              "start": _epoch_to_3dview(_to_epoch(start)),
              "stop": _epoch_to_3dview(_to_epoch(stop))}
    if sampling:
        params["sampling"] = str(int(sampling))
    return params


def render_bodies_and_frames(bodies_payload: Dict[str, Any], frames_payload: Dict[str, Any]) -> str:
    bodies = sorted(b["name"] for b in bodies_payload.get("bodies", []))
    frames = frames_payload.get("frames", [])
    lines = [f"### bodies ({len(bodies)})", ", ".join(bodies), "",
             f"### frames ({len(frames)})"]
    lines += [f"- `{f['name']}` — {f.get('desc', '')}" for f in frames]
    return "\n".join(lines)


def _bodies_and_frames_impl() -> str:
    bodies = http.get(f"{BASE_URL}/get_bodies", params={"format": "json"}).json()
    frames = http.get(f"{BASE_URL}/get_frames", params={"format": "json"}).json()
    return render_bodies_and_frames(bodies, frames)


bodies_and_frames = CacheCall(cache_retention=_BODIES_AND_FRAMES_RETENTION, is_pure=True)(_bodies_and_frames_impl)


def parse_trajectory(payload: Dict[str, Any]) -> Dict[str, SpeasyVariable]:
    frame = payload.get("frame", "")
    samples = payload["values"]
    times = np.array([_iso_to_ns(s["time"]) for s in samples])
    position = np.array([s["position"] for s in samples], dtype=float)
    speed = np.array([s["speed"] for s in samples], dtype=float)
    return {
        "position": SpeasyVariable(
            axes=[VariableTimeAxis(values=times)],
            values=DataContainer(position, meta={"UNITS": "km", "COORDINATE_SYSTEM": frame}, name="position"),
            columns=["X", "Y", "Z"],
        ),
        "speed": SpeasyVariable(
            axes=[VariableTimeAxis(values=times.copy())],
            values=DataContainer(speed, meta={"UNITS": "km/s", "COORDINATE_SYSTEM": frame}, name="speed"),
            columns=["Vx", "Vy", "Vz"],
        ),
    }


def fetch_ephemeris(body: str, frame: Optional[str], start, stop, sampling, name: str,
                    shell_ns: Dict[str, Any], *, overwrite: bool = False,
                    http_get: Callable) -> Dict[str, Any]:
    blocked = _check_overwrite(name, shell_ns, overwrite)
    if blocked:
        return blocked
    params = _time_range_params(start, stop, sampling)
    params["body"] = body
    if frame:
        params["frame"] = frame
    resp = http_get(f"{BASE_URL}/get_trajectory", params=params)
    if not resp.ok:
        return {"content": [{"type": "text", "text": resp.text}]}
    mapping = parse_trajectory(resp.json())
    shell_ns[name] = mapping
    n = mapping["position"].shape[0]
    resolved_frame = mapping["position"].meta.get("COORDINATE_SYSTEM", "")
    lines = [f"fetched ephemeris for `{body}` into `{name}` — {n} sample(s), frame {resolved_frame}"]
    for short, var in mapping.items():
        lines.append(_var_line(short, var))
    lines.append(f"\nbridges: `{name}['position'].to_dataframe()`, `{name}['speed'].values`, `.time`")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


def _matrix_variable(times: np.ndarray, matrices: np.ndarray, from_frame: str, to_frame: str) -> SpeasyVariable:
    meta = {"from_frame": from_frame, "to_frame": to_frame}
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=times)],
        values=DataContainer(matrices, meta=meta, name="matrix"),
    )


def fetch_transform(from_frame: Optional[str], to_frame: Optional[str], start, stop, sampling,
                    name: str, shell_ns: Dict[str, Any], *, overwrite: bool = False,
                    http_get: Optional[Callable] = None) -> Dict[str, Any]:
    """`http_get` is accepted for backward compatibility and ignored: `frames` owns the 3DView request."""
    blocked = _check_overwrite(name, shell_ns, overwrite)
    if blocked:
        return blocked
    from_frame, to_frame = from_frame or DEFAULT_FROM_FRAME, to_frame or DEFAULT_TO_FRAME
    try:
        times, matrices = frames.transform_matrices(from_frame, to_frame, _to_epoch(start), _to_epoch(stop),
                                                    sampling or DEFAULT_SAMPLING_S)
    except frames.FrameError as e:
        return {"content": [{"type": "text", "text": str(e)}]}
    var = _matrix_variable(times, matrices, from_frame, to_frame)
    shell_ns[name] = var
    text = (f"fetched transform `{from_frame}`→`{to_frame}` into `{name}` "
            f"— {var.shape[0]} sample(s)\n{_var_line('matrix', var)}"
            f"\n\nbridges: `{name}.values` (shape (n,3,3)), `{name}.time`")
    return {"content": [{"type": "text", "text": text}]}
