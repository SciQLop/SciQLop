# RESOLVED 2026-09-20 (afternoon)

Full run, single process, `--ignore=tests/fuzzing`: **3043 passed, 17 skipped, 1 xfailed, 0 failed,
exit 0, 4 min, 4.3GB peak.** Everything below in sections 4-5 is history; what was found:

| symptom | root cause | fix |
|---|---|---|
| 6 command-palette failures/errors, `mainwindow_close` | tests dirtied the main window's shared "My Catalogs" provider; every later `mw.close()` hit the unsaved-catalogs dialog | `_isolate_catalog_registry` also resets dirty state (`_forget_dirty_state`) |
| `test_agent_and_provider_icons` | `asyncio.run()` in other tests leaves no current loop (Py3.14) | autouse `_current_event_loop_is_sciqlops` |
| `swatch_double_click` | shared window's providers push the row ~5600px below the viewport, dbl-click lost | test scrolls to the row |
| `onboarding_wiring` shortcut, tour_controller | prod bug: `workspace_loaded` connected to a lambda over `self` (fires after window deleted); throwaway windows overwrote `qapp` quickstart shortcuts | bound method `_show_workspace_name_in_title`; conftest snapshots `_quickstart_shortcuts` |
| `vp_debug_layout` | `test_panel_area_add_button` left an empty bottom dock area (`closeDockWidget`), flipping root splitter orientation | `removeDockWidget` |
| `export_md` (3) | real regression: `_input_one_line` moved to `render_model.input_one_line`, Export button raised ImportError | import fixed |
| smart-search (5) | fixed 10 `processEvents()` pumps not enough once the real inventory is loaded | `qtbot.waitUntil` polling |
| speasy knobs (3) | stale fakes (`spz_provider`), `coordinate_system` now goes to `product_inputs` on non-SSC | tests updated to the documented contract |
| `web_channel_page` | test needs a real WebEngineView, hook disables it (Chromium segfaults headless) | skipif under the hook |
| `onboarding_wiring` skip test | 500ms tour timer armed by an earlier test | test waits 600ms first |
| exit 134 after green run | `tscat_gui` starts a QThread at import; its `stop()` calls `quit()` without waiting | conftest stops it at `pytest_sessionfinish` |

Not fixed (upstream, worth an issue on tscat_gui): `TscatDriver.stop()` never waits after `quit()`;
the real app may hit the same abort on exit.

# Handover: test-suite stability (memory, speed, and the remaining failing tests)

Date: 2026-09-20. Goal of the whole effort: **the full suite must run, in one process, without
taking the machine down.** That now works. What is left is a set of tests that fail or error
*only* in the full run, which is what to investigate next.

Nothing below is committed. `uv.lock` also carries changes that predate this work; split it
by diffing against the last commit rather than committing it blind.

## 1. Where things stand

Full run, single process, `--ignore=tests/fuzzing`, on this machine:

| | before | now |
|---|---|---|
| completes? | never (RSS >10GB by test ~1400, machine dies; segfault ~test 520) | yes |
| wall clock | (extrapolated ~20 min) | **4 min 29 s** |
| peak RSS | >10GB | **4.5GB** |
| result | - | 3019 passed, **22 failed, 4 errors**, 16 skipped, 1 xfailed |

The run still exits 134 (abort) *after* the summary, at interpreter shutdown. Not investigated.

## 2. What was wrong, and what was changed

Memory (root causes, all fixed):
1. Test modules do `from .fixtures import *`; pytest registers each imported copy of the
   "session" `main_window` fixture as its own fixture, so ~70 modules each built a ~1GB
   `SciQLopMainWindow`. -> `tests/fixtures.py::main_window` now caches one window per process.
2. ~10 tests build throwaway `SciQLopMainWindow()` and only `close()` it (hides, never frees).
   -> autouse `_release_gui_leftovers` in `tests/conftest.py` destroys extra windows
   (`destroy_main_window`: `hide()` + `deleteLater()`, NOT `close()` - `closeEvent` pops a modal
   "unsaved catalogs" dialog that hangs headless runs), destroys standalone top-level plot
   panels, restores `app.main_window`, removes panels a test added to the shared window.
3. Every `TimeSyncPanel` built a `ProductSearchOverlay` whose `ProductsFlatFilterModel`
   re-scores the whole product tree on every `ProductsModel` mutation, so cost = live panels x
   corpus. -> `SciQLop/components/plotting/ui/product_search_overlay.py`: the proxy is now
   built lazily on first query (`_ensure_filter_model`). Also a real app improvement.

Speed: wall clock was dominated by **teardown** (69% on one batch: 100s of 145s), not slow
tests (slowest call 8s). A per-test `gc.collect()` I had added cost ~4 min; leaked windows and
proxies made everything else slow too. **Never add per-test `gc.collect()`.**

