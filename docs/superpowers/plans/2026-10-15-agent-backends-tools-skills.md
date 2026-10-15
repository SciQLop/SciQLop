# Agent backends, tools and skills (plan 2f) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugins contribute agent backends, agent tools and agent skills through extension points; the chat dock follows them live, and withdrawing a plugin takes them back out.

**Architecture:** Three extension points on plan 1a's `ExtensionPoint`, all in `SciQLop/components/agents/` (public out-of-tree API: never move or extract it):
- `sciqlop.agent_backends` holds `AgentBackendEntry(name, factory)`. `register_agent_backend` (both call forms) and `unregister_agent_backend` keep their signatures and become adapters; `available_backends()` and `create_backend()` read the EP. The chat dock follows `added`/`removed` instead of being told to `refresh_backends()` by each backend plugin. Today five out-of-tree plugins (sciqlop_claude, sciqlop_opencode, sciqlop_copilot, sciqlop_albert, sciqlop_kimi) register this way.
- `sciqlop.agent_tools` holds `AgentTool(name, description, input_schema, call, gated, thread)`: a plugin's tool, shaped like the core `_text_tool`. `build_sciqlop_tools(main_window)` keeps building the ~45 core tools (they need the main window) and appends every contributed tool, through the same `_text_tool` wrapper and the same crash journal. Tools are fixed per agent session (backends receive the list at session creation): a contribution applies to the next session; a withdrawn tool's handler answers "this tool was withdrawn" instead of calling into a gone plugin.
- `sciqlop.agent_skills` holds `AgentSkill(name, directory)`: a folder with a `SKILL.md` (and optional reference files). SciQLop's six bundled skills become core contributions. `sync_skills(workspace_dir)` publishes every contributed skill into `<workspace>/.claude/skills/<name>/`, and removes the skills it published earlier that are no longer contributed, without ever touching a skill folder it did not write (the user's own skills).

**Tech Stack:** Python 3.10+, PySide6, pytest + pytest-qt (+ pytest-xvfb), pytest-asyncio or the existing async test helpers used by `tests/test_agent_*`.

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` — §4.3 tier-2 row `sciqlop.agent_tools`, `sciqlop.agent_backends`, `sciqlop.agent_skills` ("fixed tool list, backend dict, package-only skills dir"), §6 (consumers listen to `removed`), §7 (migration rules), §8 (errors). Plans 1a–2e are implemented and pushed.

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- Run one pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`, with Bash `timeout: 600000`. Never `--no-xvfb`. Never `uv sync`. Never edit SciQLopPlots, speasy, jupyqt, or the out-of-tree plugins in `../plugins_sciqlop` (read them to check compatibility).
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls` (broken aliases in this shell: `cat` runs `bat`, which hangs on stdin).
- SciQLop loggers bypass pytest's `caplog`; tests that check a log call monkeypatch the module's `log.warning`/`log.error`.
- Extension points are main-thread objects; anything that may run elsewhere goes through `@on_main_thread` (`SciQLop.user_api.threading`).
- Owners: contributions inside `owned_by(<plugin>)` (plugin import, `load`, `activate`) belong to that plugin; SciQLop's own contributions are owned by `"sciqlop"`, passed explicitly (plan 2e lesson: a core module imported lazily inside a plugin's `owned_by` must not end up owned by that plugin).
- Qt lifetime (plan 2e lesson): EP signals live for the whole process, the chat dock does not. Connect bound methods and start every slot with `if not shiboken6.isValid(self): return` (this PySide6 refuses `signal.connect(context, slot)`); test teardown through `destroy_main_window` (tests/fixtures.py).
- Published API keeps working (spec §7), everything exported by `SciQLop/components/agents/__init__.py`, in particular: `register_agent_backend(factory)` (name from `factory.display_name`, `TypeError` without one) and `register_agent_backend(name, factory)`; re-registering a name replaces it silently, as today; `unregister_agent_backend(name)` is a no-op for an unknown name; `available_backends()` sorted; `create_backend(name, ctx)` raises `KeyError` for an unknown name; `ensure_agent_dock(main_window)`; `build_sciqlop_tools(main_window)` returns the same list of dicts (`name`, `description`, `input_schema`, `handler`, `gated`); `sync_skills(workspace_dir)` stays best-effort (a read-only or missing workspace never raises). The skill-name test (`tests/test_agent_skills*.py` or whatever pins published tool names) keeps passing.
- Tool names: `^[a-zA-Z0-9_-]{1,64}$` (the limit backends enforce). A contributed tool whose name is already used by a core tool or by an earlier contribution is not added: `log.error` naming both, once per (session build, name). Core tools always win.
- Plugin-author docs move with the code (spec §7): `SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md` (EP list) and a new "Agents: backends, tools, skills" section in `references/ui-and-settings.md`, in the same commit as the code they document.
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **A backend plugin is installed while the chat dock is open with a live session on another backend.** The new backend appears in the combo; the live session is not restarted or rebound. → Task 1.
2. **The backend of the live session is withdrawn.** The combo drops it; the dock does not crash; the next send either keeps working on the existing session object or shows a clear message — never a traceback. → Task 1.
3. **A plugin tool is called after its plugin was withdrawn** during a running session. The agent gets a tool error text ("withdrawn"), the kernel and GUI are untouched. → Task 2.
4. **A plugin contributes a tool named like a core tool** (`sciqlop_exec_python`). The core tool is the one the agent gets; one log names both. → Task 2.
5. **The user has their own skill folder in `.claude/skills/`**, and a plugin skill is withdrawn. The plugin's published folder goes; the user's folder is untouched. → Task 3.

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/components/agents/registry.py` | `AgentBackendEntry`, `AGENT_BACKENDS` EP, adapters | 1 |
| `SciQLop/components/agents/chat_dock.py` | dock follows `AGENT_BACKENDS` | 1 |
| `SciQLop/components/agents/tools/contributed.py` (new) | `AgentTool`, `AGENT_TOOLS` EP, conversion to tool dicts | 2 |
| `SciQLop/components/agents/tools/_builder.py` | appends contributed tools | 2 |
| `SciQLop/components/agents/skills/__init__.py` | `AgentSkill`, `AGENT_SKILLS` EP, core contributions, `sync_skills` | 3 |
| `SciQLop/components/agents/__init__.py` | exports the new names | 1–3 |
| `SciQLop/components/extension_points.py` | declares the EPs | 1–3 |
| tests, skill docs, spec §4.3 | | 1–4 |

