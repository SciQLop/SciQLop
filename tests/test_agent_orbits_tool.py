"""Pure logic of the ephemeris/transform tools (time helpers + rendering).

Importing anything under `SciQLop.components.agents.tools` needs a
QApplication (agents package __init__ -> chat_dock -> _builder ->
ProductsModel), so every test takes pytest-qt's `qtbot` and imports inside
the function, matching tests/test_agent_fetch_tool.py.
"""
import pytest


def test_to_epoch_accepts_iso_and_number(qtbot):
    from SciQLop.components.agents.tools.orbits import _to_epoch
    assert _to_epoch(100) == 100.0
    assert _to_epoch("1970-01-01T00:01:40+00:00") == 100.0


def test_epoch_to_3dview_formats_milliseconds(qtbot):
    from SciQLop.components.agents.tools.orbits import _epoch_to_3dview
    assert _epoch_to_3dview(1577836800.0) == "2020-01-01T00:00:00.000"


def test_iso_to_ns_strips_trailing_z(qtbot):
    import numpy as np
    from SciQLop.components.agents.tools.orbits import _iso_to_ns
    assert _iso_to_ns("2026-01-01T00:00:00.000Z") == np.datetime64("2026-01-01T00:00:00.000", "ns")


def test_check_overwrite_blocks_existing_name(qtbot):
    from SciQLop.components.agents.tools.orbits import _check_overwrite
    out = _check_overwrite("X", {"X": 123}, overwrite=False)
    assert out is not None
    assert "already bound" in out["content"][0]["text"]


def test_check_overwrite_allows_when_flag_set_or_name_free(qtbot):
    from SciQLop.components.agents.tools.orbits import _check_overwrite
    assert _check_overwrite("X", {"X": 123}, overwrite=True) is None
    assert _check_overwrite("Y", {"X": 123}, overwrite=False) is None


def test_time_range_params_includes_sampling_only_when_given(qtbot):
    from SciQLop.components.agents.tools.orbits import _time_range_params
    p = _time_range_params(1577836800.0, 1577840400.0, None)
    assert p["format"] == "json"
    assert p["start"] == "2020-01-01T00:00:00.000"
    assert p["stop"] == "2020-01-01T01:00:00.000"
    assert "sampling" not in p
    p2 = _time_range_params(1577836800.0, 1577840400.0, 600)
    assert p2["sampling"] == "600"


_BODIES_PAYLOAD = {"bodies": [
    {"id": -144, "name": "Solar Orbiter", "coverage": ["2020-02-10T04:55:49.670Z", "2030-11-20T04:42:43.611Z"], "type": "SPACECRAFT"},
    {"id": 399, "name": "Earth", "coverage": ["1900-01-01T00:00:00.000Z", "2200-01-01T00:00:00.000Z"], "type": "PLANET"},
]}
_FRAMES_PAYLOAD = {"frames": [
    {"id": 1, "name": "J2000", "desc": "Earth mean equator, dynamical equinox of J2000", "center": "Sun"},
    {"id": 1601010, "name": "HEEQ", "desc": "Heliocentric Earth Equatorial", "center": "Sun"},
]}


def test_render_bodies_and_frames_lists_both_sorted_and_described(qtbot):
    from SciQLop.components.agents.tools.orbits import render_bodies_and_frames
    text = render_bodies_and_frames(_BODIES_PAYLOAD, _FRAMES_PAYLOAD)
    assert "### bodies (2)" in text
    assert "Earth, Solar Orbiter" in text  # sorted alphabetically
    assert "### frames (2)" in text
    assert "`HEEQ` — Heliocentric Earth Equatorial" in text


