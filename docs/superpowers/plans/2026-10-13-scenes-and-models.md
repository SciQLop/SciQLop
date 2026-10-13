# Scenes and Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `panel.plot_scene("Earth environment")` + `add_trajectory("MMS1")` draw a planet, its boundaries (summarised over the panel's time range) and spacecraft orbits in one consistent frame and unit; plugins register bodies, boundary models and scenes.

**Architecture:** Pure numpy logic in `SciQLop/components/scenes/` (frames via 3DView rotation matrices, radial boundaries, per-angle summary, registries); a thin `SciQLop/user_api/scenes/` surface; per-pane SciQLopPlots callable curves driven by the projection's time axis (they run off the GUI thread); built-in content in a `planetary_scenes` plugin.

**Tech Stack:** numpy, scipy (`Rotation`, `Slerp`), astropy.units (via speasy), speasy (`cdpp3dview` trajectories, product fetches), SciQLopPlots projection plots, pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-13-scenes-and-models-design.md`

## Global Constraints

- Everything declares its frame and unit; nothing is mixed silently. Frame conversions only between frames centred on the same body; never fall back to identity.
- No test touches the network: 3DView and speasy responses are recorded or monkeypatched.
- Nothing blocks the GUI thread: boundary and trajectory computations run inside SciQLopPlots callable graphs.
- Failures show on the plot's error overlay (`_CallbackErrorOverlay`), never raise inside a Qt slot.
- `user_api/` is published: new public functions there are `@on_main_thread` or listed in `NOT_MARSHALED_ON_PURPOSE` (`tests/test_user_api_thread_classification.py`).
- Always `uv run pytest`; one test run at a time; never `uv sync`; never rebuild SciQLopPlots.
- Commit on `main` with explicit pathspecs (untracked repo-root files `importlib.metadata`, `setWidget`, `pydata/` are not ours).
- Shell heredocs hang in this environment: write files with the Write/Edit tools, never `cat <<EOF`.
- Code style: small functions, data over code, comments only for non-obvious "why", `simplify:` notes on deliberate shortcuts.

## Facts established while planning (2026-10-13)

- 3DView GSE→GSM matrices agree with MMS MEC's own GSE/GSM positions to < 0.02° on 2015-10-16 (median 0.0099°), despite 3DView's "GSM definition not valid after 31/12/2014" note. Usable.
- 3DView frame `MSO` is centred on Mars, `MESO` on Mercury. 3DView body names: `Earth`, `Mars`, `Mercury`, `MMS1`.
- `speasy.get_data("cdpp3dview/MMS1", start, stop, coordinate_frame="GSM", sampling="600")` returns km, columns `x, y, z`, no `COORDINATE_SYSTEM` key (the frame is the one requested).
- SciQLop products-tree speasy nodes carry `metadata()["speasy_id"]` (e.g. `cda/MMS1_FGM_SRVY_L2/mms1_fgm_b_gse_srvy_l2`).
- A projection subplot is a `SciQLopPlot`. `subplot.plot(f, graph_type=GraphType.ParametricCurve, labels=[...])` returns a `SciQLopCurveFunction`; after `graph.observe(proj.time_axis())`, `f(start, stop)` is called on a worker thread with the panel time range, and `(x, y)` returned arrays are drawn.
- **`SciQLopMultiPlotPanel.create_plot(-1, PlotType.Projections)` segfaults** (SciQLopPlots 0.51.3: its switch has no Projections case, `add_plot(nullptr)`). Reported to the SciQLopPlots session. Workaround verified: create the projection by plotting a one-sample seed `[t, x, y, z]` with `plot_type=PlotType.Projections, graph_type=GraphType.ParametricCurve`, then `proj.remove_plottable(seed)`; the 3 panes stay.
- Reference values (Dp = 2 nPa, Bz = 0): Shue 1998 r(0°) = 10.251873, r(90°) = 15.427840 R_E (matches LPP `space`); Jelinek 2012 bow shock r(0°) = 13.511736, r(90°) = 23.096985 R_E; Vignes 2000 BS subsolar x = 1.644926 R_M, MPB subsolar x = 1.285263 R_M; Winslow 2013 MP r(0°) = 1.45, r(90°) = 2.050610 R_M, BS subsolar x = 1.848039 R_M.

## Deviations from the spec (decided while planning)

- **Frame catalogue is bundled data**, not fetched: `components/scenes/resources/threedview_frames.json` (snapshot of `get_frames`). Validation needs no network, so `plot_scene` never blocks. Only rotation matrices are fetched (in worker threads).
- **No frame alias table**: normalisation keeps the part before `>`, upper-cases, and checks the bundled catalogue. Add aliases when a real product needs one.
- **Trajectories go through speasy** (`cdpp3dview` provider, cached) instead of a SciQLop 3DView trajectory client.
- **`cross_section` always uses bisection** along in-plane rays (no separate fast path): one code path, exact to ~1e-12 body radii after 60 halvings.
- **Non-radial boundaries' "all sections, faint" mode is skipped**: no built-in model needs it. A non-radial `Boundary` is accepted, but its sections are summarised per angle like a radial one, which is only right if they are star-shaped around the focus. → skipped: add when a non-radial model is registered.
- **Task 0 added**: a pre-existing bug in projection plots found while planning (see Task 0).
- **Plan review (opencode, 2026-10-13)** fixed: overlay getter `text()`, `GuardedImpl` has no `__init__`, `remove_plot` takes an index, drop targets can be panes, undefined drop-error helper, `Boundary` protocol exported, unknown frames raise `FrameError` everywhere, non-position products refused, Mars label and mixed-frame tests. Its "seed workaround segfaults" claim did not reproduce (offscreen and Xvfb, bare and `TimeSyncPanel`); what did reproduce became Task 0.

## Review Focus

1. A scene plot whose time range covers a 3DView outage → every boundary curve shows an overlay error, the plot and the trajectory stay usable, nothing raises. (Task 6 test `test_boundary_error_shows_on_overlay`.)
2. A position product in a frame 3DView doesn't know (`RTN`) or without `COORDINATE_SYSTEM` dropped on a scene plot → refused with a message naming the frame, not plotted raw. (Task 7 tests.)
3. An interval crossing midnight → rotations from both days are stitched without a duplicate-time Slerp error. (Task 1 test `test_rotation_spans_two_days`.)
4. A model whose section is open (tail) → no fake closing line across the tail. (Task 3 test `test_open_tail_leaves_a_gap`.)
5. Closing a scene plot while a boundary fetch is in flight → no crash (reporter is parented to the subplot; `_PlotErrorReporter.report` already checks `shiboken6.isValid`). (Task 6 test `test_closing_scene_plot_mid_fetch`.)

---

### Task 0: Projection plots no longer get y-axis defaults they don't have

Found while planning (2026-10-13). Every projection plot added to a `TimeSyncPanel` prints
`Abstract method called: virtual SciQLopPlotAxisInterface* SciQLopPlotInterface::y_axis() const from concrete class: SciQLopNDProjectionPlot`
(and `y2_axis`): `apply_defaults_to_plot` (`SciQLop/components/plotting/backend/autoscale_percentile.py:59`, a `plot_added`
hook) treats every plot as having axes. A projection plot has none of its own; its three panes do. Calling an abstract
C++ method returns null and can crash depending on what follows.

**Files:**
- Modify: `SciQLop/components/plotting/backend/autoscale_percentile.py:59-71`
- Test: the existing autoscale-percentile test file (`grep -rln "apply_defaults_to_plot" tests`), or `tests/test_autoscale_percentile_projection.py` if none fits

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from SciQLopPlots import GraphType, PlotType

from .fixtures import *  # noqa: F401, F403


def test_projection_plots_get_defaults_on_their_panes(plot_panel, capfd):
    z = np.zeros(1)
    proj, _ = plot_panel._get_impl_or_raise().plot([z, z, z, z], plot_type=PlotType.Projections,
                                                   graph_type=GraphType.ParametricCurve, labels=["", "", ""])
    assert "Abstract method called" not in capfd.readouterr().err
    assert all(hasattr(proj.subplot(i), "_sciqlop_percentile_snapshot") for i in range(proj.subplot_count()))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest <that file>::test_projection_plots_get_defaults_on_their_panes -v`
Expected: FAIL on the "Abstract method called" assert. If the message goes to the C++ stderr and `capfd` doesn't see it, keep only the second assert (it fails too: the snapshot is set on the projection, not its panes).

- [ ] **Step 3: Fix the shared hook**

```python
def _axis_plots(plot) -> list:
    """A projection plot has no axes of its own; its panes do."""
    if hasattr(plot, "subplot_count"):
        return [plot.subplot(i) for i in range(plot.subplot_count())]
    return [plot]


def apply_defaults_to_plot(plot) -> None:
    """..."""  # keep the existing docstring
    for p in _axis_plots(plot):
        _apply_defaults(p)
```

Move the current body of `apply_defaults_to_plot` into `_apply_defaults(plot)` unchanged. Grep every other `plot_added` hook in `time_sync_panel.py` (`_route_canvas_context_menus`, `_apply_theme_to_plot`) for `x_axis()`/`y_axis()` calls on the added plot; if any warns the same way, route it through `_axis_plots` too.

- [ ] **Step 4: Run it, plus the autoscale tests**

Run: `uv run pytest -k "autoscale or percentile or projection" -v` → all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "fix(plotting): projection plots get axis defaults on their panes" -- \
  SciQLop/components/plotting/backend/autoscale_percentile.py <test file>
```

---

## File structure

```
SciQLop/components/scenes/
    __init__.py            # empty
    frames.py              # FrameError, frame_centres, normalise_frame, rotation (3DView matrices, day cache)
    boundary.py            # Plane, RadialBoundary (sample_times, cross_section by bisection)
    summary.py             # PANES, pane_basis, SectionSummary, summarise, pane_summary
    model.py               # Body, Scene, ResolvedScene, resolve
    registry.py            # Registry[T], NotRegistered, BODIES, BOUNDARIES, SCENES
    scene_plot.py          # create_scene_plot, add_boundary, trajectory_source, add_trajectory
    tree.py                # products-tree nodes for scenes/models + drop dispatch handlers
    resources/threedview_frames.json
SciQLop/user_api/scenes/__init__.py   # public surface + ScenePlot wrapper + register_* (@on_main_thread)
SciQLop/user_api/plot/_panel.py       # PlotPanel.plot_scene
SciQLop/components/plotting/ui/time_sync_panel.py  # ProductDnDCallback → (kind, target) dispatch
SciQLop/user_api/layers/_provider.py  # sciqlop_kind = "layer" replaces LAYER_META_KEY
SciQLop/plugins/planetary_scenes/
    __init__.py            # load(main_window): registers bodies, models, scenes
    plugin.json
    models.py              # Shue1998, Jelinek2012BowShock, Vignes2000BowShock, Vignes2000MPB, Winslow2013Magnetopause, Winslow2013BowShock
tests/scenes/
    __init__.py
    data/gse_gsm_20151016.json, data/gse_gsm_20151017.json   # recorded 3DView matrices
    test_frames.py test_boundary.py test_summary.py test_registry.py test_planetary_models.py
    test_scene_plot.py test_trajectory.py test_scene_tree.py
