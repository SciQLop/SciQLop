# Agent chat UI — session info, effort, and settings consolidation

**Date:** 2026-07-30
**Status:** approved design, not yet implemented
**Repos touched:** `SciQLop` (core), `plugins_sciqlop/sciqlop_claude`, `plugins_sciqlop/sciqlop_albert`, `plugins_sciqlop/sciqlop_copilot`, `plugins_sciqlop/sciqlop_opencode`

## Problem

Three separate complaints about the agent dock, all visible in the current header:

1. **No session information.** The dock shows nothing about tokens, cost, context usage or
   quota. Every backend already reports some of it and the dock discards all of it —
   `sciqlop_claude`'s `_decode_message` returns before ever looking at `ResultMessage`, and
   `sciqlop_opencode`'s `_OpencodeStream.feed` bails on any message without a `content` list.
2. **No effort control.** `ClaudeAgentOptions.effort` exists and is never set.
3. **The header does not scale.** Seven controls compete on one row
   (`New session`, `Export`, backend, `Sessions`, model, `Allow write actions`, `Activity`),
   and every new option makes it worse.

## Goals

- A compact session-info strip below the input, with a detail popup. Visible whenever the
  backend reports anything at all; hidden only when it reports nothing.
- An effort selector wherever the backend can actually honour one.
- A short top bar: `New session`, backend, `☰ Sessions`, `⚙` — everything else in the ⚙ popup.
- Uniform treatment across all four backends, degrading per-field rather than all-or-nothing.

## Non-goals

- Changing the transcript, streaming contract, or session-list behaviour.
- Historical or cross-session cost aggregation. The strip describes the *live* session.
- Making `AgentBackend`'s required contract any larger (see "Protocol compatibility").

## Backend capability matrix

Verified against live API specs and vendored SDKs on 2026-07-30, not from memory. This table
is the reason the design is shaped the way it is — the four backends expose overlapping but
genuinely different data.

| | tokens | cost | context % | quota | effort | distinctive |
|---|---|---|---|---|---|---|
| **Copilot** | ✅ + cache/reasoning | ✅ nano-AIU + token prices | ✅ `max_prompt_tokens` | ✅ % remaining + reset date | ✅ per-model | premium multiplier |
| **Claude** | ✅ | ✅ USD | ✅ full category breakdown | — | ✅ per-model | only category detail |
| **Albert** | ✅ + cache/reasoning | ✅ USD + budget | ✅ `max_context_length` | ✅ budget | ❌ | only carbon footprint |
| **Opencode** | ✅ (raw dict) | ✅ USD | ✅ via models.dev | — | ❌ SDK gap | — |

### Sources per backend

**Claude** (`claude-agent-sdk` 0.2.126, `ClaudeSDKClient`)
- `ResultMessage.usage`, `.total_cost_usd`, `.num_turns`, `.duration_api_ms`, `.session_id`
- `ResultMessage.model_usage: dict[str, ModelUsage]` — `canonicalModel` is the stable
  resolved model name, better for display than the combo label
- `client.get_context_usage()` → `categories[]`, `totalTokens`, `maxTokens`, `model`,
  `mcpTools`, `memoryFiles`, `agents` — the same data as the CLI's `/context`
- `ClaudeAgentOptions.effort: EffortLevel = "low"|"medium"|"high"|"xhigh"|"max"`

**Albert** (OpenGateLLM; live OpenAPI at `albert.api.etalab.gouv.fr/openapi.json`)
- `ChatCompletionChunk.usage` → `CompletionUsage` when `stream_options.include_usage` is set.
  `stream_options` is an untyped passthrough field, so it forwards.
- `prompt_tokens_details.cached_tokens`, `completion_tokens_details.reasoning_tokens`
- `GET /v1/me/usage` → per-request `UsageDetail`: `cost`, `impacts` (kWh, kgCO2eq),
  `metrics` (latency, ttft). This is how cost and carbon are obtained after a *streamed*
  turn, since streaming chunks carry only `CompletionUsage`.
- `GET /v1/me/info` → `budget` (`null` = unlimited), `limits`, `expires`
- `GET /v1/models` → `Model.max_context_length`, `Model.costs` (price per 1M tokens)
- No `reasoning_effort` in `CreateChatCompletion`. Effort is genuinely unavailable.

**Copilot** (`microsoft/vscode`: `src/typings/copilot-api.d.ts`, `extensions/copilot/.../chatMLFetcher.ts`)
- `usage.prompt_tokens`, `.completion_tokens`, `.prompt_tokens_details.{cached_tokens,
  cache_creation_input_tokens}`, `.completion_tokens_details.reasoning_tokens`