---

### Task 1: `sciqlop.agent_backends`

**Files:**
- Modify: `SciQLop/components/agents/registry.py`, `SciQLop/components/agents/chat_dock.py`, `SciQLop/components/agents/__init__.py` (export `AgentBackendEntry`, `AGENT_BACKENDS`), `SciQLop/components/extension_points.py` (import `registry` to declare)
- Test: `tests/test_agent_backend_contributions.py` (new); every `tests/test_agent*.py`, `tests/test_crash_report*.py`, `tests/test_sciqlop_event_loop.py` must pass.
- Docs: `references/ui-and-settings.md` ("Agents" section: backends part), `references/plugin-contract.md`.

**Interfaces:**
- Produces:
  - `AgentBackendEntry(name: str, factory: Callable[[BackendContext], AgentBackend])`, frozen dataclass; empty `name` → `ValueError`.
  - `AGENT_BACKENDS = declare(ExtensionPoint("sciqlop.agent_backends", AgentBackendEntry, what="agent backend", key=attrgetter("name"), doc="Agent chat backends by display name."))`.
  - `register_agent_backend(...)`: same argument handling and `TypeError` as today, then `_contribute_backend(AgentBackendEntry(name, factory), current_owner())`, an `@on_main_thread` function doing `AGENT_BACKENDS.contribute(entry, owner=owner, replace=True)` (owner captured on the calling thread). Replacing another owner's name: `log.warning` naming both owners (use `core.extensions.contribute_taking_over` if its signature fits; it takes the owner from `current_owner()`, so check and adapt rather than duplicating it).
  - `unregister_agent_backend(name)`: `AGENT_BACKENDS.remove(name)` if present, no-op otherwise (`@on_main_thread`).
  - `available_backends()`: `sorted(AGENT_BACKENDS.keys())` (thread-safe snapshot). `create_backend(name, ctx)`: `KeyError(f"no agent backend registered: {name!r}")` when absent, as today.
  - `_BACKENDS` is removed.
  - Chat dock: in its constructor, connect `AGENT_BACKENDS.signals.added/removed` to one bound slot, guarded by `shiboken6.isValid(self)`, that refreshes the combo **without** rebinding the live session when the current backend is still listed. Read `refresh_backends()` and `_on_backend_changed()` first: today `refresh_backends()` always calls `_on_backend_changed(idx)`; split it so the follower only rebuilds the combo items and selection, and calls `_on_backend_changed` only if the current backend disappeared (then it falls back exactly as `refresh_backends` does now: remembered, else first; with none left, `_set_empty(...)`). `refresh_backends()` stays public and keeps its current behaviour (out-of-tree plugins call it through `ensure_agent_dock`).

