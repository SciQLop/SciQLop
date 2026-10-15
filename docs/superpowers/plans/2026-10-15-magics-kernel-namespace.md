# Magics and kernel namespace (plan 2c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugins contribute IPython magics (with their tab completers) and names in the kernel's user namespace through extension points; withdrawing a plugin takes them back out.

**Architecture:** Two extension points on plan 1a's `ExtensionPoint`:
- `sciqlop.magics` holds `Magic` records: a magic name, its kind (`line`, `cell` or `line_cell`), the function, and an optional Matcher-v2 completer. The seven core magics (`%%vp`, `%%layer`, `%plot`, `%timerange`, `%install`, `%workspace`, `%job`) become core contributions owned by `"sciqlop"`. `register_all_magics(shell)` keeps its name and becomes the follower: it applies every contribution to the shell and follows `added`/`removed`.
- `sciqlop.kernel_namespace` holds `NamespaceEntry` records: a name and a value. The core names SciQLop pushes today (`main_window`, `workspace`, `app`, `background_run`, `plugins`) become core contributions at the moments they are pushed today. One follower applies entries to the shell's user namespace and follows `added`/`removed`.

The embedded shell exists from `KernelManager.__init__` on, before plugins activate, and lives for the whole process (a restart is a process restart). So both followers apply contributions immediately; no "kernel started" replay is needed. This corrects the spec's §4.3 note ("the shell does not exist at activation"), which Task 3 rewords.

**Tech Stack:** Python 3.10+, IPython (`InteractiveShell.register_magic_function`, `magics_manager.magics`, `Completer.custom_matchers`, `user_ns`), jupyqt `EmbeddedJupyter`, pytest + pytest-qt (+ pytest-xvfb).

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` — §4.3 tier-2 row `sciqlop.magics`, `sciqlop.kernel_namespace` ("fixed magics list, ad-hoc `push_variables`"), §6 (consumers listen to `removed`), §7 (migration rules). Plans 1a–2b are implemented and pushed.

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- Run one pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`, with Bash `timeout: 600000`. Never `--no-xvfb`. Never `uv sync`. Never edit SciQLopPlots, speasy or jupyqt.
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls`.
- SciQLop loggers bypass pytest's `caplog`; tests that check a log call monkeypatch the module's `log.warning`/`log.error`.
- Ids: core ids are `sciqlop.<name>`; plugins use `<plugin id>.<name>`. Core contributions are owned by `"sciqlop"` and pass it explicitly. Extension points are main-thread objects.
- Published API keeps working (spec §7): `register_all_magics(shell)` (listed in `tests/test_user_api_thread_classification.py`), every magic's behaviour and completions, `KernelManager.push_variables`, `WorkspaceManager.push_variables`, `SciQLopMainWindow.push_variables_to_console` (documented for plugins; stays a direct, un-owned push). The kernel names `main_window`, `workspace`, `app`, `background_run`, `plugins` keep their values and stay available at the same moments as today.
- Name clashes: the first contribution of a magic name (per kind) or of a namespace name is applied; a later one from another contribution is logged with `log.error` naming both ids and is not applied. When the applied one is withdrawn, the next remaining contribution with that name (in contribution order) is applied. Core contributions register first, so a plugin cannot shadow `%plot` or `main_window`.
- Withdrawal never clobbers the user: a namespace name is removed from `user_ns` only if it still holds the contributed value (`is`), so a user's own `x = ...` survives a plugin's withdrawal. A magic is removed only if the shell's registered function is still the contributed one.
- Plugin-author docs move with the code (spec §7): `SciQLop/components/agents/skills/sciqlop-plugin-design/` changes in the same commit as the code it documents. `references/plugin-contract.md` lists the EPs; add a "Kernel: magics and namespace" section to `references/ui-and-settings.md`.
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **A plugin registers `%plot`** (a core magic name). Core `%plot` keeps working; the plugin's is logged and ignored. → Task 1.
2. **A user rebinds a name a plugin contributed** (`mydata = 3` over the plugin's `mydata`), then the plugin is withdrawn. The user's value stays. → Task 2.
3. **A plugin is live-installed while a notebook runs.** Its magic and names are usable in the next cell without a restart; tab completion offers its completer. → Tasks 1, 2.
4. **A plugin's magic raises.** The cell shows the traceback like any magic error; the kernel keeps running. (IPython already does this; a test pins it.) → Task 1.
5. **Every core magic and completer works exactly as before**, including when `register_all_magics` is called twice on one shell (no duplicate completers). → Task 1.

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/core/magics.py` | `Magic`, `MAGICS` EP | 1 |
| `SciQLop/user_api/magics/__init__.py` | core magic contributions; `register_all_magics(shell)` = follower | 1 |
| `SciQLop/core/kernel_namespace.py` | `NamespaceEntry`, `KERNEL_NAMESPACE` EP | 2 |
| `SciQLop/components/jupyter/kernel/namespace.py` | namespace follower `follow_kernel_namespace(shell)` | 2 |
| `SciQLop/components/jupyter/kernel/manager.py` | `KernelManager.__init__` wires both followers | 1, 2 |
| `mainwindow.py`, `workspaces_manager.py`, `sciqlop_app.py`, `tests/fixtures.py` | core pushes become contributions | 2 |
| `SciQLop/components/extension_points.py` | declares both EPs | 1, 2 |
| `tests/test_magic_contributions.py`, `tests/test_kernel_namespace.py`, `tests/test_plugin_interop.py` | tests | 1–3 |
| skill docs, spec §4.3 | docs | 1–3 |