- `usage.copilot_usage.total_nano_aiu` — per-request credits, what VS Code's own credits
  display uses (`chatMLFetcher.ts:400`)
- `CCAModelBilling.token_prices.default.{input_price, cache_price, cache_write_price,
  output_price}`, plus a `long_context` tier, and `is_premium` / `multiplier`
- `CCAModelLimits.max_prompt_tokens` — **use this, not `max_context_window_tokens`**, which
  is widely reported as over-stated (400k advertised vs 128k usable)
- `GET /copilot_internal/user` → `quota_snapshots.{chat, completions, premium_interactions}`
  each with `percent_remaining`, `quota_remaining`, `entitlement`, `unlimited`,
  `overage_permitted`; plus top-level `quota_reset_date`
- `reasoning_effort` is in VS Code's forwarded request-body allowlist alongside `thinking`
  and `thinking_budget`; per-model bounds via `capabilities.supports.{min,max}_thinking_budget`

**Opencode** (`opencode-agent-sdk` 0.4.12)
- `ResultMessage.usage` / `.total_cost_usd` from opencode's `step-finish` part
- **Stale:** every 0.4.x release, 0.4.7 through 0.4.12, was published 2026-03-26. The
  vendored copy is already latest; there is nothing to bump.
- The ACP path (`_internal/acp.py:344`) passes `usage` through as a **bare dict**; the HTTP
  path (`_internal/http_transport.py:267`) builds a proper `Usage` dataclass with cache
  tokens. The plugin uses ACP (`server_url` empty), so the mapper must accept both shapes.
- Both paths hardcode `duration_ms=0.0` and `num_turns=1` — leave both unreported rather
  than display a fake `1`.
- `AgentOptions` has no reasoning/effort/thinking field at all. Effort is unreachable
  through this SDK regardless of model support — an SDK gap, not a model limitation.
- `ModelRegistry` / `ModelConfig` are exported but are only a caller-populated alias map:
  no enumeration, no limits, no pricing. The plugin's existing comment is accurate.

## Architecture

Four units, each independently testable.

### 1. Core protocol — `SciQLop/components/agents/backend.py`

Flat frozen dataclasses. Every field is `None`-able so "absent" is distinguishable from
"zero" — that distinction is what drives per-field rendering.

```python
@dataclass(frozen=True)
class TokenCounts:
    input: int | None = None
    output: int | None = None
    cache_read: int | None = None
    cache_write: int | None = None
    reasoning: int | None = None

    @property
    def total(self) -> int | None: ...

@dataclass(frozen=True)
class Cost:
    amount: float
    unit: str = "USD"          # "USD" | "credits"  (Copilot bills in nano-AIU)

@dataclass(frozen=True)
class Quota:
    """Remaining allowance — Copilot premium requests, Albert budget."""
    label: str                 # "premium requests" | "budget"
    percent_remaining: float | None = None
    remaining: float | None = None
    entitlement: float | None = None
    unlimited: bool = False
    resets: str | None = None

@dataclass(frozen=True)
class CarbonFootprint:
    kwh: float | None = None
    kg_co2eq: float | None = None

@dataclass(frozen=True)
class ContextCategory:
    name: str
    tokens: int

@dataclass(frozen=True)
class UsageSnapshot:
    model: str | None = None               # resolved/canonical name
    tokens: TokenCounts | None = None
    cost: Cost | None = None
    context_tokens: int | None = None
    context_max: int | None = None
    context_categories: tuple[ContextCategory, ...] = ()
    quota: Quota | None = None
    carbon: CarbonFootprint | None = None
    num_turns: int | None = None
    duration_api_ms: int | None = None
    session_id: str | None = None

    @property
    def context_percent(self) -> float | None: ...
```

`effort` is deliberately **not** in the snapshot — the dock owns the current effort as UI
state and does not need the backend to echo it back.

**Protocol compatibility.** These go in a *separate* optional protocol, never added to
`AgentBackend`:

```python
class UsageReportingBackend(Protocol):
    """Optional. Backends implement any subset; the dock probes with getattr."""
    async def usage_snapshot(self) -> UsageSnapshot | None: ...
    def effort_values(self) -> tuple[str, ...]: ...   # for the CURRENT model; () = unsupported
    async def set_effort(self, effort: str | None) -> None: ...
```

