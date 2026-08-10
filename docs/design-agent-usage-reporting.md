# Agent usage reporting — fill `UsageSnapshot` wherever the backend supports it

**Date:** 2026-08-10
**Status:** ACP part implemented 2026-08-10; Albert and Copilot open
**Scope:** `SciQLop/components/agents/acp/backend.py`, `sciqlop_albert`, `sciqlop_copilot`.

## Problem

`UsageReportingBackend` (`components/agents/backend.py:143`) is an optional
protocol the chat dock probes with `getattr`, feeding the session-info strip:
tokens, cost, context used/max, quotas, carbon. **Only `sciqlop_claude`
implements it.** The other four backends report nothing, so the strip is blank
for them — including the one backend whose API was the reason `CarbonFootprint`
exists:

```python
class CarbonFootprint:
    """Environmental impact of a request. Albert (OpenGateLLM) only."""
```

Meanwhile two channels that did not exist (or were not checked) when that code
was written now carry exactly what the protocol wants.

## What each backend can actually report

Verified 2026-08-10: ACP against a live `opencode acp` 1.18.15 turn, Albert
against the deployed OpenAPI spec.

| Backend | Channel | tokens | cost | context used/max | quota | carbon |
|---|---|---|---|---|---|---|
| Claude | SDK `ResultMessage` | ✅ implemented | ✅ | ✅ | ✅ | — |
| **Kimi, opencode** | ACP `UsageUpdate` | — | ✅ | ✅ | — | — |
| **Albert** | `/v1/me/usage`, `/v1/me/info`, `/v1/models` | ✅ | ✅ | ✅ (max) | ✅ | ✅ |
| Copilot | GitHub quota endpoint | ? | ? | ? | ? (unverified) | — |

## Design

### 1. ACP backends — one implementation in the base class

A real turn ends with a `UsageUpdate` session update:

```json
{"used": 14499, "size": 1000000, "cost": {"amount": 0.0, "currency": "USD"},
 "sessionUpdate": "usage_update"}
```

`AcpAgentBackend._on_update` currently forwards every non-`AvailableCommands`
update to the turn queue, and `AcpStreamTranslator.feed` returns `[]` for it —
so it is silently dropped today. Instead: intercept `UsageUpdate` in
`_on_update` (like `AvailableCommandsUpdate`), store the last one, and
implement `usage_snapshot()` on the base class:

```python
UsageSnapshot(
    model=self._model,
    context_tokens=update.used,
    context_max=update.size,
    cost=Cost(amount=update.cost.amount, unit=update.cost.currency),
)
```

`acp.schema.Usage` additionally defines `input_tokens`, `output_tokens`,
`thought_tokens`, `cached_read_tokens`, `cached_write_tokens` — a near-exact
match for `TokenCounts` — but no agent observed emits it yet. Map it defensively
(`getattr`, all-optional) so it lights up when one does.

**Kimi and opencode both get usage reporting from this single change**, which is
the strongest argument for landing it in the base class rather than per plugin.

### 2. Albert — the only backend that can report carbon

Three endpoints, all already deployed:

| Endpoint | Fields | Maps to |
|---|---|---|
| `GET /v1/me/usage` | `usage.{prompt_tokens, completion_tokens, total_tokens}`, `usage.cost`, `usage.impacts.{kWh, kgCO2eq}`, `usage.metrics.{latency, ttft}` | `TokenCounts`, `Cost`, **`CarbonFootprint(kwh, kg_co2eq)`** |
| `GET /v1/me/info` | `budget` (null = unlimited), `limits[]` (`router_id`, `type`, `value`), `expires` | `Quota(label, remaining, entitlement)` |
| `GET /v1/models` | `max_context_length`, `costs.{prompt_tokens, completion_tokens}` (per million) | `UsageSnapshot.context_max`, priced dropdown labels |

Notes:

- `/v1/me/usage` is a **per-request list**, not a running total — sum the rows
  belonging to the current session, or track the delta since session start.
  Don't present a lifetime figure as session usage.
- `budget: null` means unlimited; render no quota row rather than "0".
- `usage_snapshot()` may do I/O per the protocol docstring, but it is called
  from the dock — keep it to one `httpx` call with a short timeout and return
  `None` on failure, never raise.

### 3. Albert side-gaps found in the same pass

Both are independent of usage reporting and small:

- `fetch_models()` (`backend.py:126`) reads only `m["id"]`, so the dropdown
  shows raw ids. The API now returns `max_context_length` and per-million
  `costs` — enough for opencode-style `name — $x/1M` labels.
- `ask()` accepts `image_paths` and **silently drops them**
  (`backend.py:179`; never reaches `_build_request`), although
  `/v1/chat/completions` accepts image content parts. Either plumb them or make
  the drop visible.

### 4. Copilot — verify before designing

`sciqlop_copilot` contains no usage or quota code at all. GitHub's Copilot API
does expose premium-request entitlements, and `Quota`'s docstring already cites
Copilot's `percent_remaining` as the reason that field is canonical — so
something was investigated previously. **Confirm against the live API before
writing anything**; do not port from that docstring alone.

## Testing

- ACP: unit-test `usage_snapshot()` off a synthetic `UsageUpdate` (no live
  agent needed once `_on_update` stores it); one manual turn to confirm the
  strip populates for both kimi and opencode.
- Albert: mock the three endpoints; assert carbon and quota survive
  `budget: null` and missing `impacts`.
- Follow `sciqlop_claude/tests/test_usage_snapshot.py` for shape; its
  `test_live_usage_snapshot.py` is the opt-in live-CLI pattern.

## Order

1. ~~ACP base class~~ — **done 2026-08-10**: `_on_update` keeps the last
   `UsageUpdate` instead of dropping it, and `AcpAgentBackend.usage_snapshot()`
   maps it to context used/max plus cost. Kimi and opencode both gained usage
   reporting from that one change. `tests/test_agent_acp_usage.py`, 5 tests:
   metadata never reaches the transcript queue, latest update wins, cost-less
   updates survive, None before the first turn.
2. Albert (largest surface, only carbon source) — open.
3. Copilot (verify first) — open.
