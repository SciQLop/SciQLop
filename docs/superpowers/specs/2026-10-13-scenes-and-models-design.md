# Scenes and models for projection plots — design

Date: 2026-10-13. Status: approved in brainstorm; revised after an opencode review; awaiting user review.

## Goal

Make planetary projection plots easy.
Today the MMS orbit shot (`sciqlop.github.io/scripts/shots/gallery_02_projection.py`) takes about 15 manual lines:
fetch the position, divide by R_E, hand-write labels, reach into `_get_impl_or_raise()`.
It draws no planet and no boundary.

After this work:

```python
proj = panel.plot_scene("Earth environment")
proj.add_trajectory("MMS1")
```

draws Earth, the magnetopause and the bow shock in each pane, and the MMS1 orbit, all in GSM and R_E,
for the panel's time range.

Plugins can register their own **bodies**, **models** and **scenes**, so they are reused across SciQLop.

## Non-goals

- A 3D viewer, and so model surfaces. `RadialBoundary` makes a `surface()` cheap to add when a viewer exists.
- Field models (T89, dipole) and region classifiers. They are a second model kind, values at positions.
  This spec only covers boundaries.
- Cutting panes anywhere but through the body centre (for example through the spacecraft).
- An entry-point group for non-plugin packages. Add it when a package such as LPP `space` wants to register models.

## 1. Units and frames

Rule: everything declares its frame and unit. Nothing is mixed silently.

- **Units** convert with `astropy.units`. It is already installed through speasy.
  Each body defines its radius, so R_E, R_M and so on are plain astropy units.