`components/agents/` is consumed by out-of-tree plugins, so adding required members to
`AgentBackend` would misdocument every backend that does not implement them. Nothing in the
tree does `isinstance(x, AgentBackend)` today (it is used only as a type annotation), but the
protocol must stay an honest description of the required contract regardless.

**One async hook, not two.** Both Claude and Albert need a *follow-up call after the streamed
turn* to obtain the rich numbers — Claude a control request, Albert a `GET /v1/me/usage`. A
single `usage_snapshot()` covers both, and Copilot's quota fetch, and Opencode's
already-buffered values.

`effort_values()` returns the set for the **currently selected model**, and lives in the
backend rather than in core, because the constraint is a *join* of two things only the
backend knows: what the SDK will accept on the wire, and what the model supports. Claude
returns the SDK's `EffortLevel` set; Copilot returns the models.dev per-model values;
Albert and Opencode return `()`.

### 2. Model capability lookup — `SciQLop/components/agents/model_capabilities.py`

models.dev is a public unauthenticated registry (175 providers, 5,892 models) that covers
`anthropic`, `github-copilot` and `opencode`. It supplies exactly the three things otherwise
hardcoded per backend:

- `limit.context` — present for 5,780 models
- `cost.{input, output, cache_read, cache_write}` (per 1M tokens) — 5,489 models, with a
  tiered variant above 200k context
- `reasoning_options` with `type: "effort"` — 1,641 models, **each with its own value list**

That last point is the reason this module exists. Effort values are per-model, not
per-provider:

```
claude-sonnet-4.6   low | medium | high | max
gemini-3.5-flash    minimal | low | medium | high
gpt-5.6-sol         none | low | medium | high | xhigh | max
```

A hardcoded `low…high` list would offer `xhigh` to a Gemini model that rejects it.

```python
@dataclass(frozen=True)
class ModelCapabilities:
    context_limit: int | None = None
    output_limit: int | None = None
    effort_values: tuple[str, ...] = ()
    cost_input: float | None = None       # USD per 1M tokens
    cost_output: float | None = None
    cost_cache_read: float | None = None

def capabilities_for(provider: str, model: str) -> ModelCapabilities | None: ...
```

**Constraints, all load-bearing:**

- **Offline is a supported state.** SciQLop must remain fully usable with no network.
  `capabilities_for` returns `None` when the registry is unavailable, and every consumer
  already handles `None`. The strip simply shows fewer segments.
- **Never fetched on the GUI thread.** The refresh is an async task, same as
  `usage_snapshot()`.
- **Cached on disk** through the normal SciQLop cache-dir helper, refreshed at most once per
  7 days. It must go through that helper and not a hand-built path, because
  `tests/conftest.py` redirects `XDG_CACHE_HOME` for every pytest run — a hardcoded path
  would silently read the developer's real cache during tests.
- **Tests never hit the network.** The registry is injected in tests via a fixture holding a
  small literal fixture document.
- Albert is absent from models.dev and does not need it: its own `/v1/models` already
  provides `max_context_length` and `Model.costs`.

### 3. Widgets — two new files under `chat/`

**`chat/info_bar.py`**
- `SessionInfoBar` — the footer strip. `set_snapshot(UsageSnapshot | None)`,
  `set_effort(str | None)`. Renders only the segments that have data; hides itself entirely
  when every field is empty.
- `ContextBreakdownPopup` — the ⓘ detail. Category rows, then a footer line with turns,
  api duration, cost, and (Albert) carbon.
- `TokenBar` — a slim meter shared by both.
- Pure formatters — `fmt_tokens`, `fmt_cost`, `fmt_duration`, `fmt_quota` — with no Qt
  dependency, so the bulk of the display logic is testable without a widget.
- Bar heights in `ex` units, per the project QSS rule.

**`chat/settings_popup.py`**
- `AgentSettingsPopup` — a `Qt.WindowType.Popup` widget with a `QFormLayout`: model, effort,
  activity verbosity, allow-writes, a separator, and Export.
- A `Qt.Popup` widget rather than a `QMenu` with `QWidgetAction`s: combos inside menus
  swallow clicks and close the menu on interaction. Click-away dismissal comes free with the
  flag.

### 4. Dock changes — `chat_dock.py`

Header becomes `[＋ New] [Claude ▾] [☰ Sessions] [⚙ ▾]  <status label, stretch>`.

The moved widgets stay instance attributes, so the existing `_interactive` enable/disable
path and the existing tests keep working. Constructing them moves into
`settings_popup.py`, which shrinks `chat_dock.py` — it is 733 lines today, above where it
should be.

Refresh points, no timer:

```
turn completes (_run_turn success path) → _spawn(_refresh_usage())
ⓘ popup opens                          → _spawn(_refresh_usage())
backend switch (_bind_to_session)      → _spawn(_refresh_usage()) + repopulate effort
model change (_on_model_changed)       → repopulate effort from backend.effort_values()
```

`_refresh_usage()` skips if a refresh is already in flight, awaits
`backend.usage_snapshot()`, and hands the result to the strip. It swallows every exception:
a usage failure must never surface as a turn error.

Effort persists **per backend**, as `AgentChatSettings.effort: dict[str, str]` keyed by
`backend.display_name`, with `""` meaning "backend default" — mirroring how `model_choices`
uses `None` for no-override. It must be per-backend rather than a single global string
because the valid value sets differ (`xhigh` is meaningful to Claude and rejected by a
Copilot-hosted Gemini). On bind, a persisted value is applied only if it appears in the
current model's `effort_values()`; otherwise it is ignored and the combo falls back to
default, leaving the stored value untouched for when that model is selected again.

## Per-backend implementation notes

**`sciqlop_claude`** — capture `ResultMessage` in `ask()` into `self._last_result`.
`usage_snapshot()` merges it with `await client.get_context_usage()`, preferring
`model_usage[...].canonicalModel` for the display name. `effort_values()` returns the SDK's
`EffortLevel` set narrowed by `capabilities_for("anthropic", model)` when known.

`set_effort` is the one wrinkle: the SDK has `client.set_model()` but **no** `set_effort` —
effort only enters through `ClaudeAgentOptions` at connect time. So `set_effort` stores the
value and disconnects, letting the next turn reconnect with it. For that not to lose the
conversation, the backend must start recording `ResultMessage.session_id` into `self._resume`
so a reconnect resumes the live session. That is a small, contained addition, and it also
hardens the existing `set_model` error path, which today drops the session silently on
reconnect.

**`sciqlop_albert`** — add `stream_options: {"include_usage": True}` to the request body and
**move the `if not choices: return` guard** in `consume_line`: the usage-bearing final chunk
is precisely the one with `choices: []`, so the current guard discards it. `usage_snapshot()`
combines the captured chunk tokens with a `GET /v1/me/usage?limit=1` for cost and carbon, a
cached `GET /v1/me/info` for budget, and `Model.max_context_length` from the already-fetched
model list. `effort_values()` returns `()`.

**`sciqlop_copilot`** — same `include_usage` change and the same `choices: []` guard fix.
`usage_snapshot()` reads `copilot_usage.total_nano_aiu` as `Cost(unit="credits")`,
`capabilities.limits.max_prompt_tokens` as `context_max`, and
`GET /copilot_internal/user` for `quota_snapshots.premium_interactions` — cached for 5
minutes, since a monthly quota does not move per turn and the strip refreshes after every
one. `effort_values()` comes from `capabilities_for("github-copilot", model)`.

**`sciqlop_opencode`** — handle `ResultMessage` in `_OpencodeStream.feed` (it currently
returns early on anything without a `content` list). The mapper accepts `usage` as either a
`Usage` dataclass or a bare dict. `context_max` from
`capabilities_for(*self._model.split("/"))`. Leave `num_turns` and `duration_api_ms` unset —
both are hardcoded upstream. `effort_values()` returns `()`.

**Shared OpenAI-compatible code.** Albert and Copilot currently hold ~130 verbatim-identical
lines (`_stream_sse`, `_build_openai_tools`, `_execute_tool`), and both need the same usage
work inside them. That moves to `SciQLop/components/agents/openai_compat.py` — written once,
with the usage-chunk capture built in — and each plugin keeps only what is genuinely its own
(Albert: `/v1/me/usage`, budget, carbon; Copilot: quota, nano-AIU). Both plugins gain a
SciQLop version floor as a result.

## Implementation phasing

The work spans core plus four plugins, which is more than one sitting. It stages naturally
into three, each independently shippable and each leaving the tree green:

- **Phase 1 — core + Claude.** Protocol dataclasses, `model_capabilities`, both widgets,
  dock rewiring, and `sciqlop_claude`. This proves the entire path end to end against the
  richest backend, including effort, before any other plugin is touched.
- **Phase 2 — `openai_compat` + Albert + Copilot.** Factor the shared streaming helper into
  core, port both plugins onto it, add their usage/quota/carbon specifics.
- **Phase 3 — Opencode.** The smallest change: handle `ResultMessage`, accept both `usage`
  shapes, context via models.dev.