def test_bodies_and_frames_impl_calls_both_endpoints_and_renders(qtbot, monkeypatch):
    """Tests `_bodies_and_frames_impl` directly (NOT the cached `bodies_and_frames`
    wrapper) by monkeypatching orbits.http.get — this sidesteps speasy's
    disk-persistent CacheCall cache entirely, so the test is not flaky across
    runs (the cached wrapper has no args to key on, so any test that exercised
    it through the real cache would read stale results from a prior run)."""
    import SciQLop.components.agents.tools.orbits as orbits

    calls = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if url.endswith("/get_bodies"):
            return _Resp(_BODIES_PAYLOAD)
        return _Resp(_FRAMES_PAYLOAD)

    monkeypatch.setattr(orbits.http, "get", fake_get)
    text = orbits._bodies_and_frames_impl()
    assert "Earth, Solar Orbiter" in text
    assert len(calls) == 2
    assert calls[0].endswith("/get_bodies") and calls[1].endswith("/get_frames")


_TRAJECTORY_PAYLOAD = {
    "bodyid": -144, "frameid": 1601010, "frame": "HEEQ",
    "kernel": {"name": "so/mk/solo_ANC_soc-pred-mk.tm", "date": "2026-07-02T01:21:26.845Z"},
    "start": "2026-01-01T00:00:00.000Z", "stop": "2026-01-01T02:00:00.000Z",
    "sampling (s)": 3600, "units": "km/s",
    "values": [
        {"time": "2026-01-01T00:00:00.000Z", "position": [1.25759608E8, 1.968625E7, 7086599.0],
         "speed": [-6.342198848724365, -4.787736892700195, -7.029590129852295]},
        {"time": "2026-01-01T01:00:00.000Z", "position": [1.25736744E8, 1.9669028E7, 7061289.5],
         "speed": [-6.359248161315918, -4.780154228210449, -7.031221866607666]},
    ],
}


def test_parse_trajectory_builds_position_and_speed_variables(qtbot):
    from SciQLop.components.agents.tools.orbits import parse_trajectory
    mapping = parse_trajectory(_TRAJECTORY_PAYLOAD)
    assert set(mapping.keys()) == {"position", "speed"}
    pos, speed = mapping["position"], mapping["speed"]
    assert pos.shape == (2, 3) and speed.shape == (2, 3)
    assert pos.unit == "km" and speed.unit == "km/s"
    assert pos.columns == ["X", "Y", "Z"] and speed.columns == ["Vx", "Vy", "Vz"]
    assert pos.meta.get("COORDINATE_SYSTEM") == "HEEQ"
    assert pos.values[0].tolist() == [1.25759608E8, 1.968625E7, 7086599.0]


class _FakeResponse:
    def __init__(self, ok, payload=None, text=""):
        self.ok = ok
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_fetch_ephemeris_binds_dict_and_summarizes(qtbot):
    from SciQLop.components.agents.tools.orbits import fetch_ephemeris
    ns = {}
    captured = {}

    def http_get(url, params):
        captured["url"], captured["params"] = url, params
        return _FakeResponse(True, _TRAJECTORY_PAYLOAD)

    out = fetch_ephemeris("Solar Orbiter", "HEEQ", 1767225600.0, 1767232800.0, 3600,
                          "orbit", ns, http_get=http_get)
    assert "position" in ns["orbit"] and "speed" in ns["orbit"]
    text = out["content"][0]["text"]
    assert "orbit" in text and "HEEQ" in text and "2 sample" in text
    assert "to_dataframe()" in text
    assert captured["url"].endswith("/get_trajectory")
    assert captured["params"]["body"] == "Solar Orbiter"
    assert captured["params"]["frame"] == "HEEQ"


def test_fetch_ephemeris_error_response_returns_text_verbatim(qtbot):
    from SciQLop.components.agents.tools.orbits import fetch_ephemeris
    ns = {}
    out = fetch_ephemeris("NOPE", None, 0.0, 1.0, None, "orbit", ns,
                          http_get=lambda url, params: _FakeResponse(False, text="Body NOPE not found"))
    assert "orbit" not in ns
    assert out["content"][0]["text"] == "Body NOPE not found"