```

---

### Task 1: Frames — catalogue, normalisation, rotations

**Files:**
- Create: `SciQLop/components/scenes/__init__.py` (empty), `SciQLop/components/scenes/frames.py`, `SciQLop/components/scenes/resources/threedview_frames.json`
- Create: `tests/scenes/__init__.py` (empty), `tests/scenes/data/gse_gsm_20151016.json`, `tests/scenes/data/gse_gsm_20151017.json`, `tests/scenes/test_frames.py`
- Modify: `pyproject.toml` only if `SciQLop/components/**/resources/*.json` is not already package data (check `[tool.setuptools.package-data]` or equivalent; mirror how other component resources are included).

**Interfaces:**
- Produces: `FrameError(ValueError)`; `frame_centres() -> dict[str, str]`; `normalise_frame(name: str) -> str`; `rotation(from_frame: str, to_frame: str, times: np.ndarray) -> scipy.spatial.transform.Rotation` (times = float epoch seconds, result has `len(times)` rotations); `_fetch_json(path: str, **params) -> dict` (the only network call; tests monkeypatch it).

- [ ] **Step 1: Record the data files**

Write a throwaway script in the scratchpad (not in the repo) that saves:
- `https://3dview.irap.omp.eu/webresources/get_frames` (header `Accept: application/json`) → `SciQLop/components/scenes/resources/threedview_frames.json`, pretty-printed.
- `get_transform_matrices?format=json&fromframe=GSE&toframe=GSM&sampling=600&start=2015-10-16T00:00:00.000&stop=2015-10-17T00:00:00.000` → `tests/scenes/data/gse_gsm_20151016.json`; same for 2015-10-17 → `..._20151017.json`.

Check: the frames file has 106 entries and `GSM` has `"center": "Earth"`.

- [ ] **Step 2: Write the failing tests** — `tests/scenes/test_frames.py`

```python
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
```

The `tilt` expectation: compute it from the recorded file in Step 1 (angle of the YZ rotation at 00:00 and 01:00) and paste the two values, rounded to 2 decimals. The live values on 2026-10-13 were ≈ 12.65° and 13.81°.

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/scenes/test_frames.py -v`
Expected: FAIL, `ModuleNotFoundError: SciQLop.components.scenes.frames`.

- [ ] **Step 4: Implement** — `SciQLop/components/scenes/frames.py`

```python
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
    values = data["values"]
    times = np.array([np.datetime64(v["time"].rstrip("Z"), "ns") for v in values]).astype("int64") / 1e9
    return times, Rotation.from_matrix(np.array([v["matrix"] for v in values], dtype=float))


def _stitched(from_frame: str, to_frame: str, times: np.ndarray) -> tuple[np.ndarray, Rotation]:
    days = np.unique(np.floor(times / _DAY_S).astype(int))
    parts = [_day_rotations(from_frame, to_frame, int(d)) for d in days]
    stamps = np.concatenate([p[0] for p in parts])
    rots = Rotation.concatenate([p[1] for p in parts])
    stamps, first = np.unique(stamps, return_index=True)  # consecutive days share their midnight sample
    return stamps, rots[first]


def rotation(from_frame: str, to_frame: str, times: np.ndarray) -> Rotation:
    """Rotations taking vectors from *from_frame* to *to_frame* at *times* (epoch seconds)."""
    times = np.asarray(times, dtype=float)
    if from_frame == to_frame:
        return Rotation.identity(len(times))
    _check_same_centre(from_frame, to_frame)
    stamps, rots = _stitched(from_frame, to_frame, times)
    return Slerp(stamps, rots)(np.clip(times, stamps[0], stamps[-1]))
```

Note: `rotation` validates centres with the bundled catalogue, so `test_frames_centred_on_different_bodies_are_refused` makes no network call.

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest tests/scenes/test_frames.py -v`
Expected: 10 passed.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/scenes/__init__.py SciQLop/components/scenes/frames.py \
  SciQLop/components/scenes/resources/threedview_frames.json tests/scenes/__init__.py \
  tests/scenes/data/gse_gsm_20151016.json tests/scenes/data/gse_gsm_20151017.json tests/scenes/test_frames.py
git commit -m "feat(scenes): frame rotations from 3DView matrices" -- <same paths>
```

---

### Task 2: Radial boundaries — planes and cross sections

**Files:**
- Create: `SciQLop/components/scenes/boundary.py`, `tests/scenes/test_boundary.py`

**Interfaces:**
- Produces:
  - `Plane(normal: np.ndarray (n,3), offset: np.ndarray (n,))`, frozen dataclass.
  - `Boundary(Protocol)`: the attributes below plus `sample_times` and `cross_section`; the type scenes accept.
  - `class RadialBoundary` with class attributes `name, body, kind, frame, label, description, reference: str`, `focus: tuple[float, float, float] = (0, 0, 0)`, `theta_max: float = np.deg2rad(150)`, `cadence: Optional[float] = None`, `n_samples: int = 200`, `n_rays: int = 720`; abstract `radius(theta, phi, times) -> np.ndarray` (theta, phi shape (n, m); times (n,); returns (n, m)); `sample_times(start, stop) -> np.ndarray`; `cross_section(planes: Plane, times) -> np.ndarray (n, n_rays, 3)` in model frame, body radii, NaN where no crossing.

- [ ] **Step 1: Write the failing tests** — `tests/scenes/test_boundary.py`

```python
import numpy as np
import pytest

from SciQLop.components.scenes.boundary import Plane, RadialBoundary


class Sphere(RadialBoundary):
    name, body, kind, frame = "sphere", "earth", "test", "GSM"

    def radius(self, theta, phi, times):
        return np.full(np.shape(theta), 3.0)


class Conic(RadialBoundary):
    """r = L / (1 + e cos θ) from a focus on +X: an ellipse, closed on every ray."""
    name, body, kind, frame = "conic", "mars", "test", "MSO"
    focus = (0.6, 0.0, 0.0)
    theta_max = np.pi

    def radius(self, theta, phi, times):
        return 2.0 / (1 + 0.5 * np.cos(theta))


class Paraboloid(RadialBoundary):
    """Shue-like, open tail."""
    name, body, kind, frame = "open", "earth", "test", "GSM"

    def radius(self, theta, phi, times):
        return 10.0 * (2 / (1 + np.cos(theta))) ** 0.5


def planes(normal, n=1, offset=0.0):
    return Plane(normal=np.tile(normal, (n, 1)).astype(float), offset=np.full(n, offset))


@pytest.mark.parametrize("normal", [(0, 0, 1), (1, 0, 0), (0, 1, 0)])
def test_a_sphere_cuts_as_a_circle_in_every_pane(normal):
    s = Sphere().cross_section(planes(normal), np.array([0.0]))
    assert s.shape == (1, 720, 3)
    assert np.allclose(np.linalg.norm(s[0], axis=1), 3.0)
    assert np.allclose(s[0] @ np.array(normal, float), 0.0)


def test_a_conic_section_through_its_focus_matches_the_formula():
    s = Conic().cross_section(planes((0, 0, 1)), np.array([0.0]))[0]
    rel = s - np.array(Conic.focus)
    theta = np.arccos(rel[:, 0] / np.linalg.norm(rel, axis=1))
    assert np.allclose(np.linalg.norm(rel, axis=1), 2.0 / (1 + 0.5 * np.cos(theta)))


def test_a_pane_missing_the_focus_still_gets_the_true_boundary():
    s = Conic().cross_section(planes((1, 0, 0)), np.array([0.0]))[0]   # x = 0, focus at x = 0.6
    assert np.all(np.isfinite(s)) and np.allclose(s[:, 0], 0.0)
    rel = s - np.array(Conic.focus)
    theta = np.arccos(rel[:, 0] / np.linalg.norm(rel, axis=1))
    assert np.allclose(np.linalg.norm(rel, axis=1), 2.0 / (1 + 0.5 * np.cos(theta)), atol=1e-9)


def test_each_time_gets_its_own_plane():
    p = Plane(normal=np.array([[0, 0, 1.0], [1.0, 0, 0]]), offset=np.zeros(2))
    s = Sphere().cross_section(p, np.array([0.0, 1.0]))
    assert np.allclose(s[0, :, 2], 0) and np.allclose(s[1, :, 0], 0)


def test_rays_past_theta_max_are_nan():
    s = Paraboloid().cross_section(planes((0, 0, 1)), np.array([0.0]))[0]
    finite = np.isfinite(s[:, 0])
    assert finite.any() and not finite.all()
    theta = np.arccos(s[finite, 0] / np.linalg.norm(s[finite], axis=1))
    assert np.all(theta <= Paraboloid.theta_max)


def test_sample_times_follow_cadence_or_count():
    assert len(Sphere().sample_times(0.0, 100.0)) == 200
    cadenced = type("C", (Sphere,), {"cadence": 10.0})()
    assert np.allclose(cadenced.sample_times(0.0, 100.0), np.arange(0.0, 101.0, 10.0))
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/scenes/test_boundary.py -v`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `SciQLop/components/scenes/boundary.py`

```python
"""Boundaries star-shaped around a focus: r = r(θ, φ, t)."""
from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np

_BISECTIONS = 60
_FAR = 1e3  # body radii; a ray still inside the boundary this far out has no crossing


@dataclass(frozen=True)
class Plane:
    normal: np.ndarray   # (n, 3) unit normals, one per time
    offset: np.ndarray   # (n,) signed distance from the origin


class Boundary(Protocol):
    """What a scene needs from a boundary model. RadialBoundary implements it; a
    non-radial model implements sample_times and cross_section itself."""
    name: str
    body: str
    kind: str
    frame: str
    label: str
    description: str
    reference: str
    focus: tuple[float, float, float]

    def sample_times(self, start: float, stop: float) -> np.ndarray: ...

    def cross_section(self, planes: Plane, times: np.ndarray) -> np.ndarray: ...


def _in_plane_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    helper = np.where(np.abs(normal[:, :1]) < 0.9, [[1.0, 0, 0]], [[0, 1.0, 0]])
    u = np.cross(normal, helper)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    return u, np.cross(normal, u)


def _spherical(rel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r = np.linalg.norm(rel, axis=-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        theta = np.arccos(np.clip(rel[..., 0] / r, -1, 1))
    return r, theta, np.arctan2(rel[..., 2], rel[..., 1])


class RadialBoundary:
    name: str
    body: str
    kind: str
    frame: str
    label: str = ""
    description: str = ""
    reference: str = ""
    focus: tuple[float, float, float] = (0.0, 0.0, 0.0)
    theta_max: float = np.deg2rad(150)
    cadence: Optional[float] = None
    n_samples: int = 200
    n_rays: int = 720

    def radius(self, theta: np.ndarray, phi: np.ndarray, times: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def sample_times(self, start: float, stop: float) -> np.ndarray:
        if self.cadence:
            return np.arange(start, stop + self.cadence / 2, self.cadence)
        return np.linspace(start, stop, self.n_samples)

    def _outside(self, points: np.ndarray, times: np.ndarray) -> np.ndarray:
        r, theta, phi = _spherical(points - np.asarray(self.focus))
        with np.errstate(invalid="ignore"):
            return (theta > self.theta_max) | (r > self.radius(theta, phi, times))

    def cross_section(self, planes: Plane, times: np.ndarray) -> np.ndarray:
        """Bisection along rays from the focus projected onto each plane."""
        focus = np.asarray(self.focus, dtype=float)
        n = planes.normal
        centre = focus - ((n @ focus) - planes.offset)[:, None] * n           # (n, 3)
        u, v = _in_plane_basis(n)
        a = np.linspace(-np.pi, np.pi, self.n_rays, endpoint=False)
        rays = np.cos(a)[None, :, None] * u[:, None] + np.sin(a)[None, :, None] * v[:, None]   # (n, m, 3)
        point = lambda s: centre[:, None] + s[..., None] * rays
        lo, hi = np.zeros(rays.shape[:2]), np.full(rays.shape[:2], _FAR)
        for _ in range(_BISECTIONS):
            mid = (lo + hi) / 2
            out = self._outside(point(mid), times)
            hi, lo = np.where(out, mid, hi), np.where(out, lo, mid)
        crossing = point(hi)
        valid = ~self._outside(point(lo), times) & (hi < _FAR * 0.999)
        _, theta, _ = _spherical(crossing - focus)
        valid &= theta < self.theta_max - 1e-6
        return np.where(valid[..., None], crossing, np.nan)
```

`times` passed to `radius` must broadcast against (n, m): models use `times[:, None]` when they depend on time.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/scenes/test_boundary.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(scenes): radial boundaries cut by any plane" -- SciQLop/components/scenes/boundary.py tests/scenes/test_boundary.py
```

(`git add` the two new files first.)

---

### Task 3: Interval summary per pane

**Files:**
- Create: `SciQLop/components/scenes/summary.py`, `tests/scenes/test_summary.py`

**Interfaces:**
- Consumes: `Plane`, `RadialBoundary.sample_times/cross_section/focus/frame` (Task 2); `rotation` (Task 1).
- Produces:
  - `PANES: tuple[tuple[int, int], ...] = ((0, 1), (1, 2), (2, 0))` — (e1 axis, e2 axis) per pane, XY, YZ, ZX; the normal is the remaining axis.
  - `pane_basis(pane: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]` (e1, e2, normal).
  - `SectionSummary(angles, centre, low, high, origin)` frozen dataclass; `.curve(which: Literal["centre", "low", "high"]) -> tuple[np.ndarray, np.ndarray]` pane coordinates.
  - `summarise(sections: np.ndarray (n,m,3) scene frame, pane: int, origin: np.ndarray (3,), how: Literal["median","mean"]) -> SectionSummary`.
  - `pane_summary(model, scene_frame: str, pane: int, start: float, stop: float, how: str) -> SectionSummary`.

- [ ] **Step 1: Write the failing tests** — `tests/scenes/test_summary.py`

```python
import numpy as np
import pytest

from SciQLop.components.scenes import summary
from SciQLop.components.scenes.boundary import RadialBoundary
from SciQLop.components.scenes.summary import pane_basis, pane_summary, summarise


def circle(radius, n=360, phase=0.0, z=0.0):
    a = np.linspace(-np.pi, np.pi, n, endpoint=False) + phase
    return np.stack([radius * np.cos(a), radius * np.sin(a), np.full(n, z)], axis=1)


def test_pane_bases():
    e1, e2, n = pane_basis(1)
    assert np.allclose(e1, [0, 1, 0]) and np.allclose(e2, [0, 0, 1]) and np.allclose(n, [1, 0, 0])


def test_sections_sampled_at_different_angles_are_reduced_per_angle():
    sections = np.stack([circle(2.0, 360), circle(4.0, 500, phase=0.003)])
    s = summarise(sections, pane=0, origin=np.zeros(3), how="median")
    assert np.allclose(s.centre, 3.0, atol=1e-6)
    assert np.allclose(s.low, 2.0, atol=1e-6) and np.allclose(s.high, 4.0, atol=1e-6)


def test_mean_and_nan_are_handled():
    third = np.full((360, 3), np.nan)
    sections = np.stack([circle(2.0), circle(5.0), third])
    s = summarise(sections, pane=0, origin=np.zeros(3), how="mean")
    assert np.allclose(s.centre, 3.5, atol=1e-6)


def test_an_asymmetric_section_keeps_its_orientation():
    shifted = circle(2.0) + [0.5, 0, 0]          # still contains the origin, so star-shaped around it
    s = summarise(shifted[None], pane=0, origin=np.zeros(3), how="median")
    x, y = s.curve("centre")
    assert np.nanmax(x) == pytest.approx(2.5, abs=1e-3) and np.nanmin(x) == pytest.approx(-1.5, abs=1e-3)


def test_open_tail_leaves_a_gap():
    c = circle(3.0)
    c[np.abs(np.arctan2(c[:, 1], c[:, 0])) > np.deg2rad(150)] = np.nan
    s = summarise(c[None], pane=0, origin=np.zeros(3), how="median")
    tail = np.abs(s.angles) > np.deg2rad(155)
    assert np.all(np.isnan(s.centre[tail])) and np.all(np.isfinite(s.centre[np.abs(s.angles) < np.deg2rad(140)]))


class TiltedSphereInGSE(RadialBoundary):
    """A sphere at the origin, in another frame: rotating it must not change its section."""
    name, body, kind, frame = "tilted", "earth", "test", "GSE"
    n_samples = 3

    def radius(self, theta, phi, times):
        return np.full(np.shape(theta), 2.0)


def test_rotation_happens_before_reduction(monkeypatch):
    from scipy.spatial.transform import Rotation
    angles = np.deg2rad([0.0, 10.0, 20.0])
    monkeypatch.setattr(summary, "rotation",
                        lambda f, t, times: Rotation.from_euler("x", angles[: len(times)]))
    s = pane_summary(TiltedSphereInGSE(), "GSM", pane=0, start=0.0, stop=2.0, how="median")
    assert np.allclose(s.centre, 2.0, atol=1e-6)   # a sphere at the origin is rotation-invariant
    assert s.origin.shape == (3,)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/scenes/test_summary.py -v`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `SciQLop/components/scenes/summary.py`

```python
"""Summarise a boundary's sections over an interval, per pane, in the scene frame."""
import warnings
from dataclasses import dataclass

import numpy as np

from .boundary import Plane
from .frames import rotation

PANES = ((0, 1), (1, 2), (2, 0))   # XY, YZ, ZX
N_ANGLES = 720
_GAP = 3  # a resampled angle farther than this many section steps from any valid point is a gap
_REDUCERS = {"median": np.nanmedian, "mean": np.nanmean}


def pane_basis(pane: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    i, j = PANES[pane]
    e = np.eye(3)
    return e[i], e[j], e[3 - i - j]


@dataclass(frozen=True)
class SectionSummary:
    angles: np.ndarray
    centre: np.ndarray
    low: np.ndarray
    high: np.ndarray
    origin: np.ndarray   # pane origin of the polar coordinates, scene frame (3,)
    pane: int

    def curve(self, which: str) -> tuple[np.ndarray, np.ndarray]:
        e1, e2, _ = pane_basis(self.pane)
        r = getattr(self, which)
        closed = np.append(r, r[0])
        a = np.append(self.angles, self.angles[0] + 2 * np.pi)
        return self.origin @ e1 + closed * np.cos(a), self.origin @ e2 + closed * np.sin(a)


def _polar(section: np.ndarray, e1, e2, origin) -> tuple[np.ndarray, np.ndarray]:
    rel = section - origin
    return np.arctan2(rel @ e2, rel @ e1), np.hypot(rel @ e1, rel @ e2)


def _resample(angles: np.ndarray, radii: np.ndarray, grid: np.ndarray) -> np.ndarray:
    keep = np.isfinite(radii)
    if keep.sum() < 2:
        return np.full(grid.shape, np.nan)
    order = np.argsort(angles[keep])
    a, r = angles[keep][order], radii[keep][order]
    out = np.interp(grid, a, r, period=2 * np.pi)
    step = 2 * np.pi / len(angles)
    gap = np.abs(np.angle(np.exp(1j * (grid[:, None] - a[None, :])))).min(axis=1) > _GAP * step
    return np.where(gap, np.nan, out)


def summarise(sections: np.ndarray, pane: int, origin: np.ndarray, how: str) -> SectionSummary:
    e1, e2, _ = pane_basis(pane)
    grid = np.linspace(-np.pi, np.pi, N_ANGLES, endpoint=False)
    resampled = np.stack([_resample(*_polar(s, e1, e2, origin), grid) for s in sections])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN angles stay NaN
        return SectionSummary(grid, _REDUCERS[how](resampled, axis=0), np.nanmin(resampled, axis=0),
                              np.nanmax(resampled, axis=0), origin, pane)


def pane_summary(model, scene_frame: str, pane: int, start: float, stop: float, how: str) -> SectionSummary:
    times = model.sample_times(start, stop)
    to_model = rotation(scene_frame, model.frame, times)
    _, _, normal = pane_basis(pane)
    planes = Plane(normal=to_model.apply(np.tile(normal, (len(times), 1))), offset=np.zeros(len(times)))
    sections = model.cross_section(planes, times)
    to_scene = to_model.inv().as_matrix()
    in_scene = np.einsum("nij,nmj->nmi", to_scene, sections)
    focus = to_model.inv()[len(times) // 2].apply(np.asarray(model.focus, dtype=float))
    # simplify: one polar origin for the whole interval, the focus at mid-interval. Exact when the
    # model frame is the scene frame or the focus is the body centre (every built-in model).
    origin = focus - (focus @ normal) * normal
    return summarise(in_scene, pane, origin, how)
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/scenes/test_summary.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(scenes): summarise a boundary per pane over an interval" -- SciQLop/components/scenes/summary.py tests/scenes/test_summary.py
```

---

### Task 4: Bodies, scenes, registries and the public surface

**Files:**
- Create: `SciQLop/components/scenes/model.py`, `SciQLop/components/scenes/registry.py`, `SciQLop/user_api/scenes/__init__.py`, `tests/scenes/test_registry.py`
- Modify: `tests/test_user_api_thread_classification.py` only if the classification test flags something (expected: nothing, since registration helpers are `@on_main_thread`).

**Interfaces:**
- Consumes: `frame_centres` (Task 1), `RadialBoundary` (Task 2).
- Produces:
  - `Body(name: str, radius: astropy.units.Quantity, threedview: str, symbol: str)` frozen dataclass (`symbol` e.g. `"R_E"`).
  - `Scene(name, body: str, frame: str, boundaries: Mapping[str, str | RadialBoundary], summary: Literal["median","mean"]="median", envelope: bool=True)` frozen; `with_boundary(kind, model) -> Scene`.
  - `ResolvedScene(scene: Scene, body: Body, boundaries: dict[str, RadialBoundary])`; `resolve(scene: Scene | str) -> ResolvedScene`.
  - `class NotRegistered(LookupError)`; `class Registry(Generic[T])` with `register(item, replace=False)`, `get(name)`, `list(**filters)`; module globals `BODIES`, `BOUNDARIES`, `SCENES`.
  - `SciQLop.user_api.scenes`: re-exports `Body, Scene, Plane, RadialBoundary, NotRegistered, FrameError`; `register_body(body, replace=False)`, `register_boundary(model, replace=False)`, `register_scene(scene, replace=False)` (`@on_main_thread`; Task 8 adds tree nodes in them); `list_bodies(**f)`, `list_boundaries(**f)`, `list_scenes(**f)` are re-exports of `Registry.list` bound methods (defined in components, so the user_api AST scan doesn't see them).

- [ ] **Step 1: Write the failing tests** — `tests/scenes/test_registry.py`

```python
import astropy.units as u
import numpy as np
import pytest

from SciQLop.components.scenes.boundary import RadialBoundary
from SciQLop.components.scenes.frames import FrameError
from SciQLop.components.scenes.model import Body, Scene, resolve
from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES, NotRegistered, Registry


class Ball(RadialBoundary):
    name, body, kind, frame = "ball", "earth", "magnetopause", "GSM"

    def radius(self, theta, phi, times):
        return np.full(np.shape(theta), 10.0)


@pytest.fixture
def registries(monkeypatch):
    for reg in (BODIES, BOUNDARIES, SCENES):
        monkeypatch.setattr(reg, "_items", {})
    BODIES.register(Body("earth", 6371.2 * u.km, "Earth", "R_E"))
    BOUNDARIES.register(Ball())


def test_duplicates_raise_unless_replaced(registries):
    with pytest.raises(ValueError, match="boundary 'ball' is already registered"):
        BOUNDARIES.register(Ball())
    BOUNDARIES.register(Ball(), replace=True)


def test_list_filters_on_attributes(registries):
    assert [b.name for b in BOUNDARIES.list(body="earth", kind="magnetopause")] == ["ball"]
    assert BOUNDARIES.list(body="mars") == []


def test_names_resolve_late_and_missing_ones_list_what_exists(registries):
    scene = Scene("Earth", "earth", "GSM", {"magnetopause": "ball", "bow_shock": "later"})
    SCENES.register(scene)
    with pytest.raises(NotRegistered, match="no boundary named 'later'.*available: ball"):
        resolve("Earth")


def test_a_resolved_scene_holds_objects(registries):
    r = resolve(Scene("Earth", "earth", "GSM", {"magnetopause": "ball"}))
    assert r.body.symbol == "R_E" and isinstance(r.boundaries["magnetopause"], Ball)


def test_a_model_of_another_body_is_refused(registries):
    martian = type("M", (Ball,), {"name": "m", "body": "mars"})()
    with pytest.raises(ValueError, match="'m' is a mars model.*earth scene"):
        resolve(Scene("Earth", "earth", "GSM", {"magnetopause": martian}))


def test_a_scene_frame_must_be_centred_on_its_body(registries):
    with pytest.raises(FrameError, match="MSO is centred on Mars, not Earth"):
        resolve(Scene("Earth", "earth", "MSO", {}))


def test_with_boundary_swaps_one_kind(registries):
    s = Scene("Earth", "earth", "GSM", {"magnetopause": "ball"}).with_boundary("magnetopause", "other")
    assert s.boundaries == {"magnetopause": "other"}


def test_public_surface_reexports():
    from SciQLop.user_api import scenes
    for name in ("Body", "Scene", "Boundary", "RadialBoundary", "Plane", "register_body", "register_boundary",
                 "register_scene", "list_bodies", "list_boundaries", "list_scenes"):
        assert hasattr(scenes, name)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/scenes/test_registry.py -v`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 3: Implement** — `SciQLop/components/scenes/registry.py`

```python
from typing import Generic, TypeVar

T = TypeVar("T")


class NotRegistered(LookupError):
    pass


class Registry(Generic[T]):
    def __init__(self, what: str):
        self._what = what
        self._items: dict[str, T] = {}

    def register(self, item: T, replace: bool = False) -> T:
        if item.name in self._items and not replace:
            raise ValueError(f"{self._what} {item.name!r} is already registered")
        self._items[item.name] = item
        return item

    def get(self, name: str) -> T:
        if name not in self._items:
            raise NotRegistered(f"no {self._what} named {name!r}; available: {', '.join(sorted(self._items))}")
        return self._items[name]

    def list(self, **filters) -> list[T]:
        return [i for i in self._items.values() if all(getattr(i, k, None) == v for k, v in filters.items())]


BODIES = Registry("body")
BOUNDARIES = Registry("boundary")
SCENES = Registry("scene")
```

`SciQLop/components/scenes/model.py`:

```python
import dataclasses
from dataclasses import dataclass, field
from typing import Literal, Mapping, Union

import astropy.units as u

from .boundary import Boundary
from .frames import FrameError, frame_centres
from .registry import BODIES, BOUNDARIES, SCENES


@dataclass(frozen=True)
class Body:
    name: str
    radius: u.Quantity
    threedview: str          # 3DView body name, also the `center` of its frames
    symbol: str              # unit label, e.g. "R_E"


@dataclass(frozen=True)
class Scene:
    name: str
    body: str
    frame: str
    boundaries: Mapping[str, Union[str, Boundary]] = field(default_factory=dict)
    summary: Literal["median", "mean"] = "median"
    envelope: bool = True

    def with_boundary(self, kind: str, model: Union[str, Boundary]) -> "Scene":
        return dataclasses.replace(self, boundaries={**self.boundaries, kind: model})


@dataclass(frozen=True)
class ResolvedScene:
    scene: Scene
    body: Body
    boundaries: dict[str, Boundary]


def _model(ref) -> Boundary:
    return BOUNDARIES.get(ref) if isinstance(ref, str) else ref


def _check_frame(frame: str, body: Body) -> None:
    centre = frame_centres().get(frame)
    if centre != body.threedview:
        raise FrameError(f"{frame} is centred on {centre}, not {body.threedview}")


def _check_body(model: Boundary, body: Body) -> None:
    if model.body != body.name:
        raise ValueError(f"{model.name!r} is a {model.body} model; this is a {body.name} scene")


def resolve(scene: Union[Scene, str]) -> ResolvedScene:
    scene = SCENES.get(scene) if isinstance(scene, str) else scene
    body = BODIES.get(scene.body)
    _check_frame(scene.frame, body)
    models = {kind: _model(ref) for kind, ref in scene.boundaries.items()}
    for model in models.values():
        _check_body(model, body)
    return ResolvedScene(scene, body, models)
```

`SciQLop/user_api/scenes/__init__.py`:

```python
"""Planetary scenes: bodies, boundary models and the scenes that combine them.

Register your own from a plugin's ``load(main_window)``; plot one with ``panel.plot_scene(name)``.
"""
from SciQLop.components.scenes.boundary import Boundary, Plane, RadialBoundary
from SciQLop.components.scenes.frames import FrameError
from SciQLop.components.scenes.model import Body, Scene
from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES, NotRegistered
from SciQLop.user_api.threading import on_main_thread

__all__ = ["Body", "Scene", "Plane", "Boundary", "RadialBoundary", "FrameError", "NotRegistered",
           "register_body", "register_boundary", "register_scene",
           "list_bodies", "list_boundaries", "list_scenes"]

list_bodies = BODIES.list
list_boundaries = BOUNDARIES.list
list_scenes = SCENES.list


@on_main_thread
def register_body(body: Body, replace: bool = False) -> Body:
    return BODIES.register(body, replace)


@on_main_thread
def register_boundary(model: RadialBoundary, replace: bool = False) -> RadialBoundary:
    return BOUNDARIES.register(model, replace)


@on_main_thread
def register_scene(scene: Scene, replace: bool = False) -> Scene:
    return SCENES.register(scene, replace)
```

Check `SciQLop.user_api.threading.on_main_thread` is the decorator other user_api modules use (`grep -rn "import on_main_thread" SciQLop/user_api | head -3`); use the same import.

- [ ] **Step 4: Run the tests and the thread-classification test**

Run: `uv run pytest tests/scenes/test_registry.py tests/test_user_api_thread_classification.py -v`
Expected: all pass. If the classification test lists a new name, decorate it with `@on_main_thread` or add it to `NOT_MARSHALED_ON_PURPOSE` with the reason.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(scenes): bodies, scenes and registries" -- SciQLop/components/scenes/model.py \
  SciQLop/components/scenes/registry.py SciQLop/user_api/scenes/__init__.py tests/scenes/test_registry.py
```

---

### Task 5: Built-in planetary content

**Files:**
- Create: `SciQLop/plugins/planetary_scenes/__init__.py`, `SciQLop/plugins/planetary_scenes/models.py`, `SciQLop/plugins/planetary_scenes/plugin.json`, `tests/scenes/test_planetary_models.py`

**Interfaces:**
- Consumes: `RadialBoundary`, `Body`, `Scene`, `register_*` (Tasks 2, 4).
- Produces: model classes `Shue1998`, `Jelinek2012BowShock`, `Vignes2000BowShock`, `Vignes2000MPB`, `Winslow2013Magnetopause`, `Winslow2013BowShock`; `BODIES_DATA`, `MODELS`, `SCENES_DATA` tuples; `register_all()`; `load(main_window)`. Scene names: `"Earth environment"`, `"Mars environment"`, `"Mercury environment"`.

- [ ] **Step 1: Check each model's frame and parameters against its paper**

Read the abstract/method of each paper and confirm or correct the values below before writing code. Record any correction in the commit message.
- Shue et al. 1998, JGR 103(A8), 17691, doi:10.1029/98JA01103 — GSM; r0 = (10.22 + 1.29 tanh(0.184 (Bz + 8.14))) Dp^(−1/6.6); α = (0.58 − 0.007 Bz)(1 + 0.024 ln Dp).
- Jelínek et al. 2012, JGR 117, A05208, doi:10.1029/2011JA017252 — bow shock R0 = 2·15.02·Dp^(−1/6.55), λ = 1.17, r = R0 / (cos θ + √(cos²θ + λ² sin²θ)). Frame expected: aberrated GSE → declare `"GSE"` (aberration ignored, say so in `description`). If the paper uses GSM, declare `"GSM"`.
- Vignes et al. 2000, GRL 27(1), 49, doi:10.1029/1999GL010703 — conics r = L/(1 + ε cos θ) from focus (x0, 0, 0) in aberrated MSO: BS x0 = 0.64, ε = 1.03, L = 2.04; MPB x0 = 0.78, ε = 0.90, L = 0.96 (R_M).
- Winslow et al. 2013, JGR 118, 2213, doi:10.1002/jgra.50237 — MP: R = 1.45 (2/(1 + cos θ))^0.5 from the dipole centre (0, 0, 0.196) R_M; BS: conic X0 = 0.5, ε = 1.04, p = 2.75 with focus (0.5, 0, 0.196) R_M; frame MSO (3DView `MESO`).

- [ ] **Step 2: Write the failing tests** — `tests/scenes/test_planetary_models.py`

```python
import numpy as np
import pytest

from SciQLop.components.scenes.boundary import Plane
from SciQLop.components.scenes.frames import frame_centres
from SciQLop.plugins.planetary_scenes import BODIES_DATA, SCENES_DATA
from SciQLop.plugins.planetary_scenes.models import (Jelinek2012BowShock, Shue1998, Vignes2000BowShock,
                                                     Vignes2000MPB, Winslow2013BowShock, Winslow2013Magnetopause)


def r_at(model, theta_deg):
    t = np.deg2rad(np.array([[theta_deg]]))
    return float(model.radius(t, np.zeros_like(t), np.zeros(1))[0, 0])


@pytest.mark.parametrize("model, theta, expected", [
    (Shue1998(), 0, 10.251873), (Shue1998(), 90, 15.427840),
    (Jelinek2012BowShock(), 0, 13.511736), (Jelinek2012BowShock(), 90, 23.096985),
    (Winslow2013Magnetopause(), 0, 1.45), (Winslow2013Magnetopause(), 90, 2.050610),
])
def test_radius_matches_reference(model, theta, expected):
    assert r_at(model, theta) == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("model, subsolar_x", [
    (Vignes2000BowShock(), 1.644926), (Vignes2000MPB(), 1.285263), (Winslow2013BowShock(), 1.848039)])
def test_conic_subsolar_point(model, subsolar_x):
    focus_plane = Plane(normal=np.array([[0, 0, 1.0]]), offset=np.array([model.focus[2]]))
    s = model.cross_section(focus_plane, np.array([0.0]))[0]
    assert np.nanmax(s[:, 0]) == pytest.approx(subsolar_x, abs=1e-3)


def test_every_scene_frame_is_centred_on_its_body():
    bodies = {b.name: b for b in BODIES_DATA}
    for scene in SCENES_DATA:
        assert frame_centres()[scene.frame] == bodies[scene.body].threedview, scene.name


def test_every_model_is_labelled_and_cited():
    from SciQLop.plugins.planetary_scenes import MODELS
    for m in MODELS:
        assert m.label and m.reference.startswith("doi:") and m.frame in frame_centres()


def test_register_all_makes_the_scenes_resolvable(monkeypatch):
    from SciQLop.components.scenes import registry
    from SciQLop.components.scenes.model import resolve
    from SciQLop.plugins.planetary_scenes import register_all
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
    register_all()
    for scene in SCENES_DATA:
        assert resolve(scene.name).boundaries
```

`register_all()` calls the components registries directly (not the `@on_main_thread` user_api wrappers) so this test needs no Qt.

- [ ] **Step 3: Run to verify they fail**

Run: `uv run pytest tests/scenes/test_planetary_models.py -v`
Expected: FAIL, `ModuleNotFoundError`.

- [ ] **Step 4: Implement** — `SciQLop/plugins/planetary_scenes/models.py`

```python
import numpy as np

from SciQLop.components.scenes.boundary import RadialBoundary

_DP, _BZ = 2.0, 0.0   # nominal solar wind: Dp in nPa, IMF Bz in nT


class Shue1998(RadialBoundary):
    name, body, kind, frame = "shue1998", "earth", "magnetopause", "GSM"
    label = "Shue 1998 (Dp=2 nPa, Bz=0)"
    description = "Earth magnetopause, empirical, nominal solar wind."
    reference = "doi:10.1029/98JA01103"

    def radius(self, theta, phi, times):
        r0 = (10.22 + 1.29 * np.tanh(0.184 * (_BZ + 8.14))) * _DP ** (-1 / 6.6)
        alpha = (0.58 - 0.007 * _BZ) * (1 + 0.024 * np.log(_DP))
        return r0 * (2 / (1 + np.cos(theta))) ** alpha


class Jelinek2012BowShock(RadialBoundary):
    name, body, kind, frame = "jelinek2012", "earth", "bow_shock", "GSE"
    label = "Jelínek 2012 (Dp=2 nPa)"
    description = "Earth bow shock, THEMIS-based, nominal pressure; solar-wind aberration ignored."
    reference = "doi:10.1029/2011JA017252"

    def radius(self, theta, phi, times):
        r0 = 2 * 15.02 * _DP ** (-1 / 6.55)
        return r0 / (np.cos(theta) + np.sqrt(np.cos(theta) ** 2 + 1.17 ** 2 * np.sin(theta) ** 2))


class _Conic(RadialBoundary):
    semi_latus: float
    eccentricity: float

    def radius(self, theta, phi, times):
        return self.semi_latus / (1 + self.eccentricity * np.cos(theta))


class Vignes2000BowShock(_Conic):
    name, body, kind, frame = "vignes2000_bs", "mars", "bow_shock", "MSO"
    label, reference = "Vignes 2000 bow shock", "doi:10.1029/1999GL010703"
    description = "Mars bow shock, conic fit to MGS data; aberration ignored."
    focus, semi_latus, eccentricity = (0.64, 0.0, 0.0), 2.04, 1.03


class Vignes2000MPB(_Conic):
    name, body, kind, frame = "vignes2000_mpb", "mars", "mpb", "MSO"
    label, reference = "Vignes 2000 MPB", "doi:10.1029/1999GL010703"
    description = "Mars magnetic pileup boundary, conic fit to MGS data; aberration ignored."
    focus, semi_latus, eccentricity = (0.78, 0.0, 0.0), 0.96, 0.90


class Winslow2013Magnetopause(RadialBoundary):
    name, body, kind, frame = "winslow2013_mp", "mercury", "magnetopause", "MESO"
    label, reference = "Winslow 2013 magnetopause", "doi:10.1002/jgra.50237"
    description = "Mercury magnetopause, MESSENGER fit, centred on the offset dipole."
    focus = (0.0, 0.0, 0.196)

    def radius(self, theta, phi, times):
        return 1.45 * (2 / (1 + np.cos(theta))) ** 0.5


class Winslow2013BowShock(_Conic):
    name, body, kind, frame = "winslow2013_bs", "mercury", "bow_shock", "MESO"
    label, reference = "Winslow 2013 bow shock", "doi:10.1002/jgra.50237"
    description = "Mercury bow shock, MESSENGER conic fit."
    focus, semi_latus, eccentricity = (0.5, 0.0, 0.196), 2.75, 1.04
```

If Step 1 corrected any frame, parameter or DOI, the code above must carry the corrected value.

`SciQLop/plugins/planetary_scenes/__init__.py`:

```python
"""Built-in planetary scenes. Uses only the public scenes API, so it doubles as an example."""
import astropy.units as u

from SciQLop.components.scenes.model import Body, Scene
from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES

from .models import (Jelinek2012BowShock, Shue1998, Vignes2000BowShock, Vignes2000MPB,
                     Winslow2013BowShock, Winslow2013Magnetopause)

BODIES_DATA = (
    Body("earth", 6371.2 * u.km, "Earth", "R_E"),
    Body("mars", 3389.5 * u.km, "Mars", "R_M"),
    Body("mercury", 2440.0 * u.km, "Mercury", "R_M"),
)
MODELS = (Shue1998(), Jelinek2012BowShock(), Vignes2000BowShock(), Vignes2000MPB(),
          Winslow2013Magnetopause(), Winslow2013BowShock())
SCENES_DATA = (
    Scene("Earth environment", "earth", "GSM", {"magnetopause": "shue1998", "bow_shock": "jelinek2012"}),
    Scene("Mars environment", "mars", "MSO", {"mpb": "vignes2000_mpb", "bow_shock": "vignes2000_bs"}),
    Scene("Mercury environment", "mercury", "MESO",
          {"magnetopause": "winslow2013_mp", "bow_shock": "winslow2013_bs"}),
)


def register_all(replace: bool = False) -> None:
    for registry, items in ((BODIES, BODIES_DATA), (BOUNDARIES, MODELS), (SCENES, SCENES_DATA)):
        for item in items:
            registry.register(item, replace)


def load(main_window):
    from SciQLop.user_api.scenes import register_body, register_boundary, register_scene
    for register, items in ((register_body, BODIES_DATA), (register_boundary, MODELS),
                            (register_scene, SCENES_DATA)):
        for item in items:
            register(item, replace=True)
```

`load` goes through the user_api so Task 8's tree nodes get created; `replace=True` because the test-suite may load plugins more than once per process.

`plugin.json`: copy the shape of a sibling built-in plugin's `plugin.json` (`find SciQLop/plugins -name plugin.json | head -1`), with name "Planetary scenes", description "Earth, Mars and Mercury scenes with magnetopause and bow shock models", no dependencies, enabled by default.

- [ ] **Step 5: Run to verify they pass**

Run: `uv run pytest tests/scenes/test_planetary_models.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(scenes): built-in Earth, Mars and Mercury scenes" -- SciQLop/plugins/planetary_scenes tests/scenes/test_planetary_models.py
```

---

### Task 6: Scene plot — panes, body, boundaries

**Files:**
- Create: `SciQLop/components/scenes/scene_plot.py`, `tests/scenes/test_scene_plot.py`
- Modify: `SciQLop/user_api/scenes/__init__.py` (add `ScenePlot`), `SciQLop/user_api/plot/_panel.py` (add `PlotPanel.plot_scene`)

**Interfaces:**
- Consumes: `resolve`, `ResolvedScene` (Task 4), `pane_summary`, `SectionSummary.curve` (Task 3), `_CallbackErrorOverlay` from `SciQLop.components.plotting.ui.time_sync_panel`, `GraphType`, `PlotType` from SciQLopPlots.
- Produces:
  - `create_scene_plot(panel_impl, resolved: ResolvedScene) -> SciQLopNDProjectionPlot` (labels axes, draws body disks and boundaries).
  - `add_boundary(proj, resolved, kind: str, model) -> list` (the graphs it created; 3 panes × centre (+ low, high when `envelope`)).
  - `remove_boundary(proj, graphs: list) -> None`.
  - `ScenePlot` (user_api, `GuardedImpl` subclass): `.scene -> Scene`, `.set_boundary(kind, model)`, `.add_trajectory(source)` (Task 7), `.projection -> ProjectionPlot`.
  - `PlotPanel.plot_scene(scene: Scene | str) -> ScenePlot`.
  - `remember_scene_plot(proj, scene_plot)` and `scene_plot_for(widget) -> Optional[ScenePlot]` in `components/scenes/scene_plot.py` (walks parents, so a pane resolves to its scene); used by Task 8.

- [ ] **Step 1: Write the failing tests** — `tests/scenes/test_scene_plot.py`

```python
import numpy as np
import pytest

from SciQLop.components.scenes import registry, summary
from SciQLop.plugins.planetary_scenes import register_all

from ..fixtures import *  # noqa: F401, F403


@pytest.fixture
def earth(monkeypatch):
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
    register_all()
    from scipy.spatial.transform import Rotation
    monkeypatch.setattr(summary, "rotation", lambda f, t, times: Rotation.identity(len(times)))


def wait_for_data(qtbot, graph):
    qtbot.waitUntil(lambda: graph.data() is not None and len(graph.data()[0]) > 0, timeout=5000)


def axis_labels(sp):
    proj = sp.projection._get_impl_or_raise()
    return {a.label() for i in range(proj.subplot_count()) for a in (proj.subplot(i).x_axis(), proj.subplot(i).y_axis())}


def test_a_scene_plot_has_three_labelled_panes(plot_panel, earth):
    sp = plot_panel.plot_scene("Earth environment")
    assert sp.projection._get_impl_or_raise().subplot_count() == 3
    assert axis_labels(sp) == {"X GSM [R_E]", "Y GSM [R_E]", "Z GSM [R_E]"}


def test_another_body_labels_its_own_frame_and_unit(plot_panel, earth):
    assert axis_labels(plot_panel.plot_scene("Mars environment")) == {"X MSO [R_M]", "Y MSO [R_M]", "Z MSO [R_M]"}


def test_a_model_in_another_frame_is_rotated(plot_panel, earth, qtbot, monkeypatch):
    from scipy.spatial.transform import Rotation
    seen = set()
    monkeypatch.setattr(summary, "rotation",
                        lambda f, t, times: seen.add((f, t)) or Rotation.identity(len(times)))
    plot_panel.plot_scene("Earth environment")   # Jelinek 2012 is a GSE model in a GSM scene
    qtbot.waitUntil(lambda: ("GSM", "GSE") in seen, timeout=5000)


def test_each_pane_draws_its_own_section(plot_panel, earth, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    xy, yz = (sp._boundary_graphs["magnetopause"][pane][0] for pane in (0, 1))
    for g in (xy, yz):
        wait_for_data(qtbot, g)
    x_xy, y_xy = xy.data()[0], xy.data()[1]
    assert np.nanmax(x_xy) == pytest.approx(10.251873, abs=0.05)
    assert np.nanmax(np.hypot(*yz.data()[:2])) == pytest.approx(15.427840, abs=0.1)   # terminator ring


def test_a_time_range_change_recomputes(plot_panel, earth, qtbot):
    calls = []
    original = summary.pane_summary
    summary_calls = lambda *a, **k: calls.append(a[3:5]) or original(*a, **k)
    from SciQLop.components.scenes import scene_plot
    scene_plot.pane_summary = summary_calls
    try:
        plot_panel.plot_scene("Earth environment")
        plot_panel.time_range = TimeRange(0.0, 3600.0)
        qtbot.waitUntil(lambda: (0.0, 3600.0) in set(calls), timeout=5000)
    finally:
        scene_plot.pane_summary = original


def test_boundary_error_shows_on_overlay(plot_panel, earth, qtbot, monkeypatch):
    from SciQLop.components.scenes import scene_plot
    from SciQLop.components.scenes.frames import FrameError

    def down(*a, **k):
        raise FrameError("could not get GSE → GSM matrices from 3DView: connection refused")

    monkeypatch.setattr(scene_plot, "pane_summary", down)
    sp = plot_panel.plot_scene("Earth environment")
    sub = sp.projection._get_impl_or_raise().subplot(0)
    qtbot.waitUntil(lambda: "3DView" in (sub.overlay().text() or ""), timeout=5000)


def test_closing_scene_plot_mid_fetch(plot_panel, earth, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    plot_panel._get_impl_or_raise().remove_plot(sp.projection._get_impl_or_raise())
    qtbot.wait(300)


def test_swapping_a_boundary_replaces_its_curves(plot_panel, earth):
    sp = plot_panel.plot_scene("Earth environment")
    before = len(sp.projection._get_impl_or_raise().subplot(0).plottables())
    sp.set_boundary("magnetopause", "shue1998")
    assert len(sp.projection._get_impl_or_raise().subplot(0).plottables()) == before
```

Add `from SciQLop.user_api.plot import TimeRange` to the test imports.

Checked by the plan review (SciQLopPlots 0.51.3): the overlay getter is `overlay().text()`; `SciQLopCurveFunction.data()` stays `[None, None]` until a finite range is set, hence `wait_for_data`; `PlotPanel.remove_plot` takes an index and only finds `SciQLopPlot` children, so the test removes the projection through the raw panel's `remove_plot(plot)`.

Before Step 3, confirm that setting `plot_panel.time_range` reaches `proj.time_axis()` of a projection inside the panel (one introspection: set the range, print `proj.time_axis().range()`). If it does not, `_pane_graph` must also observe the panel's time axis; `test_a_time_range_change_recomputes` is the check either way.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/scenes/test_scene_plot.py -v`
Expected: FAIL, `AttributeError: 'PlotPanel' object has no attribute 'plot_scene'`.

- [ ] **Step 3: Implement** — `SciQLop/components/scenes/scene_plot.py`

```python
"""Draw a resolved scene into a three-pane projection plot."""
import functools
import threading

import numpy as np
from PySide6.QtCore import Qt
from SciQLopPlots import GraphType, PlotType

from SciQLop.components.plotting.ui.time_sync_panel import _CallbackErrorOverlay
from .model import ResolvedScene
from .summary import PANES, pane_summary

_AXES = "XYZ"
_KIND_COLOURS = {"magnetopause": "#4FC3F7", "bow_shock": "#FFB74D", "mpb": "#BA68C8"}
_DEFAULT_COLOUR = "#B0BEC5"
_lock = threading.Lock()


@functools.lru_cache(maxsize=64)
def _cached_summary(model, frame, pane, start, stop, how):
    return pane_summary(model, frame, pane, start, stop, how)


class _PaneCurve:
    """One curve of one boundary in one pane; the three curves of a pane share one summary."""

    def __init__(self, model, frame: str, pane: int, which: str, how: str):
        self.model, self.frame, self.pane, self.which, self.how = model, frame, pane, which, how
        self.__name__ = model.label or model.name

    def __call__(self, start, stop):
        with _lock:   # simplify: one summary at a time; the cache makes the 2nd and 3rd curve free
            s = _cached_summary(self.model, self.frame, self.pane, float(start), float(stop), self.how)
        return s.curve(self.which)


def _seeded_projection(panel_impl):
    """simplify: SciQLopMultiPlotPanel.create_plot(Projections) segfaults (SciQLopPlots 0.51.3,
    reported); plot a one-sample curve to get the panes, then drop it. Use create_plot once fixed."""
    z = np.zeros(1)
    proj, seed = panel_impl.plot([z, z, z, z], plot_type=PlotType.Projections,
                                 graph_type=GraphType.ParametricCurve, labels=["", "", ""])
    proj.remove_plottable(seed)
    return proj


def _axis_labels(resolved: ResolvedScene) -> list[str]:
    return [f"{axis} {resolved.scene.frame} [{resolved.body.symbol}]" for axis in _AXES]


def _draw_body(proj, resolved: ResolvedScene) -> None:
    a = np.linspace(0, 2 * np.pi, 181)
    for pane in range(len(PANES)):
        proj.subplot(pane).plot(np.cos(a), np.sin(a), graph_type=GraphType.ParametricCurve,
                                labels=[resolved.body.threedview])


def _style(graph, colour: str, dashed: bool) -> None:
    from PySide6.QtGui import QColor, QPen
    for line in graph.components():
        pen = QPen(QColor(colour), 1.0 if dashed else 2.0)
        pen.setStyle(Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine)
        line.set_pen(pen)


def _pane_graph(proj, pane: int, curve: _PaneCurve, label: str):
    sub = proj.subplot(pane)
    reporter = _CallbackErrorOverlay(curve)
    graph = sub.plot(reporter, graph_type=GraphType.ParametricCurve, labels=[label])
    graph = graph[1] if isinstance(graph, tuple) else graph
    reporter.attach(sub)
    graph.observe(proj.time_axis())
    rng = proj.time_axis().range()
    if np.isfinite(rng.start()) and np.isfinite(rng.stop()):
        graph.set_range(rng)
    return graph


def add_boundary(proj, resolved: ResolvedScene, kind: str, model) -> list:
    scene = resolved.scene
    curves = ["centre", "low", "high"] if scene.envelope else ["centre"]
    colour = _KIND_COLOURS.get(kind, _DEFAULT_COLOUR)
    graphs = []
    for pane in range(len(PANES)):
        pane_graphs = []
        for which in curves:
            label = model.label if which == "centre" else f"{model.label} {'min' if which == 'low' else 'max'}"
            g = _pane_graph(proj, pane, _PaneCurve(model, scene.frame, pane, which, scene.summary), label)
            _style(g, colour, dashed=which != "centre")
            pane_graphs.append(g)
        graphs.append(pane_graphs)
    return graphs


def remove_boundary(proj, graphs: list) -> None:
    for pane, pane_graphs in enumerate(graphs):
        for g in pane_graphs:
            proj.subplot(pane).remove_plottable(g)


def create_scene_plot(panel_impl, resolved: ResolvedScene):
    proj = _seeded_projection(panel_impl)
    proj.set_axis_labels(_axis_labels(resolved))
    _draw_body(proj, resolved)
    return proj
```

Check `proj.subplot(i).remove_plottable` exists (`type(SciQLopPlot.remove_plottable)`), and `graph.components()[i].set_pen` (it exists on line components — see `user_api/plot/_lines.py`). `set_axis_labels` labels the three dimensions; verify with the axis-label test which axis gets which label and fix `_axis_labels` order if needed.

`SciQLop/user_api/scenes/__init__.py` — add:

The lookup from a Qt plot to its `ScenePlot` lives in `components/scenes/scene_plot.py`, so it stays out of the
public surface. A drop can land on one of the three panes rather than the projection itself, so it walks up the parents:

```python
import shiboken6

_SCENE_PLOTS: dict[int, object] = {}


def _key(qobject) -> int:
    return shiboken6.getCppPointer(qobject)[0]


def remember_scene_plot(proj, scene_plot) -> None:
    key = _key(proj)
    _SCENE_PLOTS[key] = scene_plot
    proj.destroyed.connect(lambda *_: _SCENE_PLOTS.pop(key, None))


def scene_plot_for(widget):
    """The ScenePlot showing *widget*: the projection itself or one of its panes; None otherwise."""
    while widget is not None:
        found = _SCENE_PLOTS.get(_key(widget))
        if found is not None:
            return found
        widget = widget.parent()
    return None
```

Test it in `test_scene_plot.py`: `scene_plot_for(proj.subplot(1)) is sp` and `scene_plot_for(<a time-series plot of the same panel>) is None`.

`SciQLop/user_api/scenes/__init__.py` — add (`GuardedImpl` is a bare mixin with no `__init__`: assign `_impl` like `ProjectionPlot.__init__` does):

```python
from SciQLop.components.scenes import scene_plot as _scene_plot
from SciQLop.components.scenes.model import resolve
from SciQLop.user_api.plot._plots import ProjectionPlot
from SciQLop.user_api.plot._thread_safety import GuardedImpl


class ScenePlot(GuardedImpl):
    """A projection plot showing a scene: its body, boundaries and trajectories, in one frame and unit."""

    def __init__(self, proj, resolved):
        self._impl = proj
        self._resolved = resolved
        self._boundary_graphs = {}
        _scene_plot.remember_scene_plot(proj, self)

    def _get_impl_or_raise(self):
        return self._impl

    @property
    @on_main_thread
    def scene(self):
        return self._resolved.scene

    @property
    @on_main_thread
    def projection(self) -> ProjectionPlot:
        return ProjectionPlot(self._impl)

    @on_main_thread
    def set_boundary(self, kind: str, model) -> None:
        """Add or swap the boundary of one kind, by registered name or object."""
        resolved = resolve(self._resolved.scene.with_boundary(kind, model))
        if kind in self._boundary_graphs:
            _scene_plot.remove_boundary(self._impl, self._boundary_graphs.pop(kind))
        self._boundary_graphs[kind] = _scene_plot.add_boundary(self._impl, resolved, kind,
                                                               resolved.boundaries[kind])
        self._resolved = resolved
```

Compare with `ProjectionPlot.__init__`/`_get_impl_or_raise` in `SciQLop/user_api/plot/_plots.py` and copy its dead-object check (it raises a clear error once the Qt object is gone) into `ScenePlot._get_impl_or_raise`.

`PlotPanel.plot_scene` in `SciQLop/user_api/plot/_panel.py` (next to `plot_data`):

```python
    @on_main_thread
    def plot_scene(self, scene) -> "ScenePlot":
        """Plot a planetary scene (a registered name or a Scene): the body, its boundaries
        summarised over the panel's time range, all in the scene's frame and unit.
        Add spacecraft with ``add_trajectory``."""
        from SciQLop.components.scenes.model import resolve
        from SciQLop.components.scenes.scene_plot import create_scene_plot
        from SciQLop.user_api.scenes import ScenePlot
        resolved = resolve(scene)
        sp = ScenePlot(create_scene_plot(self._get_impl_or_raise(), resolved), resolved)
        for kind, model in resolved.boundaries.items():
            sp.set_boundary(kind, model)
        return sp
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/scenes/test_scene_plot.py tests/test_user_api_thread_classification.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(scenes): plot a scene with per-pane boundary summaries" -- SciQLop/components/scenes/scene_plot.py \
  SciQLop/user_api/scenes/__init__.py SciQLop/user_api/plot/_panel.py tests/scenes/test_scene_plot.py
```

---

### Task 7: Trajectories

**Files:**
- Modify: `SciQLop/components/scenes/scene_plot.py` (add `trajectory_source`, `add_trajectory`), `SciQLop/user_api/scenes/__init__.py` (`ScenePlot.add_trajectory`)
- Create: `tests/scenes/test_trajectory.py`

**Interfaces:**
- Consumes: `rotation`, `normalise_frame`, `FrameError` (Task 1); `ResolvedScene` (Task 4); `_CallbackErrorOverlay`.
- Produces:
  - `trajectory_source(source: str, resolved: ResolvedScene) -> Callable[[float, float], list[np.ndarray]]` returning `[t, x, y, z]` in the scene frame and body radii.
  - `add_trajectory(proj, resolved, source: str) -> graph`.
  - `ScenePlot.add_trajectory(source: str)`.
  - Source forms: a 3DView body name (`"MMS1"`, no `/`); a speasy id (`"cda/MMS1_MEC_SRVY_L2_EPHT89D/mms1_mec_r_gsm"`); a SciQLop product path (`"speasy//cda//..."`, resolved through `ProductsModel.node(path.split("//")).metadata()["speasy_id"]`).

- [ ] **Step 1: Write the failing tests** — `tests/scenes/test_trajectory.py`

```python
import numpy as np
import pytest

from SciQLop.components.scenes import scene_plot
from SciQLop.components.scenes.frames import FrameError
from SciQLop.components.scenes.model import ResolvedScene
from SciQLop.plugins.planetary_scenes import BODIES_DATA, SCENES_DATA


class FakeVariable:
    def __init__(self, values, meta):
        self.time = np.array(["2015-10-16T00:00", "2015-10-16T00:10"], dtype="datetime64[ns]")
        self.values = np.asarray(values, dtype=float)
        self.meta = meta
        self.unit = meta.get("UNITS")


EARTH = ResolvedScene(SCENES_DATA[0], BODIES_DATA[0], {})
RE = 6371.2


@pytest.fixture
def fake_speasy(monkeypatch):
    requests = []

    def get_data(product, start, stop, **kwargs):
        requests.append((product, kwargs))
        if product.startswith("cdpp3dview/"):
            return FakeVariable([[RE, 0, 0], [2 * RE, 0, 0]], {"UNITS": "km"})
        if product.endswith("r_gse"):
            return FakeVariable([[RE, 0, 0, RE], [0, RE, 0, RE]], {"UNITS": "km", "COORDINATE_SYSTEM": "GSE>x"})
        if product.endswith("rtn"):
            return FakeVariable([[1, 0, 0]] * 2, {"UNITS": "km", "COORDINATE_SYSTEM": "RTN"})
        return FakeVariable([[1, 0, 0]] * 2, {"UNITS": "km"})

    import speasy
    monkeypatch.setattr(speasy, "get_data", get_data)
    return requests


def test_a_3dview_body_is_fetched_in_the_scene_frame_and_scaled(fake_speasy):
    t, x, y, z = scene_plot.trajectory_source("MMS1", EARTH)(0.0, 600.0)
    assert fake_speasy[0][0] == "cdpp3dview/MMS1" and fake_speasy[0][1]["coordinate_frame"] == "GSM"
    assert np.allclose(x, [1.0, 2.0]) and len(t) == 2


def test_a_product_is_rotated_into_the_scene_frame(fake_speasy, monkeypatch):
    from scipy.spatial.transform import Rotation
    seen = []
    monkeypatch.setattr(scene_plot, "rotation",
                        lambda f, to, times: seen.append((f, to)) or Rotation.from_euler("x", [90, 90], degrees=True))
    t, x, y, z = scene_plot.trajectory_source("cda/X/mms1_mec_r_gse", EARTH)(0.0, 600.0)
    assert seen == [("GSE", "GSM")]
    assert np.allclose(np.stack([x, y, z], axis=1), [[1, 0, 0], [0, 0, 1]], atol=1e-9)   # only 3 columns used


def test_a_product_without_frame_metadata_is_refused(fake_speasy):
    with pytest.raises(FrameError, match="no COORDINATE_SYSTEM"):
        scene_plot.trajectory_source("cda/X/mms1_pos", EARTH)(0.0, 600.0)


def test_a_frame_3dview_does_not_know_is_refused(fake_speasy):
    with pytest.raises(FrameError, match="RTN"):
        scene_plot.trajectory_source("cda/X/mms1_rtn", EARTH)(0.0, 600.0)


def test_a_product_without_unit_is_refused(fake_speasy, monkeypatch):
    import speasy
    monkeypatch.setattr(speasy, "get_data", lambda *a, **k: FakeVariable([[1, 0, 0]] * 2, {"COORDINATE_SYSTEM": "GSM"}))
    with pytest.raises(ValueError, match="no unit"):
        scene_plot.trajectory_source("cda/X/pos", EARTH)(0.0, 600.0)


def test_a_product_that_is_not_a_position_is_refused(monkeypatch):
    import speasy
    monkeypatch.setattr(speasy, "get_data", lambda *a, **k: FakeVariable(
        [[1.0], [2.0]], {"UNITS": "km", "COORDINATE_SYSTEM": "GSM", "FIELDNAM": "Bt"}))
    with pytest.raises(ValueError, match="Bt is not a position"):
        scene_plot.trajectory_source("cda/X/bt", EARTH)(0.0, 600.0)
```

Plus one Qt test in the same file, using `plot_panel`, the `earth` fixture pattern from Task 6 and `fake_speasy`: `sp.add_trajectory("MMS1")` adds a plottable to the projection and time colouring is enabled (`proj.time_color_enabled()`).

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/scenes/test_trajectory.py -v`
Expected: FAIL, `AttributeError: module ... has no attribute 'trajectory_source'`.

- [ ] **Step 3: Implement** — add to `SciQLop/components/scenes/scene_plot.py` (imports go with the module's other imports at the top)

```python
import astropy.units as u

from .frames import FrameError, normalise_frame, rotation

_THREEDVIEW_SAMPLING_S = 60


def _speasy_id(source: str) -> str:
    if source.startswith("speasy//"):
        from SciQLopPlots import ProductsModel
        node = ProductsModel.node(source.split("//"))
        if node is None or "speasy_id" not in node.metadata():
            raise ValueError(f"{source!r} is not a speasy product")
        return node.metadata()["speasy_id"]
    return source


def _fetch(source: str, frame: str, start: float, stop: float):
    """The variable and the frame its values are in."""
    import speasy
    start, stop = (np.datetime64(int(s * 1e9), "ns") for s in (start, stop))
    if "/" not in source:
        v = speasy.get_data(f"cdpp3dview/{source}", start, stop, coordinate_frame=frame,
                            sampling=str(_THREEDVIEW_SAMPLING_S))
        return v, frame
    v = speasy.get_data(_speasy_id(source), start, stop)
    if "COORDINATE_SYSTEM" not in v.meta:
        raise FrameError(f"{source!r} has no COORDINATE_SYSTEM: its frame is unknown")
    return v, normalise_frame(v.meta["COORDINATE_SYSTEM"])


def _in_body_radii(v, body) -> np.ndarray:
    name = v.meta.get("FIELDNAM", "the product")
    unit = v.unit or v.meta.get("UNITS")
    if not unit:
        raise ValueError(f"{name} has no unit")
    if v.values.ndim != 2 or v.values.shape[1] < 3:
        raise ValueError(f"{name} is not a position: values of shape {v.values.shape}")
    return (v.values[:, :3] * u.Unit(unit)).to_value(body.radius)


def trajectory_source(source: str, resolved: ResolvedScene):
    frame = resolved.scene.frame

    def fetch(start, stop):
        v, data_frame = _fetch(source, frame, float(start), float(stop))
        t = v.time.astype("datetime64[ns]").astype("int64") / 1e9
        xyz = rotation(data_frame, frame, t).apply(_in_body_radii(v, resolved.body))
        return [t] + [np.ascontiguousarray(xyz[:, i]) for i in range(3)]

    fetch.__name__ = source
    return fetch


def add_trajectory(proj, resolved: ResolvedScene, source: str):
    reporter = _CallbackErrorOverlay(trajectory_source(source, resolved))
    name = source.split("/")[-1]
    graph = proj.plot(reporter, labels=[name] * 3, graph_type=GraphType.ParametricCurve)
    graph = graph[1] if isinstance(graph, tuple) else graph
    reporter.attach(proj)
    proj.set_time_color_enabled(True)
    return graph
```

`u.Unit("km")` parses CDF unit strings; if a real product's `UNITS` fails to parse, `_in_body_radii` raises astropy's `ValueError`, which the overlay shows — acceptable.

Verify `proj.plot(callable, labels=..., graph_type=ParametricCurve)` is the right call on an existing projection (the probe used `panel.plot(..., plot_type=Projections)`); if `proj.plot` rejects it, use `panel_impl.plot(reporter, plot_type=PlotType.Projections, graph_type=GraphType.ParametricCurve, labels=..., index=<proj index>)` or `proj.parametric_curve(...)` — check `help(type(proj).plot)` and `help(type(proj).parametric_curve)` first.

`ScenePlot.add_trajectory` in `SciQLop/user_api/scenes/__init__.py`:

```python
    @on_main_thread
    def add_trajectory(self, source: str):
        """Draw a spacecraft orbit in the scene's frame and unit.

        source: a 3DView body name ("MMS1"), a speasy id, or a SciQLop product path.
        Products must declare COORDINATE_SYSTEM and a unit; others are refused."""
        return _scene_plot.add_trajectory(self._impl, self._resolved, source)
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/scenes/test_trajectory.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(scenes): trajectories converted to the scene frame and unit" -- SciQLop/components/scenes/scene_plot.py \
  SciQLop/user_api/scenes/__init__.py tests/scenes/test_trajectory.py
```

---

### Task 8: Products tree and drag and drop

**Files:**
- Create: `SciQLop/components/scenes/tree.py`, `tests/scenes/test_scene_tree.py`
- Modify: `SciQLop/user_api/scenes/__init__.py` (register_* add nodes), `SciQLop/components/plotting/ui/time_sync_panel.py:1250-1265` (`ProductDnDCallback.call`), `SciQLop/user_api/layers/_provider.py:15,30-34` (`sciqlop_kind`)

**Interfaces:**
- Consumes: `add_product_node`, `ProductsModelNodeType` from `SciQLop.core.models`; `ParameterType` from `SciQLop.core.enums`; `scene_plot_for` (Task 6).
- Produces:
  - `KIND_KEY = "sciqlop_kind"`; `add_scene_node(scene)`, `add_boundary_node(model)`.
  - `drop_handler(kind: str, target_is_scene: bool) -> Callable[[plot, product: list[str], panel], None]` — the (kind, target) table.
  - `ProductDnDCallback.call` dispatches through it; layers tag `sciqlop_kind = "layer"`.

- [ ] **Step 1: Write the failing tests** — `tests/scenes/test_scene_tree.py`

```python
import pytest

from SciQLop.components.scenes import tree


@pytest.mark.parametrize("kind, on_scene, expected", [
    ("scene", False, "plot_scene"), ("scene", True, "plot_scene"),
    ("boundary", True, "set_boundary"), ("boundary", False, "refuse"),
    ("product", True, "add_trajectory"), ("product", False, "plot_product"),
    ("layer", False, "attach_layer"), ("layer", True, "attach_layer"),
])
def test_drop_table(kind, on_scene, expected):
    assert tree.drop_handler(kind, on_scene).__name__ == expected


def test_registering_adds_tree_nodes(main_window, monkeypatch):
    from SciQLopPlots import ProductsModel
    from SciQLop.components.scenes import registry
    from SciQLop.plugins.planetary_scenes import load
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
    load(main_window)
    scene = ProductsModel.node(["Scenes", "Earth environment"])
    model = ProductsModel.node(["Models", "Earth", "magnetopause", "Shue 1998 (Dp=2 nPa, Bz=0)"])
    assert scene.metadata()["sciqlop_kind"] == "scene"
    assert model.metadata()["sciqlop_kind"] == "boundary" and "doi:" in model.metadata()["description"]


def test_dropping_a_scene_creates_a_scene_plot(plot_panel, main_window, monkeypatch):
    ...  # build the mime data like existing DnD tests do (grep tests for ProductDnDCallback / encode_mime)
```

Fill the last test by copying the mime construction from an existing products drag-and-drop test (`grep -rln "PRODUCT_LIST_MIME_TYPE\|encode_mime" tests | head`): drop `["Scenes", "Earth environment"]` onto the panel's first plot, assert the panel now has a projection plot registered in `scene_plot_for`. Add one more: dropping a boundary onto a non-scene plot shows the refusal message on that plot's overlay.

Also add to the existing layer DnD test file (find it with `grep -rln "attach_layer\|LAYER_META_KEY" tests`) nothing new — its tests must keep passing after the refactor.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/scenes/test_scene_tree.py -v`
Expected: FAIL, `ModuleNotFoundError: SciQLop.components.scenes.tree`.

- [ ] **Step 3: Implement** — `SciQLop/components/scenes/tree.py`

```python
"""Scenes and models in the products tree, and what dropping them does."""
from SciQLopPlots import OverlayLevel, OverlayPosition, OverlaySizeMode

from SciQLop.core.enums import ParameterType
from SciQLop.core.models import ProductsModelNodeType, add_product_node

KIND_KEY = "sciqlop_kind"


def show_drop_error(plot, message: str) -> None:
    plot.overlay().show_message(message, OverlayLevel.Error, OverlaySizeMode.FitContent, OverlayPosition.Top)


def _add_node(path: list[str], name: str, kind: str, description: str) -> None:
    add_product_node(path, name, "scenes", {KIND_KEY: kind, "description": description,
                                             "stable_id": "/".join(path + [name])},
                     ProductsModelNodeType.PARAMETER, ParameterType.Scalar)


def add_scene_node(scene) -> None:
    _add_node(["Scenes"], scene.name, "scene", f"{scene.body} scene in {scene.frame}")


def add_boundary_node(model) -> None:
    _add_node(["Models", model.body.capitalize(), model.kind], model.label or model.name, "boundary",
              f"{model.description} {model.reference}".strip())


def plot_scene(plot, product, panel):
    from SciQLop.user_api.plot import PlotPanel   # see note below on wrapping the panel impl
    PlotPanel(panel).plot_scene(product[-1])


def set_boundary(plot, product, panel):
    from SciQLop.components.scenes.registry import BOUNDARIES
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    model = next(m for m in BOUNDARIES.list() if (m.label or m.name) == product[-1])
    scene_plot_for(plot).set_boundary(model.kind, model)


def add_trajectory(plot, product, panel):
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    scene_plot_for(plot).add_trajectory("//".join(product))


def refuse(plot, product, panel):
    show_drop_error(plot, f"{product[-1]} is a model: drop it on a scene plot of its body")


def plot_product(plot, product, panel):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product as _plot_product
    _plot_product(plot, product)


def attach_layer(plot, product, panel):
    from SciQLop.components.plotting.ui.time_sync_panel import attach_layer as _attach_layer
    _attach_layer(plot, product, panel=panel)


_TABLE = {
    ("scene", False): plot_scene, ("scene", True): plot_scene,
    ("boundary", True): set_boundary, ("boundary", False): refuse,
    ("product", True): add_trajectory, ("product", False): plot_product,
    ("layer", False): attach_layer, ("layer", True): attach_layer,
}


def drop_handler(kind: str, target_is_scene: bool):
    return _TABLE[(kind, target_is_scene)]
```

For `plot_scene`, check how the user_api wraps an existing `TimeSyncPanel` impl into a `PlotPanel` (`grep -n "class PlotPanel" -A20 SciQLop/user_api/plot/_panel.py`) and use that constructor; if wrapping is awkward, call `create_scene_plot` + `ScenePlot` directly as `PlotPanel.plot_scene` does. A boundary dropped on a scene of another body: `set_boundary` raises `ValueError` from `resolve`; catch it in `ProductDnDCallback.call` and show it with `refuse`'s overlay style (never raise from the drop slot).

`ProductDnDCallback.call` becomes:

```python
    def call(self, plot, mime_data: QMimeData):
        from SciQLop.components.scenes.tree import KIND_KEY, drop_handler, show_drop_error
        from SciQLop.components.scenes.scene_plot import scene_plot_for
        for product in decode_mime(mime_data):
            node = ProductsModel.node(product)
            if node is None:
                continue
            kind = node.metadata().get(KIND_KEY, "product")
            try:
                drop_handler(kind, scene_plot_for(plot) is not None)(plot, product, self.parent())
            except Exception as e:
                log.error("drop of %s failed", product, exc_info=True)
                show_drop_error(plot, f"{product[-1]}: {e}")
```

Add a drop test onto a **pane** (`proj.subplot(1)`) of a scene plot, not only onto the projection: a boundary dropped there must swap the scene's boundary. In `_provider.py`, replace `LAYER_META_KEY: "true"` with `"sciqlop_kind": "layer"` and delete `LAYER_META_KEY`; `grep -rn "LAYER_META_KEY\|sciqlop_layer" SciQLop tests` must return nothing afterwards (update any test that referenced it).

Smart search: check that it indexes node `description` metadata (`grep -n "description" SciQLop/components/smart_search/*.py SciQLop/components/products/smart_search_domain.py`). If it does, typing "magnetopause" finds the models with no extra code; add that as a test in `test_scene_tree.py`. If it doesn't, put the kind in the node name's path (it already is: `Models/Earth/magnetopause/...`) and say so in the commit message.

`SciQLop/user_api/scenes/__init__.py`: `register_scene` calls `tree.add_scene_node(scene)` after registering, `register_boundary` calls `tree.add_boundary_node(model)`. With `replace=True` and an existing node, check `add_product_node` tolerates re-adding (read `SciQLop/core/models.py`); if it duplicates, skip the node when the name was already registered.

- [ ] **Step 4: Run the scene tests and every layer/DnD test**

Run: `uv run pytest tests/scenes tests -k "layer or dnd or drop or scene" -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(scenes): scenes and models in the products tree; drops dispatch on (kind, target)" -- \
  SciQLop/components/scenes/tree.py SciQLop/user_api/scenes/__init__.py \
  SciQLop/components/plotting/ui/time_sync_panel.py SciQLop/user_api/layers/_provider.py tests/scenes/test_scene_tree.py \
  <any layer test file you updated>
```

---

### Task 9: End-to-end shot, changelog, docs, full suite

**Files:**
- Create: `tests/scenes/test_scene_end_to_end.py`, `tests/scenes/data/mms1_gsm_20151016.npz` (recorded trajectory)
- Modify: `CHANGELOG.md`, `/home/jeandet/.claude/memory/sciqlop-user-api.md` (global user_api memory), project memory `design-scenes-and-models.md`

- [ ] **Step 1: Record MMS1's 2015-10-16 trajectory**

Scratchpad script: `speasy.get_data("cdpp3dview/MMS1", "2015-10-16", "2015-10-17", coordinate_frame="GSM", sampling="600")` → save `time` (datetime64[ns] as int64) and `values` with `np.savez_compressed` to `tests/scenes/data/mms1_gsm_20151016.npz`.

- [ ] **Step 2: Write the end-to-end test**

```python
from pathlib import Path

import numpy as np

from SciQLop.components.scenes import registry, summary
from SciQLop.plugins.planetary_scenes import register_all

from ..fixtures import *  # noqa: F401, F403

DATA = Path(__file__).parent / "data"


def test_the_mms_orbit_shot_in_three_lines(plot_panel, qtbot, monkeypatch):
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
    register_all()
    recorded = np.load(DATA / "mms1_gsm_20151016.npz")

    class Var:
        time = recorded["time"].astype("datetime64[ns]")
        values = recorded["values"]
        meta = {"UNITS": "km"}
        unit = "km"

    import speasy
    monkeypatch.setattr(speasy, "get_data", lambda *a, **k: Var())
    from scipy.spatial.transform import Rotation
    monkeypatch.setattr(summary, "rotation", lambda f, t, times: Rotation.identity(len(times)))

    from SciQLop.user_api.plot import TimeRange
    plot_panel.time_range = TimeRange("2015-10-16", "2015-10-17")
    sp = plot_panel.plot_scene("Earth environment")
    sp.add_trajectory("MMS1")

    proj = sp.projection._get_impl_or_raise()
    qtbot.waitUntil(lambda: len(proj.plottables()) >= 1, timeout=5000)
    assert proj.time_color_enabled()
```

Adjust `TimeRange` import to wherever `plot_panel.time_range` takes its type from (see other tests using `time_range =`).

- [ ] **Step 3: Run it**

Run: `uv run pytest tests/scenes/test_scene_end_to_end.py -v`
Expected: PASS.

- [ ] **Step 4: Manual visual check**

Scratchpad script (offscreen, like the gallery `shots` scripts in `../sciqlop.github.io/scripts/shots/`): real network, Earth scene, MMS1 on 2015-10-16, `panel.save(...)` a PNG; open it and check: Earth disk in each pane, magnetopause ≈ 10.3 R_E at the nose in XY and ZX, a ring in YZ, dashed envelopes, orbit time-coloured, labels "X GSM [R_E]". Measure at native resolution before claiming anything is wrong.

- [ ] **Step 5: CHANGELOG and memories**

`CHANGELOG.md`, under the unreleased section's Plotting heading (match its existing style):
- "Planetary scenes: `panel.plot_scene("Earth environment")` draws the planet and its magnetopause and bow shock, summarised over the panel's time range; `add_trajectory("MMS1")` adds an orbit, converted to the scene's frame and unit. Earth, Mars and Mercury are built in; plugins register their own bodies, models and scenes."
- "Products tree: Scenes/ and Models/ entries; drop a scene on a panel, a model on a scene plot, a spacecraft position on a scene plot."

Global memory `sciqlop-user-api.md`: add a "Scenes" block — `from SciQLop.user_api.scenes import Body, Scene, RadialBoundary, register_body/boundary/scene, list_*`; `panel.plot_scene(name|Scene) -> ScenePlot`; `ScenePlot.add_trajectory(3dview body | speasy id | product path)`, `.set_boundary(kind, name|model)`, `.projection`; a model subclasses `RadialBoundary` and writes `radius(theta, phi, times)` ((n, m) arrays, θ from +X around `focus`), declares `name, body, kind, frame, label, reference`.

Project memory `design-scenes-and-models.md`: implemented, commits, what's skipped (non-radial faint mode, alias table, spacecraft cut, surfaces), the create_plot segfault workaround to drop once SciQLopPlots ships the fix.

- [ ] **Step 6: flake8 and the full suite**

Run: `git ls-files '*.py' | xargs uv run flake8 --select=E9,F63,F7,F82 --count` → `0`.
Run: `uv run pytest` (foreground, alone) → read the real pass/fail count and exit code. All pass.

- [ ] **Step 7: Commit**

```bash
git commit -m "test(scenes): MMS orbit end to end; changelog" -- tests/scenes/test_scene_end_to_end.py \
  tests/scenes/data/mms1_gsm_20151016.npz CHANGELOG.md
```

(Memories live outside the repo; no commit for them.)