---

### Task 1: `sciqlop.magics`

**Files:**
- Create: `SciQLop/core/magics.py`
- Modify: `SciQLop/user_api/magics/__init__.py`
- Modify: `SciQLop/components/extension_points.py` (`prepare_extension_points`: `import SciQLop.core.magics  # noqa: F401  declares sciqlop.magics`)
- Test: `tests/test_magic_contributions.py` (new); `tests/test_magics/`, `tests/test_layers/test_magic.py`, `tests/test_vp_magic*.py` must pass unchanged.
- Docs: `references/ui-and-settings.md` ("Kernel: magics and namespace", magics half), `references/plugin-contract.md` EP list.

**Interfaces:**
- Produces:
  - `Magic(id: str, name: str, kind: str, function: Callable, completer: Optional[Callable] = None)`; `kind` in `LINE, CELL, LINE_CELL = "line", "cell", "line_cell"`, anything else raises `ValueError` in `__post_init__`; `name` must be a valid identifier without `%` (`ValueError` otherwise).
  - `MAGICS` (id `sciqlop.magics`).
  - `CORE_MAGICS`: tuple of the seven core `Magic`s, ids `sciqlop.<name>` (`sciqlop.vp`, `sciqlop.layer`, `sciqlop.plot`, `sciqlop.timerange`, `sciqlop.install`, `sciqlop.workspace`, `sciqlop.job`), each carrying the completer it uses today (`_match_vp` with vp, `_match_plot` with plot, `_match_timerange` with timerange, `_match_workspace` with workspace, `_match_job` with job; layer and install have none). Contributed with `owner="sciqlop"`, idempotently (skip ids already present), the first time `register_all_magics` runs or when `prepare_extension_points` runs, whichever is first — put the contribution in one module-level function `contribute_core_magics()` both call.
  - `register_all_magics(shell) -> None`: contributes the core magics if needed, applies every `MAGICS` contribution to `shell`, and follows `MAGICS.signals.added/removed` for that shell. Idempotent per shell (a second call neither re-follows nor appends completers twice).

Behaviour:
- Apply = `shell.register_magic_function(function, magic_kind=kind, magic_name=name)`, and append `completer` to `shell.Completer.custom_matchers` if it is not already there.
- Clash: a name already applied (for the same kind; `line_cell` clashes with both) by another contribution → `log.error(f"magic %{name} from {new_id} ignored: already provided by {holder_id}")`, not applied. Track which contribution holds each (kind, name) in a dict keyed per shell; keep that dict in a module-level `weakref.WeakKeyDictionary` keyed by shell if the shell is weak-referenceable, else a plain dict keyed by `id(shell)` — check, and say which in the report.
- Withdraw (on `removed`): if the shell's registered function for (kind, name) is still the contributed one, delete it from `shell.magics_manager.magics[kind]` (both kinds for `line_cell`); remove the completer from `custom_matchers` if present; then apply the next remaining contribution with that name (contribution order = `MAGICS.list()` order).
- The follower connects module-level functions (Qt lifetime rule), with the shell captured in a `functools.partial` or closure; the per-shell idempotence flag lives in the same per-shell state.

