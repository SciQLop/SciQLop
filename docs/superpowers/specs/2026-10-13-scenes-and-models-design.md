# Scenes and models for projection plots — design

Date: 2026-10-13. Status: approved in brainstorm, spec under review.

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

- A 3D viewer. The model contract keeps `surface()` available for one later.
- Field models (T89, dipole) and region classifiers. They are a second model kind, values at positions.
  This spec only covers boundaries.
- An entry-point group for non-plugin packages. Add it when a package such as LPP `space` wants to register models.

## 1. Units and frames

Rule: everything declares its frame and unit. Nothing is mixed silently.

- **Units** convert with `astropy.units`. It is already installed through speasy.
  Each body defines its radius, so R_E, R_M and so on are plain astropy units.
- **Frames** convert with 3DView rotation matrices (`get_transform_matrices`,
  https://3dview.irap.omp.eu/pages/restServices.html).
  It knows 106 frames, including GSE, GSM, SM, MSO, KSM and JSM.
  It returns one 3x3 float32 matrix per time step.
- Matrices are interpolated to the needed times with quaternion SLERP (`scipy.spatial.transform.Slerp`).
  Linear interpolation of matrix elements does not give a rotation.
- One SciQLop function hides where matrices come from:

  ```python
  def rotation(from_frame: str, to_frame: str, times: np.ndarray) -> scipy.spatial.transform.Rotation
  ```

  It returns identity when the frames are equal and makes no network call in that case.
  Until speasy wraps the endpoint ([speasy#406](https://github.com/SciQLop/speasy/issues/406)),
  it calls the REST endpoint itself, marked `simplify:` with "switch to speasy once #406 is released".
- A missing transform (unknown frame, 3DView down) raises with the two frame names.
  It never falls back to identity.

## 2. Boundaries

### Contract

```python
class Boundary(Protocol):
    name: str              # registry key, e.g. "shue1998"
    body: str              # body name, e.g. "earth"
    kind: str              # "magnetopause", "bow_shock", "mpb", ... (free string)
    frame: str             # frame the model computes in
    description: str
    reference: str         # paper citation or DOI

    def sample_times(self, start: float, stop: float) -> np.ndarray: ...
    def cross_section(self, planes: Planes, times: np.ndarray) -> np.ndarray: ...   # (n, m, 3)
    # optional:
    def surface(self, times: np.ndarray) -> Mesh: ...
```

- The scene asks the model which times to sample in `[start, stop]`, then asks for one section per time.
- `Planes` = one unit normal and offset **per time**, (n, 3) and (n,), in the **model's** frame and body radii.
  The scene's plane is fixed in the scene frame. When the frames differ, it maps to a different plane
  in the model frame at each time (GSE→GSM rotates during the day), so the scene rotates it per time.
- The result is one section per time, in the model frame and body radii.
  It may contain NaN where a section is cut, for example an open tail.
- How a model's parameters are driven (constants, solar-wind data, a simulation) is its own business.
- A model computes, the scene summarises. Models never compute statistics.

### RadialBoundary

Most planetary boundaries are star-shaped around a point: r = r(θ, φ, t).
A base class gives those models everything from one method:

```python
class RadialBoundary(Boundary):
    origin: tuple[float, float, float] = (0, 0, 0)   # focus of conic models (Mars, Mercury)
    theta_max: float                                  # tail clip; r grows without bound past it
    cadence: Optional[float] = None                   # seconds; None = fixed sample count

    def radius(self, theta, phi, times) -> np.ndarray: ...   # the only method a model writes

    # provided:
    def sample_times(self, start, stop): ...   # cadence or fixed count
    def cross_section(self, planes, times): ...   # per time: sweep in-plane directions from origin, r(dir) * dir
    def surface(self, times): ...                # θ, φ grid → mesh
```

- `radius` is vectorised over time: shape (n_times, n_directions).
- Sample times: every `cadence` seconds, or a fixed 200 samples over the interval when `cadence` is None.
- Sections from `radius` are exact. Each point lies on the true boundary; nothing is a mesh slice.
- A non-radial model implements `cross_section` itself. If it implements only `surface`, the framework slices the mesh.

## 3. Interval summary

A scene follows its panel's time range, so a boundary is drawn as a summary over the interval.

1. `times = model.sample_times(start, stop)`; rotate the scene plane into the model frame at each time;
   `model.cross_section(planes, times)`.
2. Rotate each section back into the scene frame, using that time's matrix.
3. Express each point as (in-plane angle, radius) around the boundary origin, in the scene plane.
4. Per angle, reduce over time: `median` or `mean` for the curve, `min` and `max` for the envelope.

The reduction happens in the scene frame, after the per-time rotation. Reducing in the model frame
would blur the frame's own swing (GSE→GSM tilts up to ±35° a day) into the boundary's motion.

Display options per boundary in a scene: `summary="median" | "mean"`, `envelope: bool`.
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
    name: str                               # "Earth environment"
    body: str                               # body name
    frame: str                              # "GSM"
    boundaries: Mapping[str, str | Boundary]   # kind → model name (or an object, for notebooks)
    summary: Literal["median", "mean"] = "median"
    envelope: bool = True
    section_offset: Literal["origin", "spacecraft"] = "origin"

    def with_boundary(self, kind: str, model: str | Boundary) -> "Scene": ...
```

- A scene is data. Variants are `dataclasses.replace(...)` or `with_boundary(...)`.
- The scene unit is the body radius.
- `section_offset`: `"origin"` cuts each pane through the body centre (z=0 for XY, x=0 for YZ, y=0 for ZX).
  `"spacecraft"` cuts through the first trajectory's mean position over the interval.
- Models whose `body` differs from the scene's are refused.

### Plotting

```python
proj = panel.plot_scene("Earth environment")   # name or Scene
proj.add_trajectory("MMS1")                    # 3DView body name
proj.add_trajectory("speasy//cda//MMS//MMS1//MEC//...//mms1_mec_r_gsm")   # any position product
```

`plot_scene` returns a `ScenePlot` wrapping the three-pane projection plot. Each pane gets:

- the body disk,
- each boundary's summary curve and envelope for that pane's plane,
  recomputed when the panel time range changes.

Boundaries are drawn **per pane**: each pane has its own plane, unlike the orbit,
which is one 3D curve projected on every pane. So `add_model_curve` (one 3D curve for all panes) does not fit.

`add_trajectory`:
- A 3DView body name is fetched with `get_trajectory` directly in the scene frame.
- Any other product is converted to the scene frame and unit using its `COORDINATE_SYSTEM` and unit metadata.
  It is refused when either is missing.
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
- A duplicate name raises, naming the first registrant.
  Registering the same name again **from the same module** replaces the entry, so `%install` hot-reloads work.
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
- Tooltips show `description` and `reference`. Smart search indexes them.

| Drop | onto | result |
|---|---|---|
| scene | panel | new scene plot |
| model | scene plot, same body | adds that kind, or swaps the current one |
| model | anything else | refused, with a message |
| position product | scene plot | `add_trajectory` (converted, not plotted raw) |

`ProductDnDCallback.call` (`time_sync_panel.py`) dispatches on a node metadata key `sciqlop_kind`
(`layer`, `scene`, `boundary`) through one dict of handlers. Layers move onto it.
Nodes without the key keep today's `plot_product`.

## 7. Built-in content

A built-in plugin, `SciQLop/plugins/planetary_scenes/`, using only the public API above:

- Bodies: Earth, Mars, Mercury.
- Earth: Shue 1998 magnetopause, Jelinek 2012 bow shock; scene "Earth environment" in GSM.
- Mars: Vignes 2000 bow shock and MPB (conics, `origin` at the focus); scene in MSO.
- Mercury: Winslow 2013 magnetopause and bow shock; scene in MSO.

Models start with fixed parameters (the papers' nominal values).
Solar-wind-driven variants are later registrations, not API changes.

Models are written from the papers, cited in `reference`.
LPP `space` (GPLv3, like SciQLop) has the same formulas; tests compare against values computed with it.

## 8. Code layout

- `SciQLop/components/scenes/` — frames (`rotation`), boundary base classes, summary, registries, scene plot.
- `SciQLop/user_api/scenes/` — public surface: `Body`, `Scene`, `Boundary`, `RadialBoundary`, `Plane`,
  `register_*`, `list_*`. `plot_scene` on `PlotPanel`. `@on_main_thread` where Qt is touched.
- `SciQLop/plugins/planetary_scenes/` — built-in content.

## 9. Testing

- Frames: `rotation` with recorded 3DView JSON (no network in tests); identity short-cut; SLERP stays orthonormal;
  unknown frame raises.
- `RadialBoundary.cross_section`: a sphere model gives circles in every plane; a conic gives the focus-centred section;
  a different plane per time gives a different section per time.
- Summary: two synthetic sections at known radii → median, mean, min and max per angle; rotation applied before reduction.
- Models: Shue 1998, Jelinek 2012, Vignes 2000, Winslow 2013 against reference values.
- Registry: duplicates raise; same-module re-register replaces; late resolution; missing-name error lists names.
- Scene plot: three panes get their own sections; a time range change recomputes; axis labels;
  a model for another body is refused.
- `add_trajectory`: km/GSE product lands in R_E/GSM; product without frame metadata is refused.
- Drag and drop: dispatch table routes layer, scene, boundary and plain products.
- The MMS shot rewritten with `plot_scene` as an end-to-end test (recorded data).

## Checks during planning

- Whether a per-pane callable curve on a projection subplot follows the panel time range, as `add_model_curve` does.
  If not, the scene plot connects the range signal itself.
- Whether projection panes can fill between two curves. If not, the envelope starts as two thin dashed lines.
- 3DView body names for Mars and Mercury, and whether MSO is the right frame name for each.