def test_fetch_ephemeris_respects_overwrite_guard(qtbot):
    from SciQLop.components.agents.tools.orbits import fetch_ephemeris
    ns = {"orbit": 123}
    out = fetch_ephemeris("Solar Orbiter", None, 0.0, 1.0, None, "orbit", ns,
                          http_get=lambda url, params: _FakeResponse(True, _TRAJECTORY_PAYLOAD))
    assert ns["orbit"] == 123
    assert "already bound" in out["content"][0]["text"]


_TRANSFORM_PAYLOAD = {
    "fromframeId": 1600399, "fromframe": "GSE", "toframeid": 1601010, "toframe": "HEEQ",
    "start": "2026-01-01T00:00:00.000Z", "stop": "2026-01-01T02:00:00.000Z", "sampling(s)": 3600,
    "values": [
        {"time": "2026-01-01T00:00:00.000Z",
         "matrix": [[-0.998632, 0.006017, 0.051945], [-0.0, -0.993359, 0.115056], [0.052292, 0.114898, 0.992]]},
        {"time": "2026-01-01T01:00:00.000Z",
         "matrix": [[-0.998627, 0.006025, 0.052029], [-0.0, -0.993363, 0.115017], [0.052377, 0.11486, 0.992]]},
    ],
}


@pytest.fixture
def fake_3dview(monkeypatch):
    from SciQLop.components.scenes import frames
    calls = []

    def fake(path, **params):
        calls.append((path, params))
        return _TRANSFORM_PAYLOAD

    monkeypatch.setattr(frames, "_fetch_json", fake)
    return calls


def test_fetch_transform_binds_variable_and_summarizes(qtbot, fake_3dview):
    from SciQLop.components.agents.tools.orbits import fetch_transform
    ns = {}
    out = fetch_transform("GSE", "HEEQ", 1767225600.0, 1767232800.0, 3600, "R", ns)
    assert ns["R"].shape == (2, 3, 3)
    assert ns["R"].meta.get("from_frame") == "GSE" and ns["R"].meta.get("to_frame") == "HEEQ"
    assert ns["R"].values[0].tolist() == _TRANSFORM_PAYLOAD["values"][0]["matrix"]
    text = out["content"][0]["text"]
    assert "GSE" in text and "HEEQ" in text and "R" in text and "2 sample" in text
    assert "(n,3,3)" in text
    path, params = fake_3dview[0]
    assert path == "get_transform_matrices"
    assert params["fromframe"] == "GSE" and params["toframe"] == "HEEQ"
    assert params["start"] == "2026-01-01T00:00:00.000" and params["sampling"] == 3600


def test_fetch_transform_missing_frames_default_to_documented_ones(qtbot, fake_3dview):
    from SciQLop.components.agents.tools.orbits import fetch_transform
    fetch_transform(None, None, 0.0, 1.0, None, "R", {})
    params = fake_3dview[0][1]
    assert (params["fromframe"], params["toframe"], params["sampling"]) == ("J2000", "ECLIPJ2000", 3600)


def test_fetch_transform_error_is_returned_as_text(qtbot, monkeypatch):
    from SciQLop.components.agents.tools.orbits import fetch_transform
    from SciQLop.components.scenes import frames

    def refuse(path, **params):
        raise OSError("Frame id not recognized: NOPE")

    monkeypatch.setattr(frames, "_fetch_json", refuse)
    ns = {}
    out = fetch_transform("GSE", "NOPE", 0.0, 1.0, None, "R", ns)
    assert "R" not in ns
    assert "GSE" in out["content"][0]["text"] and "Frame id not recognized: NOPE" in out["content"][0]["text"]


def test_fetch_transform_respects_overwrite_guard(qtbot, fake_3dview):
    from SciQLop.components.agents.tools.orbits import fetch_transform
    ns = {"R": 123}
    out = fetch_transform(None, None, 0.0, 1.0, None, "R", ns)
    assert ns["R"] == 123 and not fake_3dview
    assert "already bound" in out["content"][0]["text"]