- [ ] **Step 1: Write the failing tests** in `tests/test_agent_backend_contributions.py` (use the chat-dock fixtures/helpers `tests/test_agent_chat_dock_wiring.py` uses; a minimal fake backend class with `display_name`, copy from existing tests; remove every contribution in teardown):
  - `test_register_is_a_contribution`: `register_agent_backend(Fake)` under `owned_by("be_demo")`; `"Fake" in AGENT_BACKENDS`, owner `"be_demo"`; `available_backends()` lists it; `AGENT_BACKENDS.remove_owner("be_demo")` removes it from `available_backends()`; `create_backend("Fake", ctx)` raises `KeyError`.
  - `test_legacy_two_arg_form_and_unregister`: `register_agent_backend("Named", factory)`; `unregister_agent_backend("Named")`; `unregister_agent_backend("Named")` again is a no-op.
  - `test_reregistering_replaces`: same name twice, second factory wins, no exception.
  - `test_missing_display_name_raises_type_error`.
  - `test_the_dock_lists_a_live_installed_backend_without_rebinding` (Review Focus 1): dock with backend A selected and a session bound (spy on `_on_backend_changed` or the bind method the wiring tests use); register B; B is in the combo; A is still current; no rebind happened.
  - `test_withdrawing_the_current_backend` (Review Focus 2): dock on A; `remove_owner` A's owner; A leaves the combo; selection falls back as specified; with no backend left, the empty-state message shows; no exception.
  - `test_a_destroyed_dock_ignores_backend_signals`: build the dock in a main window, destroy it with `destroy_main_window`, then register a backend; no exception (pytest-qt reports slot exceptions).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, then (one invocation each) `tests/test_agent*.py`, `tests/test_crash_report*.py tests/test_sciqlop_event_loop.py`. All pass.
- [ ] **Step 5: Commit** `feat(plugins): agent backends are contributions to sciqlop.agent_backends; the chat dock follows them`.

---

### Task 2: `sciqlop.agent_tools`

**Files:**
- Create: `SciQLop/components/agents/tools/contributed.py`
- Modify: `SciQLop/components/agents/tools/_builder.py`, `SciQLop/components/agents/tools/__init__.py` and `SciQLop/components/agents/__init__.py` (export `AgentTool`, `AGENT_TOOLS`), `SciQLop/components/extension_points.py`
- Test: `tests/test_agent_tool_contributions.py` (new); every `tests/test_agent*.py` must pass, including the test that pins published tool names.
- Docs: "Agents" section in `references/ui-and-settings.md` (tools part, with a 10-line example of a read-only tool and a gated one), `references/plugin-contract.md`.