- [ ] **Step 1: Write the failing tests** in `tests/test_magic_contributions.py`. Use a real shell: create one with `IPython.core.interactiveshell.InteractiveShell()` if that works without clobbering the app's singleton (check; otherwise use the `main_window` fixture's kernel shell via `workspaces_manager_instance()._kernel_manager.shell` and clean up). Contribute under `owned_by("mg_demo")`, `MAGICS.remove_owner("mg_demo")` in teardown. Tests:
  - `test_core_magics_are_contributions`: every name in (`vp`, `layer`, `plot`, `timerange`, `install`, `workspace`, `job`) has a `sciqlop.<name>` contribution owned by `"sciqlop"`, and after `register_all_magics(shell)` each is in `shell.magics_manager.magics[<kind>]`.
  - `test_a_plugin_line_magic_runs`: contribute `Magic("mg_demo.hello", "hello", "line", lambda line: f"hi {line}")`; `shell.run_line_magic("hello", "you") == "hi you"`.
  - `test_a_magic_contributed_before_the_shell_is_replayed`: contribute first, then `register_all_magics(fresh_shell)`; the magic is there.
  - `test_withdrawal_removes_the_magic_and_its_completer`.
  - `test_a_plugin_cannot_shadow_a_core_magic`: contribute `Magic("mg_demo.plot", "plot", "line", ...)`; `shell.magics_manager.magics["line"]["plot"]` is still the core function; `log.error` was called once naming `mg_demo.plot`.
  - `test_withdrawing_the_holder_promotes_the_next`: two plugin contributions of `%zz` (owners `mg_demo` and `mg_demo2`); withdraw the first; the second's function is now registered.
  - `test_register_all_magics_twice_adds_no_duplicate_completers`.
  - `test_a_raising_magic_reports_and_the_shell_lives`: `shell.run_cell("%boom")` result has `error_in_exec` set; a following `shell.run_cell("1+1")` succeeds.
  - `test_kind_and_name_are_validated`.
- [ ] **Step 2: Run them; they fail** (missing module).
- [ ] **Step 3: Implement** `core/magics.py`, the `user_api/magics/__init__.py` rewrite, the startup import.
- [ ] **Step 4: Run** `tests/test_magic_contributions.py tests/test_magics tests/test_layers/test_magic.py tests/test_user_api_thread_classification.py tests/test_kernel_manager.py` plus the `tests/test_vp_magic*.py` files (one invocation); all pass.
- [ ] **Step 5: Commit** `feat(plugins): IPython magics are contributions to sciqlop.magics; register_all_magics follows them`.

---

### Task 2: `sciqlop.kernel_namespace`

