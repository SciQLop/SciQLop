# Handover — runtime tracing + graph-context metadata

**Branch:** `main`
**Last commit:** `1d7a971e feat(graph-context): two snippet variants + live time range + inspector tooltips`
**Tests:** `1178 passed, 1 skipped, 1 xfailed` (`uv run pytest tests/ --ignore=tests/fuzzing -q`)

## What was shipped this session

19 commits on top of `afc7070e` (the SciQLopPlots 0.21 → 0.23 bump),
grouped logically:

### Docs (2 commits)
- `d753e9ff` `docs(plans): graph context metadata design`
  → `docs/plans/2026-05-05-graph-context-metadata.md`
- `6d7dbc8e` `docs(plans): graph context metadata implementation plan (P1+P2)`
  → `docs/plans/2026-05-05-graph-context-metadata-plan.md`
  *(plan title says P1+P2 but P3+P4 also landed — see "Phasing" below)*

### Graph context (12 commits, P1+P2+P3+P4)
- `6750d430` schema (`GraphContext`, `GraphRichRefs`)
- `3d5d3b69` `_is_importable` helper
- `05282520` storage helpers (`attach_context`, `context_of`, `rich_of`,
  `provider_for`)
- `61672e0e` builders (`build_speasy_ctx`, `build_vp_ctx`,
  `build_function_ctx`, `build_static_ctx`)
- `81b0a5c3` `_attach_graph_context` wired into `_post_plot`
- `b93f7e31` `attach_context` wired into `plot_static_data`,
  `plot_function`
- `1cb04d50` `update_knobs` slot
- `2b59175b` `DataProvider.python_snippet` + `extended_metadata` defaults
- `8e35789c` SpeasyPlugin overrides (initial single-variant snippet)
- `a62c3c7b` EasyProvider three-tier snippet + `extended_metadata`
- `e354e097` `add_graph_context_actions` menu helper
- `1ef21630` wired into `TimeSyncPanel._show_context_menu`
- `9a724e78` `feat(graph-context): hover tooltip and inspector extension (P3+P4)`
- `1d7a971e` `feat(graph-context): two snippet variants + live time range + inspector tooltips`

### Tracing / profiling (3 commits)
- `44efea01` `SciQLop/core/tracing.py` shim + `user_api/tracing.py`
  re-export + `sciqlop_app.py` `set_thread_name("Qt-Main")` hook
- `02ec9aa4` zones in `user_api/plot/_panel.py` (PlotPanel.time_range
  setter loop + `@traced` on plot_*) and `user_api/plot/_graphs.py`
  (set_data wrappers split conversion vs impl)
- `baf32083` `Tools › Profiling` submenu (`SciQLop/components/profiling/`)
  with start/stop trace + Perfetto launcher (postMessage flow, NOT URL+localhost — that doesn't work)

Zones in `data_provider.py` / `easy_provider.py` / `speasy_provider.py`
were rolled into the graph-context commits when those files were
co-modified (functionally complete, just not in their own commits —
intentional artifact of the squash-recovery flow).

## Architecture cheat-sheet

```
GraphContext (Pydantic)        graph.meta_data slot (C++ QVariantMap)
+ GraphRichRefs (callable, knobs_model class) in _RICH dict
                ↑
             attach_context(graph, ctx, rich)
                ↑
        _attach_graph_context (provider-aware) /
        plot_static_data / plot_function
                ↓
        _install_graph_context_ui:
          - plot.setToolTip(graph_tooltip(graph)) + data_changed refresh
          - graph.add_inspector_extension(GraphContextExtension)
        Right-click: add_graph_context_actions(menu, _all_graphs(panel))
                ↓
        DataProvider:
          python_snippets(ctx, graph=None) -> dict[label, snippet]
          extended_metadata(ctx) -> dict
```

Speasy graphs ship two snippet variants:
- *Reproduce in SciQLop*: `panel.plot_product(<path>, ...)`
- *Notebook (matplotlib)*: `import speasy as spz; v.plot(ax=ax)`

VPs ship one variant (*Reproduce in SciQLop*) — three-tier behavior
inside (importable callback → real `from x import y`; lambda/closure →
comment stub; else nothing). Both variants read the live panel
time range via `graph_time_range(graph)` (i.e., `graph.parent().time_axis().range()`).

## What's NOT shipped / known gaps

- **Tooltip refresh on knob change** is wired through
  `state.knobs_changed → update_knobs(graph, values)` (which updates
  the envelope), but the plot's `setToolTip` only refreshes on
  `graph.data_changed`, not on knob change directly. The envelope is
  current; the displayed tooltip will lag knob edits until the next
  fetch. Easy fix if needed: extend `_install_graph_context_ui` to
  hook `graph._knob_state.knobs_changed` → tooltip refresh.
- **`GraphContext.last_range` is not stored** — snippets read live
  range from the plot at call time. Time range mutation is fast; no
  caching needed. Inspector "Last fetch" line uses `graph.data()` shape.
- **Tooltip for ColorMap is heuristic-only** — `_last_fetch_line` shows
  "N points · dtype" via the first array. Color maps have a different
  data shape; the heuristic just omits the line. Polish task in
  follow-up.
- **`_show_context_menu` integration test** — not behavioral. Source-
  inspection only (see `pitfall-shiboken-exec-vtable.md`). Behavioral
  coverage of the menu helper + `_all_graphs` is via separate tests.
- **`update_knobs` wired in `_attach_knob_state`** — it fires on knob
  edits but the live time-range and last-fetch fields are derived on
  read, not stored. By design.

## Things to watch / pre-flight checks

- The tracing shim falls back to no-ops when `SciQLopPlots.tracing` is
  absent (current 0.23.0 release ships only the raw `tracing_*` C
  functions). Once the upstream Python submodule lands in a release,
  `from SciQLopPlots import tracing` succeeds and the shim transparently
  picks it up — no code change needed on our side.
- For the right-click menu / Perfetto launcher, see the relevant
  memories — `pitfall-shiboken-exec-vtable.md` and
  `profiling-perfetto-postmessage.md` capture non-obvious gotchas.

## To pick up next

The original spec mentions a few items that aren't on a plan yet:

- ColorMap-aware tooltip line.
- Wire tooltip refresh on `knobs_changed` (not just `data_changed`).
- Refactor `_last_fetch_line` heuristic into something `graph_type`-aware.
- `Open last trace in Perfetto` could pre-fill the file dialog with a
  default `~/.sciqlop/traces/` location instead of `~`.

None of these are blockers — file when convenient.