Phase 1 is the only phase that touches the dock UI, so a regression in phases 2–3 can only
affect a single backend's numbers, never the chat itself.

## Testing

TDD, in this order. Most of the logic is deliberately pushed into pure functions so it does
not need a running dock.

1. **Formatters and derived properties** — `fmt_tokens`, `fmt_cost` (USD vs credits),
   `fmt_duration`, `fmt_quota`, `TokenCounts.total`, `UsageSnapshot.context_percent`
   including the `context_max=None` case. No Qt.
2. **`model_capabilities`** — per-model effort value lists parsed from a fixture document
   (the three divergent examples above); `None` when the registry is absent; cache path
   resolves under the redirected `XDG_CACHE_HOME`; no network in any test.
3. **`SessionInfoBar.set_snapshot`** — a snapshot with only tokens renders one segment; one
   with tokens + cost + context renders three; an all-empty snapshot hides the widget;
   carbon renders only when present.
4. **`AgentSettingsPopup`** — effort combo absent when `effort_values()` is `()`; present
   with exactly the model's values when not; changing it calls `set_effort` and persists to
   `AgentChatSettings`.
5. **Dock wiring** — header contains only the four primary widgets; the moved widgets are
   parented to the popup; Export still exports from its new home; a backend raising from
   `usage_snapshot()` leaves the turn unaffected.
6. **Per-plugin mappers**, in each plugin's own test dir: a fake `ResultMessage` →
   `UsageSnapshot` (Claude, Opencode-dataclass, Opencode-bare-dict); a fake
   `get_context_usage()` dict → categories; a fake SSE final chunk with `choices: []` →
   tokens captured, proving the guard fix; a fake `/copilot_internal/user` → `Quota`;
   a fake `/v1/me/usage` → cost + carbon.

## Needs live verification during implementation

Each of these is a claim I could not confirm from specs alone. None blocks the design; all
must be checked against a real run before the feature is called done.

1. Whether Claude's `ResultMessage.total_cost_usd` is per-turn or cumulative — decides
   whether the backend sums it.
2. That effort change → disconnect → reconnect → resume actually preserves conversation
   history.
3. That Albert's live deployment honours `stream_options.include_usage` (needs an API key).
   Note the deployment still exposes the RAG endpoints, so it is on ≤0.4.9, not 0.5.0.
4. That Copilot honours `include_usage`, and the exact `/copilot_internal/user` response
   shape (needs a GitHub token).

## Out of scope — flagged, not addressed here

- **`claude-agent-sdk` 0.2.126 → 0.2.128**, to be bumped in its own commit before this work.
  0.2.127 fixes a *PreToolUse bypass when background tasks are in flight*, which is
  SciQLop's write-action gate failing open. Worth fixing independently of this feature.
- **`sciqlop_copilot` hardcodes `/chat/completions` for every model.**
  `CCAModel.supported_endpoints` documents that Anthropic-format models use `/v1/messages`,
  so selecting a Claude model in the Copilot dropdown may fail outright. Pre-existing bug.
- **`sciqlop_claude/backend.py` still carries the `DESYNC-PROBE` instrumentation** — ~25
  lines of forced-`warning` logging plus `_log.level = DEBUG`, left over from the June
  desync hunt that was confirmed fixed.
- **`uv.lock` is stale on `main`:** commit `90754bfb` bumped `pyproject.toml` to
  SciQLopPlots 0.32.1 without regenerating it.
- **Opencode HTTP transport mode** would yield cache-token detail that ACP mode lacks, but
  requires running `opencode serve` — a deployment change, not justified by this feature.

## Sources

- [OpenGateLLM releases](https://github.com/etalab-ia/OpenGateLLM/releases) — Albert API, renamed from `albert-api`; 0.5.0 (2026-07-27) removes RAG
- [Live Albert OpenAPI](https://albert.api.etalab.gouv.fr/openapi.json)
- [vscode `copilot-api.d.ts`](https://github.com/microsoft/vscode/blob/main/src/typings/copilot-api.d.ts)
- [vscode `chatMLFetcher.ts`](https://github.com/microsoft/vscode/blob/main/extensions/copilot/src/extension/prompt/node/chatMLFetcher.ts)
- [Copilot quota response shape](https://huggingface.co/spaces/imspsycho/copilot-api/blob/main/src/services/github/get-copilot-usage.ts)
- [claude-agent-sdk releases](https://github.com/anthropics/claude-agent-sdk-python/releases)
- [models.dev registry](https://models.dev/api.json)