**Files:**
- Create: `SciQLop/core/kernel_namespace.py`, `SciQLop/components/jupyter/kernel/namespace.py`
- Modify: `SciQLop/components/jupyter/kernel/manager.py` (`KernelManager.__init__`: call `follow_kernel_namespace(self._jupyter.shell)` after `register_all_magics`)
- Modify the five core pushes so they contribute instead (same values, same moments):
  - `SciQLop/core/ui/mainwindow.py` ~424: `main_window` → `NamespaceEntry("sciqlop.main_window", "main_window", wm.wrap_qt(self))`
  - `SciQLop/components/workspaces/backend/workspaces_manager.py` ~206: `workspace` → `sciqlop.workspace`
  - same file ~258 (`start`): `app`, `background_run` → `sciqlop.app`, `sciqlop.background_run`
  - `SciQLop/sciqlop_app.py` ~209 and `tests/fixtures.py` ~44: `plugins` → `sciqlop.plugins` (the fixture contributes `loaded_plugins` as today; use `replace=True` so repeated fixture setups in one process don't raise on the duplicate id)
- Modify: `SciQLop/components/extension_points.py` (declare)
- Test: `tests/test_kernel_namespace.py` (new); `tests/test_kernel_manager.py`, `tests/test_jupyterlab_on_demand.py` must pass.
- Docs: the namespace half of the "Kernel: magics and namespace" section; EP list.

**Interfaces:**
- Produces:
  - `NamespaceEntry(id: str, name: str, value: Any)`; `name` must be a valid identifier (`ValueError`).
  - `KERNEL_NAMESPACE` (id `sciqlop.kernel_namespace`).
  - `contribute_name(id: str, name: str, value, *, owner: str = "sciqlop", replace: bool = False)` helper in `core/kernel_namespace.py` that the five core call sites use (keeps each call site one line).
  - `follow_kernel_namespace(shell) -> None`: applies every entry to `shell.user_ns` (via `shell.push({name: value})`, as jupyqt's `push` does — check jupyqt `EmbeddedJupyter.push` and use the same call so behaviour matches) and follows `added`/`removed`. Idempotent per shell.
  - Clash, promote-next and withdraw-only-if-unchanged rules exactly as in Global Constraints. `replace=True` re-contribution of the same id with a new value (the fixture case, or a future workspace switch) re-pushes the new value; check what `ExtensionPoint` emits on replace (`removed` then `added`, or only `added`) in `core/extensions.py` and handle it.

Ordering note: `KernelManager.__init__` runs inside `SciQLopMainWindow.__init__`, before `prepare_extension_points()`. Importing `SciQLop.core.kernel_namespace` declares the EP, so the follower can import it directly; declaring is idempotent.

- [ ] **Step 1: Write the failing tests** in `tests/test_kernel_namespace.py` (same shell strategy as Task 1; `owned_by("kn_demo")`, teardown `remove_owner`):
  - `test_a_contributed_name_is_in_the_namespace`
  - `test_a_name_contributed_before_the_shell_is_replayed`
  - `test_withdrawal_removes_the_name`
  - `test_withdrawal_keeps_a_user_rebinding`: contribute `mydata`; `shell.user_ns["mydata"] = 3`; withdraw; `shell.user_ns["mydata"] == 3`.
  - `test_a_plugin_cannot_shadow_a_core_name`: contribute `main_window`; the namespace still holds the core value; `log.error` called naming the plugin id.
  - `test_withdrawing_the_holder_promotes_the_next`
  - `test_replace_repushes_the_new_value`
  - `test_core_names_are_contributions` (with the `main_window` fixture): `main_window`, `workspace`, `plugins` are contributions owned by `"sciqlop"` and present in the kernel shell's `user_ns`. (`app`/`background_run` only after `WorkspaceManager.start()`; assert them only if the fixture starts it — check.)
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement** the EP, follower, the five call-site migrations and the wiring.
- [ ] **Step 4: Run** `tests/test_kernel_namespace.py tests/test_kernel_manager.py tests/test_jupyterlab_on_demand.py tests/test_magic_contributions.py` (one invocation); all pass.
- [ ] **Step 5: Commit** `feat(plugins): kernel names are contributions to sciqlop.kernel_namespace; core names migrate`.

---

### Task 3: Interop proof and spec bookkeeping

**Files:**
- Modify: `tests/test_plugin_interop.py` (extend the plan 2b interop pattern: a plugin folder written to `tmp_path`, loaded through the loader, withdrawn through the loader's `_withdraw`)
- Modify: spec §4.3 table row and wording

- [ ] **Step 1: Interop test.** The test plugin's `activate(ctx)` contributes `Magic("<id>.shout", "shout", "line", lambda line: line.upper())` and `NamespaceEntry("<id>.api", "<id>_api", some_object)`. Against the app's kernel shell: `run_line_magic("shout", "hi") == "HI"`, `user_ns["<id>_api"] is some_object`; after `_withdraw`, both are gone.
- [ ] **Step 2: Run** the interop file; it passes.
- [ ] **Step 3: Spec.** In §4.3, the `sciqlop.magics`, `sciqlop.kernel_namespace` row: replace "these EPs replay their contributions when a kernel starts (the shell does not exist at activation)" with "the embedded shell exists before plugins activate and lives for the process, so contributions apply immediately; **implemented**: docs/superpowers/plans/2026-10-15-magics-kernel-namespace.md".
- [ ] **Step 4: Commit** `test(plugins): interop proof for magics and kernel names; spec row marked implemented`.