- **Frames** convert with 3DView rotation matrices (`get_transform_matrices`,
  https://3dview.irap.omp.eu/pages/restServices.html).
  It knows 106 frames, including GSE, GSM, SM, MSO (Mars), MESO (Mercury), VSO, KSM and JSM.
  It returns one 3x3 float32 matrix per time step.
- Matrices are rotations only; translation is dropped. So a transform is allowed **only between frames
  centred on the same body** (`get_frames` gives each frame's `center`). A scene's frame must be centred on its body.
  This catches real mistakes: 3DView happily returns an MSO (Mars) → MEME (Mercury) matrix.
- Matrices are interpolated to the needed times with quaternion SLERP (`scipy.spatial.transform.Slerp`),
  built with `Rotation.from_matrix`, which projects the float32 matrices onto the nearest rotation.
  Linear interpolation of matrix elements does not give a rotation.
- One SciQLop function hides where matrices come from:

  ```python
  def rotation(from_frame: str, to_frame: str, times: np.ndarray) -> scipy.spatial.transform.Rotation
  ```

  - Identity when the frames are equal, with no network call.
  - Matrices are fetched per whole day at 600 s sampling and cached by (from, to, day).
  - Until speasy wraps the endpoint ([speasy#406](https://github.com/SciQLop/speasy/issues/406)),
    it calls the REST endpoint itself, marked `simplify:` with "switch to speasy once #406 is released".
    The 3DView `get_trajectory` client used by `add_trajectory` (§4) sits next to it, with the same note.
- An unknown frame, a centre mismatch or 3DView being down raises with the two frame names.
  It never falls back to identity.
- **Frame names from metadata** are normalised: keep the part before `>` (`'GSE>Geocentric Solar Ecliptic'` → `GSE`),
  upper-case, then map through a small alias table to a 3DView name. A frame 3DView doesn't know (`RTN`) is refused.

Plane offsets need no conversion: frames share their origin, and a rotation keeps n·x = d true.

## 2. Boundaries

### Contract

```python
class Boundary(Protocol):
    name: str              # registry key, e.g. "shue1998"
    body: str              # body name, e.g. "earth"
    kind: str              # "magnetopause", "bow_shock", "mpb", ... (free string)
    frame: str             # frame the model computes in
    label: str             # legend text, including fixed inputs: "Shue 1998 (Dp=2 nPa, Bz=0)"
    description: str
    reference: str         # paper citation or DOI

    def sample_times(self, start: float, stop: float) -> np.ndarray: ...
    def cross_section(self, planes: Plane, times: np.ndarray) -> np.ndarray: ...   # (n, m, 3)
```

```python
@dataclass(frozen=True)
class Plane:
    normal: np.ndarray     # (n, 3) unit normals, one per time
    offset: np.ndarray     # (n,) signed distances from the origin, body radii
```

- The scene asks the model which times to sample in `[start, stop]`, then asks for one section per time.
- `Plane` holds one plane **per time**, in the **model's** frame and body radii.
  The scene's plane is fixed in the scene frame. When the frames differ, it maps to a different plane
  in the model frame at each time (GSE→GSM turns by about 20° over 2015-10-16), so the scene rotates the normal per time.
- The result is one section per time, in the model frame and body radii.
  It may contain NaN where a section is cut, for example an open tail.
- How a model's parameters are driven (constants, solar-wind data, a simulation) is its own business.
- A model computes, the scene summarises. Models never compute statistics.

### RadialBoundary

Most planetary boundaries are star-shaped around a point: r = r(θ, φ, t).
A base class gives those models everything from one method:

```python
class RadialBoundary(Boundary):
    focus: tuple[float, float, float] = (0, 0, 0)    # model frame, body radii; conic focus for Mars, Mercury
    theta_max: float = np.deg2rad(150)               # beyond it the tail is open: NaN
    cadence: Optional[float] = None                  # seconds; None = fixed sample count

    def radius(self, theta, phi, times) -> np.ndarray: ...   # the only method a model writes

    # provided:
    def sample_times(self, start, stop): ...
    def cross_section(self, planes, times): ...
```

- `radius` is vectorised over time: shape (n_times, n_directions). θ and φ are measured from the `focus`.
- Sample times: every `cadence` seconds, or a fixed 200 samples over the interval when `cadence` is None.
- `cross_section` sweeps rays inside each plane from the **projection of the focus onto the plane**,
  over a fixed grid of in-plane angles (§3).
  - When the plane contains the focus, the point is `radius(dir) * dir`. That is exact and cheap.
  - When it does not (Mars and Mercury, YZ pane: x = 0 misses a focus on the X axis), the crossing on each ray
    is found by bisection on `|p - focus| - radius(direction of p from focus)`.
  - A ray that doesn't cross the boundary, or crosses beyond `theta_max`, gives NaN.
- A non-radial model implements `cross_section` itself.

## 3. Interval summary

A scene follows its panel's time range, so a boundary is drawn as a summary over the interval.

Each pane has a fixed 2D basis (e1, e2) in the scene frame: XY → (x, y), YZ → (y, z), ZX → (z, x).
The in-plane angle is `atan2(v·e2, v·e1)` around the pane's centre point, everywhere.

1. `times = model.sample_times(start, stop)`. Rotate the pane's normal into the model frame at each time.
   Call `model.cross_section(planes, times)`.
2. Rotate each section back into the scene frame, using that time's matrix.
3. Express each section as r(angle) around the pane's centre point, and **resample it onto one common angle grid**
   (720 angles) by interpolation. Sections from different times don't share angles otherwise.
   - The centre point is the focus projected onto the pane, in the scene frame, at the interval's mid time.
     `simplify:` it assumes the focus barely moves over an interval. True when model and scene frames match,
     and when the focus is the body centre.
4. Per angle, reduce over time with `nanmedian` or `nanmean` for the curve, and `nanmin` / `nanmax` for the envelope.

The reduction happens in the scene frame, after the per-time rotation.
Reducing in the model frame would blur the frame's own swing into the boundary's motion.

Display options per boundary in a scene: `summary="median" | "mean"`, `envelope: bool`.
The envelope is two thin dashed lines: projection panes have no fill-between.
Non-radial boundaries can't be reduced per angle. They are drawn as every sampled section, thin and faint.

## 4. Bodies and scenes

```python
@dataclass(frozen=True)
class Body:
    name: str                 # "earth"
    radius: astropy.units.Quantity
    threedview: str           # 3DView body name, e.g. "EARTH"

@dataclass(frozen=True)
class Scene:
    name: str                                    # "Earth environment"
    body: str                                    # body name
    frame: str                                   # "GSM"; must be centred on the body
    boundaries: Mapping[str, str | Boundary]     # kind → model name (or an object, for notebooks)
    summary: Literal["median", "mean"] = "median"
    envelope: bool = True

    def with_boundary(self, kind: str, model: str | Boundary) -> "Scene": ...
```

- A scene is data. Variants are `dataclasses.replace(...)` or `with_boundary(...)`.
- The scene unit is the body radius.
- Each pane cuts through the body centre: z = 0 for XY, x = 0 for YZ, y = 0 for ZX.
- Models whose `body` differs from the scene's are refused.

### Plotting

```python
proj = panel.plot_scene("Earth environment")   # name or Scene
proj.add_trajectory("MMS1")                    # 3DView body name
proj.add_trajectory("speasy//cda//MMS//MMS1//MEC//...//mms1_mec_r_gsm")   # any position product
```

`plot_scene` returns a `ScenePlot` wrapping the three-pane projection plot. Each pane gets:

- the body disk,
- each boundary's summary curve and envelope for that pane's plane, labelled with the model's `label`,
  recomputed when the panel time range changes.

Boundaries are drawn **per pane**: each pane has its own plane, unlike the orbit,
which is one 3D curve projected on every pane. So `add_model_curve` (one 3D curve for all panes) does not fit.

**Nothing blocks the GUI thread.** Boundary computation and 3DView calls run where SciQLopPlots runs
callable-backed graphs: off the GUI thread, once per settled range change.
A failure (3DView unreachable, unknown frame) shows on the plot's error overlay,
the one virtual products already use. It never raises inside a Qt slot.

`add_trajectory`:
- A 3DView body name is fetched with `get_trajectory` directly in the scene frame.
- Any other product is converted to the scene frame and unit using its `COORDINATE_SYSTEM` (normalised, §1)
  and unit metadata. It is refused, with a message, when either is missing or the frame is unknown.
- It is drawn as a time-coloured curve with the existing linked time marker.

The axis labels come from the scene, for example "X GSM [R_E]".

## 5. Registration

```python
register_body(Body(name="earth", radius=6371.2 * u.km, threedview="EARTH"))
register_boundary(Shue1998())
register_scene(Scene(name="Earth environment", body="earth", frame="GSM",
                     boundaries={"magnetopause": "shue1998", "bow_shock": "jelinek2012"}))

list_bodies(); list_boundaries(body="mars", kind="bow_shock"); list_scenes(body="earth")
```

- One small `Registry[T]` class, instantiated three times. It keys values by `name`, has `get` and filtered `list`.
- A duplicate name raises `ValueError` with the name. `register_*(..., replace=True)` replaces on purpose.
- What gets registered is an instance. A model that needs settings is registered as a configured instance
  under its own name (`"shue1998-omni"`).
- Scenes refer to bodies and models **by name, resolved at `plot_scene` time**. Plugin load order doesn't matter.
  A missing name raises with the list of available names.
- Plugins register from their `load(main_window)`.

## 6. Products tree and drag and drop

```
Scenes/
    Earth environment
Models/
    Earth/
        magnetopause/   Shue 1998
        bow_shock/      Jelinek 2012
```

- `register_scene` and `register_boundary` add the node. Bodies have no node; they are folders under `Models/`.
- A scene node is a listing. Its model names resolve only when it is plotted.
- Tooltips show `description` and `reference`. Smart search indexes them.

| Drop | onto | result |
|---|---|---|
| scene | panel | new scene plot |
| model | scene plot, same body | adds that kind, or swaps the current one |
| model | anything else | refused, with a message |
| position product | scene plot | `add_trajectory` (converted, not plotted raw) |
| anything else | scene plot | refused, with a message |

**Refactor of `ProductDnDCallback.call`** (`time_sync_panel.py:1250`). Today it is an if/else on
`node.metadata()["sciqlop_layer"]` (`LAYER_META_KEY`, `user_api/layers/_provider.py:15`).
It becomes a lookup on **(node kind, target)**:
- node kind is a new metadata key `sciqlop_kind` (`layer`, `scene`, `boundary`), or `product` when absent;
- target is a scene plot or any other plot.

Layers move onto `sciqlop_kind = "layer"`. Producer (`_provider.py`) and consumer change in the same commit,
and `LAYER_META_KEY` goes away.

## 7. Built-in content

A built-in plugin, `SciQLop/plugins/planetary_scenes/`, using only the public API above:

| Body | Scene frame | Models |
|---|---|---|
| Earth | GSM | Shue 1998 magnetopause (Dp = 2 nPa, Bz = 0); Jelinek 2012 bow shock (Dp = 2 nPa) |
| Mars | MSO | Vignes 2000 bow shock and MPB (conics, focus offset on X) |
| Mercury | MESO | Winslow 2013 magnetopause and bow shock |

- The fixed inputs appear in each model's `label`, so the plot says the boundary is nominal, not measured.
- Solar-wind-driven variants are later registrations, not API changes.
- Mercury's papers say "MSO"; 3DView calls Mercury's solar-orbital frame `MESO`. `MSO` is Mars.
  A test checks that every built-in scene frame is centred on its body.
- Models are written from the papers, cited in `reference`.
  Test reference values are hard-coded, computed once with LPP `space` (GPLv3, like SciQLop; local checkout,
  not a dependency) and checked against the papers' published standoff distances.

## 8. Code layout

- `SciQLop/components/scenes/` — frames (`rotation`, frame-name normalisation, 3DView client),
  boundary base classes, summary, registries, scene plot.
- `SciQLop/user_api/scenes/` — public surface: `Body`, `Scene`, `Boundary`, `RadialBoundary`, `Plane`,
  `register_*`, `list_*`. `plot_scene` on `PlotPanel`. `@on_main_thread` where Qt is touched.
- `SciQLop/plugins/planetary_scenes/` — built-in content.

## 9. Testing

No test touches the network: 3DView responses are recorded JSON.

- Frames: identity short-cut; SLERP output stays orthonormal; unknown frame raises; frames centred on different
  bodies raise; `'GSE>Geocentric Solar Ecliptic'` normalises to `GSE`; `RTN` is refused.
- `RadialBoundary.cross_section`: a sphere gives circles in every plane; a conic with an X-offset focus gives
  finite, correct sections in all three panes, including YZ (bisection path); a different plane per time gives a
  different section per time; rays past `theta_max` give NaN.
- Summary: two sections sampled at different angles are resampled onto the common grid; median, mean, min and max
  per angle; NaN is ignored; an asymmetric section keeps its orientation; rotation happens before reduction.
- Mixed frames end to end: a synthetic GSE model in a GSM scene.
- Models: Shue 1998, Jelinek 2012, Vignes 2000, Winslow 2013 against hard-coded reference values.
- Registry: duplicates raise; `replace=True` replaces; late resolution; missing-name error lists names.
- Scene plot: three panes get their own sections; a range change recomputes; axis labels and legend labels;
  a model for another body is refused; a range change with 3DView unreachable shows an overlay error and doesn't raise.
- `add_trajectory`: km/GSE product lands in R_E/GSM; a product without frame metadata is refused.
- Drag and drop: the (kind, target) table routes layer, scene, boundary, position product and refusals.
- The MMS shot rewritten with `plot_scene` as an end-to-end test (recorded data).

## Checks during planning

- Whether a per-pane callable curve on a projection subplot follows the panel time range and runs off the GUI thread,
  as `add_model_curve` does. If not, the scene plot connects the range signal itself and computes in a worker.
- 3DView describes its GSM as "definition not valid after 31/12/2014", yet returns matrices for later dates.
  Compare its GSE→GSM matrices with MMS MEC's own GSE and GSM positions for 2015-10-16 before trusting them.
- Which frame each built-in model is defined in. Jelinek 2012 is likely aberrated GSE, which would make the Earth scene
  exercise the mixed-frame path for real.
- The 3DView body names for Earth, Mars and Mercury (`get_bodies`).