**Interfaces:**
- Produces:
  - `AgentTool(name: str, description: str, input_schema: dict, call: Callable[[dict], Any], gated: bool = False, thread: bool = False)`, frozen dataclass; `name` must match `^[a-zA-Z0-9_-]{1,64}$` and `description` be non-empty, else `ValueError`. `call` may return text, a dict with `"content"` (as core tools do), or a coroutine — exactly what `_text_tool` accepts. `thread=True` runs it in the I/O pool (Qt-free callables only), as `_text_tool` does.
  - `AGENT_TOOLS = declare(ExtensionPoint("sciqlop.agent_tools", AgentTool, what="agent tool", key=attrgetter("name"), doc="Tools offered to agent sessions, beyond SciQLop's own."))`.
  - `contributed_tool_dicts(taken: set[str]) -> list[dict]` in `contributed.py`: for each contribution in contribution order, skip (with `log.error(f"agent tool {name!r} from {owner} ignored: the name is already taken")`) any name in `taken` or already emitted; otherwise build the dict with `_text_tool(name, description, input_schema, _guarded(tool), gated=gated, thread=thread)`. `_guarded(tool)` returns a callable that first checks `AGENT_TOOLS` still holds this exact `tool` object (`AGENT_TOOLS.get(name) is tool`, read without the main-thread check: use `name in AGENT_TOOLS` and the `keys()`/dict read that is safe from any thread, or capture a plain flag flipped by a `removed` follower — choose the one that is correct when the handler runs off the main thread, and say which in the report) and returns `"this tool was withdrawn (its plugin was unloaded)"` as text otherwise; else delegates to `tool.call`.
  - `build_sciqlop_tools(main_window)`: after building the core list, `tools.extend(contributed_tool_dicts({t["name"] for t in tools}))`, before `_journal_all_tool_calls`. Nothing else in the core list changes.
  - Tools are a per-session snapshot: the chat dock builds `self._tools` once today. Make it rebuild `self._tools` on `AGENT_TOOLS` `added`/`removed` (bound slot, `isValid` guard), so the next session gets the current set; the running session keeps its list. `simplify:` comment: no live tools/list_changed notification to running sessions; add it when a backend supports it.

