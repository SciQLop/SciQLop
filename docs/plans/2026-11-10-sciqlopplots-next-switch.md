# Switching SciQLop to the next SciQLopPlots release

The next SciQLopPlots release is `main` plus PR #146 (API review + fuzzing campaign), 440 commits after 0.52.0.
SciQLop's suite was run against it on 2026-11-10 (PR head, build and CI wheel) in a separate environment.

## Already done on SciQLop main (works with 0.52.0 and with the next release)

- `name` is a method in the next release (a property in 0.52): SciQLop reads and sets names with
  `objectName()` / `setObjectName()`, which both versions share. `graph_name()` handles either form.
- `plots()` returns plots, not `...Ptr` handles: the comparison module uses `ordered_panel_plots()`.
- `spans()` returns spans, but `delete_span` still only takes a Ptr or an id: catalog overlays delete by id.
- Colour maps and 2-D histograms only have `metadata()` / `set_metadata()`: graph contexts go through
  `_read_slot` / `_write_slot` in `core/graph_context.py`.
- `set_log(True)` on a time axis raises: `set_axis_type` clears the time axis first.
- `TimeRange.datetime_start()` is UTC-aware: the time bar builds its date from epoch seconds.
- Timeline settings are methods taking enums: `user_api/plot/_timeline.py` maps its strings to the enums
  (`_STYLES`, `_STACKS`, `_EDIT_MODES`) and reads/writes through `_read` / `_write`.
- Tests read names with `objectName()`, and accept the new ownership (parented widgets and plot-scoped
  lines are C++-owned).

## On the day of the switch (needs the new release; not possible before)

1. Pins in `pyproject.toml`: `SciQLopPlots==<new>`, `pyside6==6.12.0` (and shiboken6),
   `PySide6-QtAds==5.1.1.1` (built for 6.12.0). `jupyqt` and `tscat-gui` accept any PySide6.
   Check the installers' bundled PySide and `[tool.sciqlop.launcher]` (a new PySide may need `minimum` raised).
2. Deprecated calls (they still work, with a warning):
   - `remove_plottable(x)` -> `plot.remove(x)`: `user_api/plot/_plots.py`, `scenes/scene_plot.py` (2),
     `comparison/ui/ghost_watch.py`.
   - `save_png/save_jpg/save_bmp/save_pdf` -> `save(path, ...)`: `plotting/export.py`,
     `user_api/screenshot`, `agents/tools/_builder.py`.
   - Item constructors -> plot/panel factories (`plot.vertical_span(...)`, `plot.text(...)`, ...):
     `user_api/plot/_graphic_primitives.py` (7), `user_api/layers/_renderer.py`, `knob_inspector/plot_items.py`.
   - Timeline: pass the enums directly; `_read` / `_write` and the string tables can then shrink to the
     string <-> enum mapping the public API still needs.
3. Remove the compatibility code that only served 0.52: the three `.data()` unwrap helpers
   (`scene_plot.concrete_plot`, `panel_introspection._concrete`, `_plots._concrete_impl`), the callable
   check in `graph_name()`, `_read_slot` / `_write_slot`'s `meta_data` fallback.
4. Workarounds the release lets go (see memory design-scenes-and-models):
   - scene `_hold_extent` (`m_axes_to_rescale` hack) -> `plot.set_fit_first_data(False)`;
   - scene legend's 7 rows -> `SciQLopPlotGroup` / `set_in_legend` (the item parked "until plot groups ship").
   Still waiting: a placeholder flag (the scene tree's "empty plot = drop placeholder" heuristic).
5. Run the full suite, then the plugins that use SciQLopPlots (cdf_workbench, sciqlop_msa, sciqlop_radio,
   sciqlop_sismo) against it.

## Gaps found in PR #146 (to report to SciQLopPlots)

- `delete_span` doesn't accept the objects `spans()` now returns.
- The `meta_data` alias exists on line graphs and curves only, not on colour maps, 2-D histograms or the
  plottable interface.