Production bugs found and fixed on the way (all "callback fires after its object died"):
- `welcome/backend.py`: app-singleton signal connected to a `lambda` closing over `self` (immortal
  receiver) -> bound method.
- `core/ui/mainwindow.py`: `QTimer.singleShot(ms, lambda: self...)` -> `singleShot(ms, self, ...)`;
  new `_schedule_dead_panel_drop` guarded with `shiboken6.isValid(self)`.
- `user_api/layers/_renderer.py::_deferred_try_bind`: guarded against a deleted plot.
- `catalogs/backend/color_palette.py::_CatalogSwatchIconEngine`: default `QIconEngine.pixmap()`
  rendered into an RGB16 buffer on the 16-bit Xvfb display (colour quantised to RGB565, e.g.
  (136,204,238) -> (140,207,239)); now builds an ARGB32 pixmap like `theming/icons.py`'s
  `_ThemeIconEngine`. The ~test-520 segfault disappeared with this (correlation, not proven).

Test-infra additions in `tests/conftest.py` (all autouse unless noted):
- RSS guard: `pytest_runtest_teardown` aborts cleanly (`pytest.exit`) above
  `SCIQLOP_TEST_MAX_RSS_MB` (default 6144). It only checks *between* tests.
- `SCIQLOP_TEST_RSS_LOG=<file>`: appends `RSS_MB nodeid widgets=N` after every test; a
  `<file>.widgets` histogram is written at session end.
- `_no_blocking_modal_dialogs`: static `QMessageBox.question/warning/information/critical` raise
  `AssertionError("unexpected blocking QMessageBox...")` instead of blocking until the timeout.
  A test that expects a dialog patches it itself and wins.
- `_is_xdist_master` guard in `pytest_configure` (controller process never builds a QApplication);
  regression test `tests/test_xdist_master_boot.py`.
- `pyproject.toml`: `pytest-timeout` added, `timeout = 120`, `timeout_method = "thread"` (the
  default `signal` method cannot interrupt a native call). `-n 2` is **opt-in** (doubles RAM;
  `-n 4` was measured unstable). Serial is now fast enough that it isn't needed.

## 3. How to run safely (read this before running anything)

This machine has been taken down by these tests several times. Always run through the guard,
which kills the whole process tree above a limit and dumps a `py-spy` stack first:

```
uv run python scripts/test_memguard.py 7000 /tmp/guard.log -- \
    uv run pytest -n0 -p no:cacheprovider -q --timeout=120 <paths>
# prints: peak=...MB killed=... exit=...   (py-spy dump goes to /tmp/guard.log.pyspy;
# needs `uv tool install py-spy` -> ~/.local/bin/py-spy)
```
- One pytest invocation at a time, foreground. Full run: add
  `--ignore=tests/fuzzing`; give it ~5 min (the Bash tool auto-backgrounds after 10).
- Per-test memory: `SCIQLOP_TEST_RSS_LOG=/some/file` (see above).
- Phase timing: `--durations=0 --durations-min=0`, then sum setup/call/teardown with awk.
- Do not use `gc.get_objects()` in diagnostics: it can itself segfault on half-dead wrappers.
- Shell traps in this environment: `cat` is aliased to `bat` (heredocs `cat > f <<EOF` HANG),
  `ls` is aliased, the shell is zsh (unquoted `$VAR` is not word-split: use arrays), `/tmp` is
  wiped between sessions. Use `command cat` / `command ls`, or the editor tools.
- Headless: pytest-xvfb starts Xvfb (16-bit screen). Do not pass `--no-xvfb` without a real
  `$DISPLAY`. If Xvfb processes leak after a crash, kill only your own orphans.

## 4. The remaining failures (this is the work to continue)

Last full run: 22 failed + 4 errors. Classification so far:

### 4a. Pre-existing (fail identically on the original code) - lower priority
- `tests/test_agent_export_md.py` (3): ImportError.
- `tests/test_product_search_overlay.py::TestProductSearchOverlaySmartSearch` (3:
  `scores_actually_surface_matches`, `scores_use_override_not_max`, `rapid_edits_while_busy...`)
  and `tests/test_sidebar_smart_search.py::TestSidebarSmartSearchWiring` (2:
  `query_changed_dispatches_and_scores_surface_a_match`, `scores_use_override_not_max`).
  Order-sensitive even before this work (2 of them pass alone, some fail alone).
- `tests/test_speasy_provider/test_knobs_argument_index.py` (3).
- `tests/test_web_channel_page.py::test_local_page_can_load_remote_images` (1).

### 4b. Fail/error in the full run but mostly pass alone - NOT yet classified vs the original
The original code cannot complete a full run (it exhausts memory), so "did I cause it?" can only
be answered per file: run the file(s) on the original code, e.g.
`git stash push -q -- SciQLop tests/conftest.py tests/fixtures.py` ... `git stash pop`
(leave `pyproject.toml`/`uv.lock` alone or `uv run` will re-sync the venv), keeping runs small.