- [ ] **Step 1: Write the failing tests** in `tests/test_agent_tool_contributions.py` (async tool handlers: run them the way existing tool tests do, e.g. `asyncio.run` or the repo's helper; remove contributions in teardown):
  - `test_a_contributed_tool_is_built`: contribute `AgentTool("demo_echo", "Echo.", schema, lambda p: p["text"])` under `owned_by("tool_demo")`; `build_sciqlop_tools(main_window)` contains a dict named `demo_echo` with `gated` False; calling its handler with `{"text": "hi"}` returns content text `hi`.
  - `test_a_gated_and_threaded_tool`: `gated=True, thread=True`; the dict has `gated` True and the handler runs (assert the call ran on a non-main thread).
  - `test_a_core_name_is_refused` (Review Focus 4): contribute `sciqlop_exec_python`; the built list has exactly one tool with that name, and it is the core one (its description is the core description); one `log.error` naming the name.
  - `test_a_withdrawn_tool_answers_withdrawn` (Review Focus 3): build tools, then `remove_owner("tool_demo")`, then call the previously built handler; the content text says withdrawn; the original `call` was not invoked.
  - `test_bad_names_are_refused`: `"has space"`, `""`, 65 characters → `ValueError`.
  - `test_the_dock_rebuilds_its_tools_for_the_next_session`: dock `_tools` gains `demo_echo` after contribution and loses it after withdrawal.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, then `tests/test_agent*.py` (one invocation). All pass.
- [ ] **Step 5: Commit** `feat(plugins): plugins contribute agent tools through sciqlop.agent_tools`.

---

### Task 3: `sciqlop.agent_skills`

**Files:**
- Modify: `SciQLop/components/agents/skills/__init__.py`, `SciQLop/components/agents/__init__.py` (export `AgentSkill`, `AGENT_SKILLS`), `SciQLop/components/extension_points.py` (contribute the core skills, owner `"sciqlop"`)
- Test: `tests/test_agent_skill_contributions.py` (new); the existing skills tests (grep `sync_skills` under `tests/`) and `tests/test_agent*.py` must pass.
- Docs: "Agents" section in `references/ui-and-settings.md` (skills part: folder layout, name rules, publication on the next agent session), `references/plugin-contract.md`.

**Interfaces:**
- Produces:
  - `AgentSkill(name: str, directory: Path)`, frozen dataclass; `name` must match `^[a-z0-9][a-z0-9-]{0,63}$` (folder-safe, the bundled ones' style) and `directory / "SKILL.md"` must be a file, else `ValueError`.
  - `AGENT_SKILLS = declare(ExtensionPoint("sciqlop.agent_skills", AgentSkill, what="agent skill", key=attrgetter("name"), doc="Agent skills published into each workspace's .claude/skills/."))`.
  - `contribute_core_skills()`: one `AgentSkill(p.name, p)` per sub-folder of `BUNDLED_SKILLS_DIR` holding a `SKILL.md`, owner `"sciqlop"`, idempotent (skip names present). Called from `prepare_extension_points`, and also at the top of `sync_skills` (so `sync_skills` used without the app — tests, tools — still publishes the core skills; it is idempotent).
  - `sync_skills(workspace_dir)`: publish every contributed skill's `*.md` files (recursively, same `_write_if_changed`) into `<workspace>/.claude/skills/<name>/`; record the published names in `<workspace>/.claude/skills/.sciqlop-published` (one name per line); remove the folders of names listed there that are no longer contributed (`shutil.rmtree`), then rewrite the list. Never remove a folder whose name is not in that list. Stays best-effort: `OSError` anywhere → swallowed, as today. Runs from the guidance publish path at session start; reading the EP there: check which thread `guidance.publish`/`sync_skills` runs on; if it can run off the main thread, read `AGENT_SKILLS` through the thread-safe `keys()` + a snapshot, never `list()` from another thread (`list()` is a dict comprehension over live values).
  - First run on an existing workspace (no `.sciqlop-published` yet): treat the bundled names as previously published, so nothing else is removed.

- [ ] **Step 1: Write the failing tests** in `tests/test_agent_skill_contributions.py` (`tmp_path` workspace and a `tmp_path` skill folder; remove contributions in teardown):
  - `test_core_skills_are_contributions`: after `contribute_core_skills()`, the six bundled names are in `AGENT_SKILLS`, owned by `"sciqlop"`.
  - `test_a_plugin_skill_is_published`: contribute `AgentSkill("demo-skill", dir)` with `SKILL.md` and `references/x.md` under `owned_by("skill_demo")`; `sync_skills(ws)`; both files exist under `ws/.claude/skills/demo-skill/`.
  - `test_a_withdrawn_skill_is_removed_but_user_skills_stay` (Review Focus 5): also create `ws/.claude/skills/my-own/SKILL.md`; publish; `remove_owner("skill_demo")`; `sync_skills(ws)`; `demo-skill/` is gone, `my-own/` is intact, the core skills are still there.
  - `test_existing_workspace_without_a_record`: a workspace that already has the bundled skills and a user folder but no `.sciqlop-published`; `sync_skills` removes nothing.
  - `test_bad_skill_is_refused`: bad name, or a folder without `SKILL.md` → `ValueError`.
  - `test_read_only_workspace_never_raises` (keep the existing best-effort contract; copy the existing test's approach if there is one).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, the existing skills tests, `tests/test_agent*.py` (one invocation each). All pass.
- [ ] **Step 5: Commit** `feat(plugins): agent skills are contributions to sciqlop.agent_skills; withdrawn skills leave the workspace`.

---

### Task 4: Interop proof and spec bookkeeping

**Files:**
- Modify: `tests/test_plugin_interop.py` (one test; reuse `_plugin`, `fresh`, `_OWNERS`; withdraw through `loader._withdraw`)
- Modify: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§4.3 row: append `; **implemented**: docs/superpowers/plans/2026-10-15-agent-backends-tools-skills.md`)

- [ ] **Step 1: Write the test** `test_plugin_contributes_an_agent_backend_a_tool_and_a_skill`: plugin `agent_maker` whose `activate(ctx)` calls `register_agent_backend(Fake)` (a minimal backend class with `display_name = "AgentMakerFake"`), contributes `AgentTool("agent_maker_ping", "Ping.", schema, lambda p: "pong")` and `AgentSkill("agent-maker", <a folder the test writes under tmp_path with SKILL.md>)`. Load it through the loader with the `main_window` fixture. Assert the three owners are `agent_maker`, `"AgentMakerFake" in available_backends()`, `build_sciqlop_tools(main_window)` holds `agent_maker_ping`, and `sync_skills(tmp_ws)` publishes `agent-maker/SKILL.md`. Then `loader._withdraw("agent_maker")`: the backend left `available_backends()`, the tool is absent from a fresh `build_sciqlop_tools`, and a second `sync_skills(tmp_ws)` removed `agent-maker/`.
- [ ] **Step 2: Run** `tests/test_plugin_interop.py` alone; all pass.
- [ ] **Step 3: Update the spec row** and commit `test(plugins): interop proof for agent backends, tools and skills; spec row marked implemented`.

Follow-up outside this plan (out-of-tree repo): the five agent-backend plugins keep working unchanged through `register_agent_backend`; they can drop their `ensure_agent_dock(...).refresh_backends()` calls once a SciQLop release ships this follower.
