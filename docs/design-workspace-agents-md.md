# Workspace `AGENTS.md` — one guidance source for every agent backend

**Date:** 2026-08-10
**Status:** Implemented 2026-08-10 (Claude injection pending one check)
**Scope:** `SciQLop/components/agents/guidance.py`, `BackendContext`, the five backend plugins.

## Problem

Operating guidance — the plotting call order, "introspect the API before writing
code", the scientist voice — is duplicated as a `SYSTEM_PROMPT` constant in
`sciqlop_claude`, `sciqlop_albert`, `sciqlop_copilot` and (until the ACP
migration) `sciqlop_opencode`. Four copies, already drifting apart in both
content and tone. `sciqlop_kimi` has none at all: ACP has no system-prompt
channel, so Kimi runs with its stock persona and no idea in what order to call
SciQLop's tools.

Separately, none of it can be adapted per workspace. A workspace *is* the
science project — mission, instrument, the intervals under study, local product
naming, which plugin providers are loaded — and today the user has no way to
tell the assistant any of that.

## Why a workspace file, and not a bigger constant

Two benefits, and the second is the one that decides the design:

1. It is the **only** channel the ACP backends have.
2. It is **user-editable per workspace.** `AGENTS.md` sits in a directory the
   user already browses (JupyterLab serves it), it is a plain text file, it
   travels with the workspace when archived or shared, and the marker protocol
   in `guidance.py` makes co-ownership safe: SciQLop rewrites only the block
   between its markers, everything else is the user's.

## What the backends can actually receive

Verified 2026-08-10 against the installed binaries and a live `opencode acp`
(1.18.15), not documentation.

| Backend | Transport | cwd = workspace | Reads `AGENTS.md` itself | Needs plumbing |
|---|---|---|---|---|
| `sciqlop_kimi` | ACP | yes | yes — probes `<dir>/.kimi-code/AGENTS.md`, `<dir>/AGENTS.md`, walking up | **no** |
| `sciqlop_opencode` | ACP (post-migration) | yes | yes — loads project `AGENTS.md`; `OPENCODE_DISABLE_PROJECT_CONFIG` opts out | **no** |
| `sciqlop_claude` | claude-agent-sdk | yes (`cwd=current_workspace_dir()`) | yes — binary: "Claude Code hardcodes CLAUDE.md / AGENTS.md discovery" | **no**, pending one check (below) |
| `sciqlop_albert` | chat-completions HTTP | n/a | no — reads no files | inject as `system` |
| `sciqlop_copilot` | chat-completions HTTP | n/a | no — reads no files | inject as `system` |

Caveat on authority: Kimi injects the file as *"project-supplied reference
data … not a privileged instruction channel."* Mechanical rules (call order,
"wait for data before screenshotting") survive that framing; voice and conduct
rules hold less firmly than in a real system prompt. That is a reason to keep
the system-prompt path where one exists — not to drop the file.

## Design

**The file on disk is the source of truth; what a backend receives is its
merged content, not a constant.** A constant cannot carry the user's own
section, and carrying it is half the point.

```
guidance.py: SCIQLOP_GUIDANCE ──sync_agents_md()──> <workspace>/AGENTS.md
                                                     (managed block + user's own text)
                                                          │
                            ┌─────────────────────────────┴───────────────┐
                    read by the agent itself              read by the plugin
                    (kimi, opencode, claude)              (albert, copilot)
                                                          → injected as `system`
```

Three of five backends need no plumbing at all: they discover the file
themselves, user section included.

### Wiring (both missing today — `sync_agents_md` has no callers)

1. **Publish before the first session exists.** opencode and kimi read project
   config when a session is created, not when a prompt is sent. Call
   `sync_agents_md(current_workspace_dir())` where `BackendContext` is built
   (`chat_dock.py:335`), not on first turn.
2. **Carry the file's contents to the two file-blind backends.** Add
   `guidance: str = ""` to `BackendContext`, populated by reading the merged
   `AGENTS.md` back after the sync. `BackendContext` is public out-of-tree API,
   so the field is additive with a default — plugins that ignore it keep
   working.