| test | symptom |
|---|---|
| `test_command_palette_catalog_commands.py` (4 FAILED: `create_catalog_command_triggers_placeholder_edit`, `open_catalog_command_selects_the_catalog`, `..._finds_folder_nested_catalog`, `..._clears_filter_and_does_not_deselect`; 2 ERROR: `..._unknown_provider_is_a_noop`, `..._unknown_value_is_a_noop`) | worst file; passes alone |
| `test_panel_area_add_button.py` (2 ERROR: `welcome_page_area_gets_add_button_before_any_plot_panel`, `auto_hide_side_panels_never_get_add_button`) | errors in the full run |
| `test_mainwindow_close.py::test_warn_if_catalogs_dirty_ignores_clean_provider` | see lead 1 |
| `test_catalog_swatch_double_click.py::test_double_click_on_name_renames_instead` | |
| `test_onboarding_tour_controller.py::test_target_destroyed_mid_step_keeps_the_tour_going` | |
| `test_onboarding_wiring.py::test_take_a_tour_shortcut_opens_the_picker` | passes alone |
| `test_vp_debug_layout.py::test_first_debug_panel_does_not_add_horizontal_children` | |
| `test_agent_and_provider_icons.py::test_agent_ui_registered_once_centrally` | also failed in an early run made before the cleanup fixtures existed -> probably pre-existing |

### 4c. Leads (unverified hypotheses, in priority order)
1. **A catalog provider stays dirty across tests.** `SciQLopMainWindow.closeEvent` asks a
   `QMessageBox` when any registered provider `is_dirty()`. Several failing tests call
   `mw.close()` or assert on dirty providers (`test_command_palette_catalog_commands`,
   `test_mainwindow_close`), and earlier in this work a full run hung on exactly that dialog.
   With `_no_blocking_modal_dialogs` that now surfaces as `AssertionError: unexpected blocking
   QMessageBox.question: 'Unsaved catalog changes'`. Find which provider is dirty and which earlier
   test leaves it registered/dirty (`CatalogRegistry.instance().providers()` + `is_dirty()`;
   `_isolate_catalog_registry` only restores the provider *list*). Print the names in the failure.
2. **Interaction with my cleanup fixture** (`_release_gui_leftovers`): tests that build their own
   window and restore `qapp.main_window = previous` themselves may fight with it; check whether the
   failures disappear if the fixture is disabled for those files (`-p no:...` is not possible for a
   conftest fixture: temporarily gate it with an env var).
3. **Order-dependent global state** (VP registry, layer registry, plot-hint registry, settings
   singletons such as `OnboardingSettings`). For `onboarding_*` and `vp_debug_layout`.
4. Method for any of them: bisect the *prefix* - run the failing test after half of the earlier
   files (full-suite order is `tests/remote/*` first, then `tests/test_*.py` alphabetically), watch
   with `SCIQLOP_TEST_RSS_LOG`.

## 5. Other open items
- Exit code 134 at interpreter shutdown after a full run (Qt/Shiboken teardown order). Not
  investigated; possibly the same class as the old GC-teardown crashes
  (see `pitfall-full-suite-gc-teardown-crash` in the project memory).
- `test_agent_chat_dock_wiring.py` adds ~105 live widgets per test (never destroyed): its `dock`
  fixture only `close()`s the `AgentChatDock`. Not fixed; RSS impact is now small.
- `.github/workflows/tests.yml`: CI still runs plain `pytest --cov=./ ...`; with the timeout and
  RSS guard now in `pyproject.toml`/`conftest.py` it inherits both. CI was not run.
- Untracked, unrelated to this work: the many `docs/` files listed in `git status`.

## 6. Files touched (all uncommitted)
`SciQLop/components/catalogs/backend/color_palette.py`,
`SciQLop/components/plotting/ui/product_search_overlay.py`,
`SciQLop/components/welcome/backend.py`, `SciQLop/core/ui/mainwindow.py`,
`SciQLop/user_api/layers/_renderer.py`, `tests/conftest.py`, `tests/fixtures.py`,
`tests/test_xdist_master_boot.py` (new), `scripts/test_memguard.py` (new),
`pyproject.toml`, `uv.lock`, `.github/workflows/tests.yml`, this file.

## 7. Using deepseek via herdr (worked well, with caveats)
A `deepseek-v4.1-flash` opencode agent found the ProductsFlatFilterModel root cause after being
given the per-test RSS log and the guard. Notes: start it with `herdr agent start <name> --kind
opencode --pane <pane> -- --model opencode-go/deepseek-v4.1-flash [--auto]` (`--auto` =
auto-approve permissions; only with a strict brief), put the brief and data inside the repo so it
needs no outside-directory permission, tell it to follow only the brief (another agent once
hijacked a session), never let it run pytest without the guard, and verify its claims - its first
answer had a wrong numeric explanation of the pixel bug (the RGB16 cause was found by reading
`theming/icons.py`).