3. **Delete the local `SYSTEM_PROMPT` constants.** Albert and Copilot use
   `ctx.guidance` (Albert keeps the write-mode-dependent tail it already
   builds); Claude drops its copy entirely once the check below passes.

### The one thing to verify before Claude drops its system prompt

The `claude` binary discovers `AGENTS.md`, but it is **unconfirmed** whether it
still does so when the SDK passes an explicit `system_prompt=` — project-memory
loading and system-prompt override are separate mechanisms. One live turn in a
temp cwd settles it. Until then Claude keeps injecting `ctx.guidance`; the cost
of being wrong is one duplicated block, the cost of assuming is a silent
regression.

### Supersedes first-turn injection

`docs/superpowers/plans/2026-08-08-agent-alignment-and-plot-api-examples.md`
Task 1 proposed prepending an alignment block to the first user turn as the ACP
workaround. Drop it: it spends tokens every session, shows up in the transcript,
and is lost when a session is resumed. A workspace file is re-read on resumed
sessions too.

### Content notes

- No tool inventory in the block — MCP already ships every tool's name,
  description and schema. What descriptions cannot carry is the *order* to call
  them in and the register to write in. (Already the stance in `guidance.py`.)
- Add a line stating the `sciqlop_*` tools exist only inside SciQLop's chat
  dock: the same workspace opened with a bare CLI would otherwise read
  instructions for tools it does not have.
- Add a line inside the managed block telling the user that edits *within* the
  markers are overwritten on re-sync and theirs belong above or below.
- Tool names are written bare (`sciqlop_products_tree`); agents see them
  prefixed (`mcp__sciqlop__…`). That matched fine in the existing system
  prompts; revisit only if a model starts guessing wrong names.

### Optional, once it works

A "Edit workspace agent instructions" entry in the chat dock's ⚙ popup, opening
the file. Per-workspace customization that nobody discovers gets no use.

## Risks

| Risk | Mitigation |
|---|---|
| Clobbering a user's own `AGENTS.md` | marker-delimited managed block; content outside preserved (`merge_guidance`, tested) |
| User edits inside the managed block | can't be prevented; state it in the block itself |
| Read-only or missing workspace dir | `sync_agents_md` is best-effort, swallows `OSError` — chat must never break on it |
| User opts out (`OPENCODE_DISABLE_PROJECT_CONFIG`) | accepted; that user chose stock behaviour |
| Guidance weaker than a system prompt on ACP | accepted, no alternative channel exists; the HTTP backends keep the strong path |

## Status — implemented 2026-08-10

- `guidance.py` gained `load_guidance()` (sync, then read back the merged file)
  and the two content lines; `merge_guidance` unchanged.
- `current_workspace_dir()` moved to `agents/workspace.py`; `acp/sessions.py`
  re-exports it, so the resolver is no longer duplicated.
- `BackendContext.guidance` added (defaulted, additive); `chat_dock`
  `_create_session` publishes and passes it before the backend is built.
- `sciqlop_claude`, `sciqlop_albert` and `sciqlop_copilot` dropped their
  `SYSTEM_PROMPT` copies for `ctx.guidance` + their own write-mode line. Albert
  keeps a `_WORKED_EXAMPLE` block — it drives smaller models and needs the
  step-by-step drill-down the shared block deliberately omits. All three read
  it via `getattr(ctx, "guidance", "")` with a `_guidance` class default, so a
  pre-0.13 core or a partially-built test instance still renders.
- Tests: `tests/test_agent_guidance.py` (16 passed) covers the new helper,
  user-section round-trip and the unusable-file fallback.

**Still open:** the Claude check above — it currently injects the guidance even
though the CLI likely discovers `AGENTS.md` itself.

## See also

- `sciqlop_opencode/docs/design-acp-migration.md` — depends on this landing
  first, or the migration ships with the persona silently gone.
- `docs/design-agent-usage-reporting.md` — the other cross-backend gap found in
  the same pass.
