# Agent Chat Session Info — Phase 1 (core + Claude) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a session-info strip (tokens / cost / context / quota / carbon) below the agent chat input, a per-model effort selector, and a ⚙ settings popup that empties the top bar down to `New session`, backend, `☰ Sessions`, `⚙` — wired end-to-end against the Claude backend.

**Architecture:** Backends report through one *optional* async hook, `usage_snapshot() -> UsageSnapshot | None`, probed with `getattr` so no existing backend breaks. Per-model effort values come from a shared models.dev lookup cached on disk rather than hardcoded per backend. All display logic lives in pure functions (`info_segments`, `fmt_*`) so the bulk of it is tested without Qt.

**Tech Stack:** Python 3.13, PySide6 6.11, Pydantic 2 (`ConfigEntry`), pytest + pytest-qt, `claude-agent-sdk`.

**Spec:** `docs/superpowers/specs/2026-07-30-agent-ui-session-info-design.md`

**Scope:** This plan covers **Phase 1 only** — core plus `sciqlop_claude`. Phase 2 (`openai_compat` + Albert + Copilot) and Phase 3 (Opencode) get their own plans once Phase 1 lands and the protocol has proven itself against a real backend. Phase 1 is the only phase that touches the dock UI.

## Global Constraints

- Every command runs under `uv run`. Canonical local test invocation is `uv run pytest --no-xvfb`.
- **Never add required members to the `AgentBackend` Protocol.** `SciQLop/components/agents/` is public API consumed by out-of-tree plugins; new capabilities go in the separate optional `UsageReportingBackend` protocol and are probed with `getattr`.
- **Never break existing `user_api` or `components/agents` signatures.**
- **Offline is a supported state.** `capabilities_for()` returns `None` when the registry is unavailable; every consumer handles `None`. SciQLop must stay fully usable with no network.
- **No test may hit the network.** `capabilities_for()` accepts an injected `registry` dict for exactly this reason.
- **All disk caching goes through `SciQLop.components.storage.cache_dir(compartment)`.** `tests/conftest.py` redirects `XDG_CACHE_HOME` for every pytest run, so a hand-built path would silently read the developer's real cache during tests.
- **Never fetch on the GUI thread.** `refresh_registry()` is blocking and must be called from a worker thread or `asyncio.to_thread`.
- QSS uses `ex` units; only 1px borders and `qproperty-iconSize` are exceptions. Widget heights set in code derive from `fontMetrics().xHeight()`.
- Icon: `get_icon("settings")` from `SciQLop.components.theming` — verified present in the SciQLopPlots theme icon set (121 icons).
- Commit after every task. Do not push — pushing is always an explicit separate request.

---

### Task 1: Usage data types and display formatters

Pure data and pure functions, no Qt. Everything the strip renders is decided here, so the rest of the feature can be tested against plain values.

**Files:**
- Modify: `SciQLop/components/agents/backend.py` (append after `SessionEntry`, around line 42)
- Create: `SciQLop/components/agents/chat/formatters.py`
- Modify: `SciQLop/components/agents/__init__.py` (extend imports and `__all__`)
- Test: `tests/test_agent_usage_types.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `TokenCounts`, `Cost`, `Quota`, `CarbonFootprint`, `ContextCategory`, `UsageSnapshot`, `UsageReportingBackend` from `SciQLop.components.agents.backend`; `fmt_tokens`, `fmt_cost`, `fmt_duration`, `fmt_quota`, `fmt_carbon`, `info_segments` from `SciQLop.components.agents.chat.formatters`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_usage_types.py`:

```python
"""Usage snapshot data types and the pure display formatters that render them.

No Qt, no network — these are the pieces every backend and the info bar agree on.
"""
import pytest


def test_token_counts_total_sums_input_and_output_only():
    from SciQLop.components.agents.backend import TokenCounts

    # cache_read is deliberately excluded: providers differ on whether cached
    # tokens are already counted inside input_tokens, so adding them would
    # double-count on some backends.
    t = TokenCounts(input=1000, output=250, cache_read=9000)
    assert t.total == 1250


def test_token_counts_total_is_none_when_nothing_known():
    from SciQLop.components.agents.backend import TokenCounts

    assert TokenCounts().total is None


def test_context_percent_needs_both_halves():
    from SciQLop.components.agents.backend import UsageSnapshot

    assert UsageSnapshot(context_tokens=50_000, context_max=200_000).context_percent == 25.0
    assert UsageSnapshot(context_tokens=50_000).context_percent is None
    assert UsageSnapshot(context_max=200_000).context_percent is None
    assert UsageSnapshot(context_tokens=0, context_max=0).context_percent is None


def test_fmt_tokens_scales_by_magnitude():
    from SciQLop.components.agents.chat.formatters import fmt_tokens

    assert fmt_tokens(None) == ""
    assert fmt_tokens(950) == "950"
    assert fmt_tokens(127_000) == "127.0k"
    assert fmt_tokens(2_400_000) == "2.40M"


def test_fmt_cost_distinguishes_usd_from_credits():
    from SciQLop.components.agents.backend import Cost
    from SciQLop.components.agents.chat.formatters import fmt_cost

    assert fmt_cost(None) == ""
    assert fmt_cost(Cost(amount=0.42)) == "$0.42"
    assert fmt_cost(Cost(amount=1.5, unit="credits")) == "1.50 credits"


def test_fmt_duration_switches_to_minutes():
    from SciQLop.components.agents.chat.formatters import fmt_duration

    assert fmt_duration(None) == ""
    assert fmt_duration(0) == ""
    assert fmt_duration(4200) == "4.2s"
    assert fmt_duration(108_000) == "1m 48s"


def test_fmt_quota_prefers_percent_then_absolute():
    from SciQLop.components.agents.backend import Quota
    from SciQLop.components.agents.chat.formatters import fmt_quota

    assert fmt_quota(None) == ""
    assert fmt_quota(Quota(label="budget", unlimited=True)) == "unlimited budget"
    assert fmt_quota(
        Quota(label="premium requests", percent_remaining=82.4)
    ) == "82% premium requests left"
    assert fmt_quota(
        Quota(label="premium requests", remaining=1200)
    ) == "1.2k premium requests left"


def test_fmt_carbon_scales_grams_to_kilos():
    from SciQLop.components.agents.backend import CarbonFootprint
    from SciQLop.components.agents.chat.formatters import fmt_carbon

    assert fmt_carbon(None) == ""
    assert fmt_carbon(CarbonFootprint(kg_co2eq=0.0043)) == "4.3 gCO₂eq"
    assert fmt_carbon(CarbonFootprint(kg_co2eq=2.5)) == "2.50 kgCO₂eq"
    assert fmt_carbon(CarbonFootprint(kwh=0.012)) == "12.0 Wh"


def test_info_segments_renders_only_what_is_present():
    from SciQLop.components.agents.backend import Cost, TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.formatters import info_segments

    tokens_only = UsageSnapshot(tokens=TokenCounts(input=1000, output=200))
    assert info_segments(tokens_only) == ["1.2k"]

    rich = UsageSnapshot(
        model="Opus 4.5",
        tokens=TokenCounts(input=100_000, output=27_000),
        cost=Cost(amount=0.42),
        context_tokens=168_000,
        context_max=500_000,
    )
    assert info_segments(rich, effort="high") == [
        "Opus 4.5", "high", "127.0k", "34%", "$0.42",
    ]


def test_info_segments_empty_for_nothing_to_show():
    from SciQLop.components.agents.backend import UsageSnapshot
    from SciQLop.components.agents.chat.formatters import info_segments

    assert info_segments(None) == []
    assert info_segments(UsageSnapshot()) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --no-xvfb tests/test_agent_usage_types.py -v`
Expected: FAIL — `ImportError: cannot import name 'TokenCounts'`

- [ ] **Step 3: Add the data types**

Append to `SciQLop/components/agents/backend.py`, after the `SessionEntry` dataclass:

```python
@dataclass(frozen=True)
class TokenCounts:
    """Token usage for a session. All fields optional — backends differ."""
    input: Optional[int] = None
    output: Optional[int] = None
    cache_read: Optional[int] = None
    cache_write: Optional[int] = None
    reasoning: Optional[int] = None

    @property
    def total(self) -> Optional[int]:
        # cache_read/cache_write are excluded on purpose: providers disagree on
        # whether cached tokens are already inside input_tokens, so summing them
        # would double-count on some backends.
        known = [v for v in (self.input, self.output) if v is not None]
        return sum(known) if known else None


@dataclass(frozen=True)
class Cost:
    """Session cost. `unit` is "USD" for real currency, or a backend-specific
    unit such as "credits" (Copilot bills in nano-AIU, not currency)."""
    amount: float
    unit: str = "USD"


@dataclass(frozen=True)
class Quota:
    """A remaining allowance — Copilot premium requests, Albert budget."""
    label: str
    percent_remaining: Optional[float] = None
    remaining: Optional[float] = None
    entitlement: Optional[float] = None
    unlimited: bool = False
    resets: Optional[str] = None


@dataclass(frozen=True)
class CarbonFootprint:
    """Environmental impact of a request. Albert (OpenGateLLM) only."""
    kwh: Optional[float] = None
    kg_co2eq: Optional[float] = None


@dataclass(frozen=True)
class ContextCategory:
    """One row of a context-window breakdown (system prompt, MCP tools, …)."""
    name: str
    tokens: int


@dataclass(frozen=True)
class UsageSnapshot:
    """What a backend knows about the live session, as of now.

    Every field is optional and independently rendered: a backend that reports
    only tokens still produces a useful strip.
    """
    model: Optional[str] = None
    tokens: Optional[TokenCounts] = None
    cost: Optional[Cost] = None
    context_tokens: Optional[int] = None
    context_max: Optional[int] = None
    context_categories: Tuple[ContextCategory, ...] = ()
    quota: Optional[Quota] = None
    carbon: Optional[CarbonFootprint] = None
    num_turns: Optional[int] = None
    duration_api_ms: Optional[int] = None
    session_id: Optional[str] = None

    @property
    def context_percent(self) -> Optional[float]:
        if not self.context_max or self.context_tokens is None:
            return None
        return 100.0 * self.context_tokens / self.context_max


@runtime_checkable
class UsageReportingBackend(Protocol):
    """OPTIONAL companion to `AgentBackend` — implement any subset.

    Never fold these into `AgentBackend`: that protocol describes the *required*
    contract, and backends without usage reporting are still perfectly valid.
    The dock probes each member with `getattr`.
    """

    async def usage_snapshot(self) -> Optional[UsageSnapshot]:
        """Current session usage. May do I/O. Returns None when unavailable."""
        ...

    def effort_values(self) -> Tuple[str, ...]:
        """Effort levels accepted for the CURRENTLY selected model.

        Empty tuple means the backend cannot vary effort. Lives here rather than
        in core because the valid set is a join of two things only the backend
        knows: what its SDK accepts on the wire, and what the model supports.
        """
        ...

    async def set_effort(self, effort: Optional[str]) -> None:
        """Select an effort level. None restores the backend default."""
        ...
```

- [ ] **Step 4: Add the formatters**

Create `SciQLop/components/agents/chat/formatters.py`:

```python
"""Pure display formatters for the session-info strip.

Kept free of Qt so the display rules are testable as plain functions — the
widgets in `info_bar.py` only join and place what `info_segments` returns.
"""
from __future__ import annotations

from typing import List, Optional

from ..backend import CarbonFootprint, Cost, Quota, UsageSnapshot


def fmt_tokens(n: Optional[int]) -> str:
    if n is None:
        return ""
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}k"
    return f"{n / 1_000_000:.2f}M"


def fmt_cost(cost: Optional[Cost]) -> str:
    if cost is None:
        return ""
    if cost.unit == "USD":
        return f"${cost.amount:.2f}"
    return f"{cost.amount:.2f} {cost.unit}"


def fmt_duration(ms: Optional[int]) -> str:
    if not ms:
        return ""
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds) // 60}m {int(seconds) % 60}s"


def fmt_quota(quota: Optional[Quota]) -> str:
    if quota is None:
        return ""
    if quota.unlimited:
        return f"unlimited {quota.label}"
    if quota.percent_remaining is not None:
        return f"{quota.percent_remaining:.0f}% {quota.label} left"
    if quota.remaining is not None:
        return f"{fmt_tokens(int(quota.remaining))} {quota.label} left"
    return ""


def fmt_carbon(carbon: Optional[CarbonFootprint]) -> str:
    if carbon is None:
        return ""
    if carbon.kg_co2eq is not None:
        grams = carbon.kg_co2eq * 1000.0
        if grams < 1000:
            return f"{grams:.1f} gCO₂eq"
        return f"{carbon.kg_co2eq:.2f} kgCO₂eq"
    if carbon.kwh is not None:
        return f"{carbon.kwh * 1000.0:.1f} Wh"
    return ""


def info_segments(
    snapshot: Optional[UsageSnapshot], effort: Optional[str] = None
) -> List[str]:
    """The strip's segments, in display order. Absent data yields no segment."""
    if snapshot is None:
        return []
    segments: List[str] = []
    if snapshot.model:
        segments.append(snapshot.model)
    if effort:
        segments.append(effort)
    total = snapshot.tokens.total if snapshot.tokens else None
    if total is not None:
        segments.append(fmt_tokens(total))
    percent = snapshot.context_percent
    if percent is not None:
        segments.append(f"{percent:.0f}%")
    for render, value in (
        (fmt_cost, snapshot.cost),
        (fmt_quota, snapshot.quota),
        (fmt_carbon, snapshot.carbon),
    ):
        text = render(value)
        if text:
            segments.append(text)
    return segments
```

- [ ] **Step 5: Export the new types**

In `SciQLop/components/agents/backend.py`, confirm the `typing` import line includes `Tuple` and `runtime_checkable` (it already imports both). In `SciQLop/components/agents/__init__.py`, extend the `from .backend import (...)` block and `__all__` with, in alphabetical position: `CarbonFootprint`, `ContextCategory`, `Cost`, `Quota`, `TokenCounts`, `UsageReportingBackend`, `UsageSnapshot`.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest --no-xvfb tests/test_agent_usage_types.py -v`
Expected: PASS — 10 passed

- [ ] **Step 7: Commit**

```bash
git add SciQLop/components/agents/backend.py \
        SciQLop/components/agents/chat/formatters.py \
        SciQLop/components/agents/__init__.py \
        tests/test_agent_usage_types.py
git commit -m "feat(agents): usage snapshot types and display formatters"
```

---

### Task 2: models.dev model capability lookup

Supplies context limits, pricing and **per-model** effort value lists. This module exists because effort values differ per model, not per provider — `claude-sonnet-4.6` accepts `low|medium|high|max`, `gemini-3.5-flash` accepts `minimal|low|medium|high`, `gpt-5.6-sol` accepts `none|low|medium|high|xhigh|max`. A hardcoded list would offer `xhigh` to a model that rejects it.

**Files:**
- Create: `SciQLop/components/agents/model_capabilities.py`
- Test: `tests/test_agent_model_capabilities.py`

**Interfaces:**
- Consumes: `SciQLop.components.storage.cache_dir`.
- Produces: `ModelCapabilities`, `capabilities_for(provider, model, registry=None)`, `load_registry()`, `registry_is_stale()`, `refresh_registry(timeout=20.0)`, `ensure_registry_fresh()`, `registry_path()`, `REGISTRY_URL`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_model_capabilities.py`:

```python
"""models.dev capability lookup.

Every test injects a literal registry document — this module must never reach
the network during tests, and `capabilities_for` takes `registry=` precisely so
no monkeypatching is needed.
"""
import pytest

REGISTRY = {
    "anthropic": {
        "models": {
            "claude-sonnet-4-6": {
                "id": "claude-sonnet-4-6",
                "reasoning_options": [
                    {"type": "effort", "values": ["low", "medium", "high", "max"]},
                    {"type": "budget_tokens", "min": 1024},
                ],
                "limit": {"context": 1_000_000, "output": 128_000},
                "cost": {"input": 3, "output": 15, "cache_read": 0.3},
            }
        }
    },
    "github-copilot": {
        "models": {
            "gemini-3.5-flash": {
                "id": "gemini-3.5-flash",
                "reasoning_options": [
                    {"type": "effort", "values": ["minimal", "low", "medium", "high"]}
                ],
                "limit": {"context": 200_000},
                "cost": {"input": 1.5, "output": 9},
            },
            "no-reasoning-model": {"id": "no-reasoning-model", "limit": {"context": 8_000}},
        }
    },
}


def test_parses_limits_cost_and_effort():
    from SciQLop.components.agents.model_capabilities import capabilities_for

    caps = capabilities_for("anthropic", "claude-sonnet-4-6", registry=REGISTRY)
    assert caps.context_limit == 1_000_000
    assert caps.output_limit == 128_000
    assert caps.effort_values == ("low", "medium", "high", "max")
    assert caps.cost_input == 3
    assert caps.cost_output == 15
    assert caps.cost_cache_read == 0.3


def test_effort_values_are_per_model_not_per_provider():
    from SciQLop.components.agents.model_capabilities import capabilities_for

    gemini = capabilities_for("github-copilot", "gemini-3.5-flash", registry=REGISTRY)
    assert gemini.effort_values == ("minimal", "low", "medium", "high")
    assert "xhigh" not in gemini.effort_values


def test_model_without_reasoning_options_has_no_effort():
    from SciQLop.components.agents.model_capabilities import capabilities_for

    caps = capabilities_for("github-copilot", "no-reasoning-model", registry=REGISTRY)
    assert caps.effort_values == ()
    assert caps.context_limit == 8_000
    assert caps.cost_input is None


def test_strips_trailing_date_suffix_from_model_id():
    from SciQLop.components.agents.model_capabilities import capabilities_for

    # The Claude CLI reports dated ids; models.dev keys are undated.
    caps = capabilities_for("anthropic", "claude-sonnet-4-6-20260217", registry=REGISTRY)
    assert caps is not None
    assert caps.context_limit == 1_000_000


def test_matches_dotted_version_against_dashed_key():
    from SciQLop.components.agents.model_capabilities import capabilities_for

    # anthropic keys use "4-6"; github-copilot uses "4.6". Accept either.
    caps = capabilities_for("anthropic", "claude-sonnet-4.6", registry=REGISTRY)
    assert caps is not None


def test_unknown_provider_or_model_returns_none():
    from SciQLop.components.agents.model_capabilities import capabilities_for

    assert capabilities_for("nope", "claude-sonnet-4-6", registry=REGISTRY) is None
    assert capabilities_for("anthropic", "nope", registry=REGISTRY) is None
    assert capabilities_for("anthropic", "", registry=REGISTRY) is None


def test_offline_is_a_supported_state():
    from SciQLop.components.agents.model_capabilities import capabilities_for

    # An empty registry is what load_registry() returns with no cache on disk.
    assert capabilities_for("anthropic", "claude-sonnet-4-6", registry={}) is None


def test_registry_path_lives_under_the_redirected_cache_dir(tmp_path, monkeypatch):
    from SciQLop.components.agents.model_capabilities import registry_path

    path = registry_path()
    # conftest redirects XDG_CACHE_HOME; going through storage.cache_dir means
    # tests never touch the developer's real ~/.cache/sciqlop.
    assert "sciqlop" in str(path).lower()
    assert path.name == "models_dev.json"


def test_missing_cache_is_stale_and_loads_empty():
    from SciQLop.components.agents.model_capabilities import (
        load_registry, registry_is_stale, registry_path)

    p = registry_path()
    if p.exists():
        p.unlink()
    assert registry_is_stale() is True
    assert load_registry() == {}


def test_corrupt_cache_loads_empty_rather_than_raising():
    from SciQLop.components.agents.model_capabilities import load_registry, registry_path

    registry_path().write_text("{ this is not json")
    assert load_registry() == {}
    registry_path().unlink()


def test_ensure_registry_fresh_skips_the_fetch_when_cache_is_current(monkeypatch):
    import asyncio
    import json

    from SciQLop.components.agents import model_capabilities as mc

    mc.registry_path().write_text(json.dumps({"anthropic": {"models": {}}}))
    calls = []
    monkeypatch.setattr(mc, "refresh_registry", lambda **kw: calls.append(True))

    asyncio.run(mc.ensure_registry_fresh())
    assert calls == []          # a fresh cache must not trigger a network call
    mc.registry_path().unlink()


def test_ensure_registry_fresh_fetches_off_the_event_loop_when_stale(monkeypatch):
    import asyncio
    import threading

    from SciQLop.components.agents import model_capabilities as mc

    if mc.registry_path().exists():
        mc.registry_path().unlink()
    threads = []
    monkeypatch.setattr(
        mc, "refresh_registry",
        lambda **kw: threads.append(threading.current_thread()) or True)

    asyncio.run(mc.ensure_registry_fresh())
    assert len(threads) == 1
    # Must not block the qasync/GUI loop: the blocking fetch runs in a worker.
    assert threads[0] is not threading.main_thread()


def test_ensure_registry_fresh_never_raises(monkeypatch):
    import asyncio

    from SciQLop.components.agents import model_capabilities as mc

    if mc.registry_path().exists():
        mc.registry_path().unlink()

    def boom(**kw):
        raise OSError("no network")

    monkeypatch.setattr(mc, "refresh_registry", boom)
    asyncio.run(mc.ensure_registry_fresh())     # offline is a supported state
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --no-xvfb tests/test_agent_model_capabilities.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'SciQLop.components.agents.model_capabilities'`

- [ ] **Step 3: Write the implementation**

Create `SciQLop/components/agents/model_capabilities.py`:

```python
"""Per-model capability lookup backed by the models.dev registry.

models.dev is a public, unauthenticated registry (175 providers, ~5900 models)
covering `anthropic`, `github-copilot` and `opencode`. It supplies the three
things that would otherwise be hardcoded per backend: context limits, token
pricing, and — critically — the *per-model* set of accepted effort levels.

Albert (OpenGateLLM) is absent from models.dev and does not need it: its own
`/v1/models` already returns `max_context_length` and `Model.costs`.

Offline is a supported state: every function degrades to empty/None rather than
raising, and callers render fewer segments.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple

from SciQLop.components.storage import cache_dir

REGISTRY_URL = "https://models.dev/api.json"
_MAX_AGE_SECONDS = 7 * 24 * 3600


@dataclass(frozen=True)
class ModelCapabilities:
    context_limit: Optional[int] = None
    output_limit: Optional[int] = None
    effort_values: Tuple[str, ...] = ()
    cost_input: Optional[float] = None       # USD per 1M tokens
    cost_output: Optional[float] = None
    cost_cache_read: Optional[float] = None


def registry_path() -> Path:
    # Must go through cache_dir(): tests redirect XDG_CACHE_HOME, and a
    # hand-built path would read the developer's real cache during tests.
    return cache_dir("agents") / "models_dev.json"


def load_registry() -> dict:
    try:
        data = json.loads(registry_path().read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def registry_is_stale() -> bool:
    path = registry_path()
    if not path.exists():
        return True
    return (time.time() - path.stat().st_mtime) > _MAX_AGE_SECONDS


def refresh_registry(timeout: float = 20.0) -> bool:
    """Fetch and cache the registry. BLOCKING — never call on the GUI thread.

    Returns True on success. Any failure leaves the previous cache untouched.
    """
    import httpx

    try:
        response = httpx.get(REGISTRY_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload:
            return False
    except Exception:
        return False

    target = registry_path()
    tmp = target.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, target)     # atomic — a torn file would poison the cache
    except OSError:
        return False
    return True


def _candidate_keys(model: str) -> Iterator[str]:
    """models.dev keys, most specific first.

    Two mismatches to absorb: the Claude CLI reports dated ids
    (`claude-sonnet-4-6-20260217`) while models.dev keys are undated, and
    version separators differ between providers (`4-6` under `anthropic`,
    `4.6` under `github-copilot`).
    """
    seen = set()
    undated = re.sub(r"-\d{8}$", "", model)
    for base in (model, undated):
        for variant in (base,
                        re.sub(r"(\d)-(\d)", r"\1.\2", base),
                        re.sub(r"(\d)\.(\d)", r"\1-\2", base)):
            if variant and variant not in seen:
                seen.add(variant)
                yield variant


def _parse(entry: dict) -> ModelCapabilities:
    limit = entry.get("limit") or {}
    cost = entry.get("cost") or {}
    effort: Tuple[str, ...] = ()
    for option in entry.get("reasoning_options") or []:
        if isinstance(option, dict) and option.get("type") == "effort":
            effort = tuple(option.get("values") or ())
            break
    return ModelCapabilities(
        context_limit=limit.get("context"),
        output_limit=limit.get("output"),
        effort_values=effort,
        cost_input=cost.get("input"),
        cost_output=cost.get("output"),
        cost_cache_read=cost.get("cache_read"),
    )


def capabilities_for(
    provider: str, model: str, registry: Optional[dict] = None
) -> Optional[ModelCapabilities]:
    """Capabilities for one model, or None when unknown/offline.

    `registry` is injectable so tests never touch the network or the cache.
    """
    if not provider or not model:
        return None
    document = registry if registry is not None else load_registry()
    models = (document.get(provider) or {}).get("models") or {}
    for key in _candidate_keys(model):
        entry = models.get(key)
        if isinstance(entry, dict):
            return _parse(entry)
    return None


async def ensure_registry_fresh() -> None:
    """Populate/refresh the cache if stale. Safe to call from the qasync loop.

    Without this nothing ever writes the cache, so `capabilities_for` would
    always return None and every effort selector would stay hidden. The blocking
    fetch is pushed to a worker thread, and every failure is swallowed — offline
    is a supported state.
    """
    import asyncio

    if not registry_is_stale():
        return
    try:
        await asyncio.to_thread(refresh_registry)
    except Exception:
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --no-xvfb tests/test_agent_model_capabilities.py -v`
Expected: PASS — 13 passed

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/agents/model_capabilities.py \
        tests/test_agent_model_capabilities.py
git commit -m "feat(agents): models.dev per-model capability lookup"
```

---

### Task 3: TokenBar and SessionInfoBar

The footer strip. Display logic already lives in `info_segments`, so this task is thin: join the segments into a label, show a meter when a context limit is known, hide the whole widget when there is nothing at all.

**Files:**
- Create: `SciQLop/components/agents/chat/info_bar.py`
- Test: `tests/test_agent_info_bar.py`

**Interfaces:**
- Consumes: `info_segments` (Task 1), `UsageSnapshot` (Task 1).
- Produces: `TokenBar(QProgressBar)`, `SessionInfoBar(QWidget)` with `set_snapshot(snapshot)`, `set_effort(effort)`, `snapshot` property, and a `details_requested` signal.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_info_bar.py`:

```python
"""The session-info strip renders per field and hides when there is nothing."""
import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


def test_hidden_when_snapshot_is_none(qtbot):
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(None)
    assert bar.isHidden()


def test_hidden_when_snapshot_carries_nothing(qtbot):
    from SciQLop.components.agents.backend import UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot())
    assert bar.isHidden()


def test_tokens_only_backend_still_shows_a_segment(qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot(tokens=TokenCounts(input=1000, output=200)))
    assert not bar.isHidden()
    assert bar.text() == "1.2k"


def test_context_meter_appears_only_with_a_known_limit(qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)

    bar.set_snapshot(UsageSnapshot(tokens=TokenCounts(input=10)))
    assert bar.meter.isHidden()

    bar.set_snapshot(UsageSnapshot(context_tokens=50_000, context_max=200_000))
    assert not bar.meter.isHidden()
    assert bar.meter.value() == 25


def test_effort_is_shown_and_updated_independently_of_the_snapshot(qtbot):
    from SciQLop.components.agents.backend import UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot(model="Opus 4.5"))
    assert bar.text() == "Opus 4.5"

    bar.set_effort("high")
    assert bar.text() == "Opus 4.5 · high"


def test_details_button_emits_details_requested(qtbot):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot(
        context_tokens=100, context_max=200,
        context_categories=(ContextCategory(name="System prompt", tokens=100),),
    ))
    with qtbot.waitSignal(bar.details_requested, timeout=1000):
        bar.details_button.click()


def test_details_button_hidden_without_a_breakdown(qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot(tokens=TokenCounts(input=10)))
    assert bar.details_button.isHidden()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --no-xvfb tests/test_agent_info_bar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'SciQLop.components.agents.chat.info_bar'`

- [ ] **Step 3: Write the implementation**

Create `SciQLop/components/agents/chat/info_bar.py`:

```python
"""Session-info strip shown under the chat input.

Renders whatever the backend reports and nothing more: a backend supplying only
token counts gets one segment, one supplying context limits also gets a meter.
The whole widget hides when there is nothing to say.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QToolButton,
    QWidget,
)

from ..backend import UsageSnapshot
from .formatters import info_segments


class TokenBar(QProgressBar):
    """A slim, textless meter. Height derives from the font's x-height so it
    scales with the UI instead of using a hardcoded pixel size."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setRange(0, 100)
        self.setFixedHeight(max(4, int(self.fontMetrics().xHeight())))


class SessionInfoBar(QWidget):
    details_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot: Optional[UsageSnapshot] = None
        self._effort: Optional[str] = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("", self)
        self._label.setStyleSheet("color: gray;")
        row.addWidget(self._label)

        self.meter = TokenBar(self)
        self.meter.setMaximumWidth(80)
        row.addWidget(self.meter)

        self.details_button = QToolButton(self)
        self.details_button.setText("ⓘ")
        self.details_button.setAutoRaise(True)
        self.details_button.setToolTip("Show the context breakdown for this session.")
        self.details_button.clicked.connect(self.details_requested)
        row.addWidget(self.details_button)

        row.addStretch(1)
        self._render()

    @property
    def snapshot(self) -> Optional[UsageSnapshot]:
        return self._snapshot

    def text(self) -> str:
        """The joined segment text — the strip's whole textual content."""
        return self._label.text()

    def set_snapshot(self, snapshot: Optional[UsageSnapshot]) -> None:
        self._snapshot = snapshot
        self._render()

    def set_effort(self, effort: Optional[str]) -> None:
        self._effort = effort
        self._render()

    def _render(self) -> None:
        segments = info_segments(self._snapshot, self._effort)
        self._label.setText(" · ".join(segments))

        percent = self._snapshot.context_percent if self._snapshot else None
        self.meter.setVisible(percent is not None)
        if percent is not None:
            self.meter.setValue(int(round(percent)))

        has_breakdown = bool(self._snapshot and self._snapshot.context_categories)
        self.details_button.setVisible(has_breakdown)

        self.setVisible(bool(segments))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --no-xvfb tests/test_agent_info_bar.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/agents/chat/info_bar.py tests/test_agent_info_bar.py
git commit -m "feat(agents): session info strip with per-field rendering"
```

---

### Task 4: ContextBreakdownPopup

The ⓘ detail view — Claude's `/context` categories plus a footer of turns, api duration, cost and carbon.

**Files:**
- Modify: `SciQLop/components/agents/chat/info_bar.py` (append)
- Test: `tests/test_agent_info_bar.py` (append)

**Interfaces:**
- Consumes: `UsageSnapshot`, `ContextCategory`, `fmt_tokens`, `fmt_cost`, `fmt_duration`, `fmt_carbon`, `TokenBar`.
- Produces: `ContextBreakdownPopup(QWidget)` with `set_snapshot(snapshot)`, `category_rows` (list of `(name, tokens_text)` tuples), `footer_text()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_agent_info_bar.py`:

```python
def test_breakdown_popup_lists_categories_largest_first(qtbot):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import ContextBreakdownPopup

    popup = ContextBreakdownPopup()
    qtbot.addWidget(popup)
    popup.set_snapshot(UsageSnapshot(
        context_tokens=168_000, context_max=500_000,
        context_categories=(
            ContextCategory(name="System prompt", tokens=3_100),
            ContextCategory(name="Messages", tokens=127_000),
            ContextCategory(name="MCP tools", tokens=28_400),
        ),
    ))
    assert popup.category_rows == [
        ("Messages", "127.0k"),
        ("MCP tools", "28.4k"),
        ("System prompt", "3.1k"),
    ]


def test_breakdown_popup_footer_joins_available_metrics(qtbot):
    from SciQLop.components.agents.backend import (
        CarbonFootprint, ContextCategory, Cost, UsageSnapshot)
    from SciQLop.components.agents.chat.info_bar import ContextBreakdownPopup

    popup = ContextBreakdownPopup()
    qtbot.addWidget(popup)
    popup.set_snapshot(UsageSnapshot(
        context_categories=(ContextCategory(name="Messages", tokens=10),),
        num_turns=12, duration_api_ms=108_000, cost=Cost(amount=0.42),
        carbon=CarbonFootprint(kg_co2eq=0.0043),
    ))
    assert popup.footer_text() == "12 turns · 1m 48s api · $0.42 · 4.3 gCO₂eq"


def test_breakdown_popup_footer_omits_missing_metrics(qtbot):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import ContextBreakdownPopup

    popup = ContextBreakdownPopup()
    qtbot.addWidget(popup)
    popup.set_snapshot(UsageSnapshot(
        context_categories=(ContextCategory(name="Messages", tokens=10),), num_turns=1))
    assert popup.footer_text() == "1 turn"


def test_breakdown_popup_rebuilds_rows_on_second_snapshot(qtbot):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import ContextBreakdownPopup

    popup = ContextBreakdownPopup()
    qtbot.addWidget(popup)
    popup.set_snapshot(UsageSnapshot(
        context_categories=(ContextCategory(name="Messages", tokens=10),)))
    popup.set_snapshot(UsageSnapshot(
        context_categories=(ContextCategory(name="MCP tools", tokens=20),)))
    assert popup.category_rows == [("MCP tools", "20")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --no-xvfb tests/test_agent_info_bar.py -k breakdown -v`
Expected: FAIL — `ImportError: cannot import name 'ContextBreakdownPopup'`

- [ ] **Step 3: Write the implementation**

Append to `SciQLop/components/agents/chat/info_bar.py`. Extend the existing imports with `QGridLayout`, `QVBoxLayout`, and add `fmt_carbon, fmt_cost, fmt_duration, fmt_tokens` to the `.formatters` import:

```python
class ContextBreakdownPopup(QWidget):
    """Context-window breakdown, opened from the strip's ⓘ button.

    A `Qt.Popup` rather than a dialog so clicking away dismisses it.
    """

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self._snapshot: Optional[UsageSnapshot] = None
        self.category_rows: list[tuple[str, str]] = []

        outer = QVBoxLayout(self)
        self._title = QLabel("", self)
        outer.addWidget(self._title)

        self._grid_host = QWidget(self)
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._grid_host)

        self._footer = QLabel("", self)
        self._footer.setStyleSheet("color: gray;")
        outer.addWidget(self._footer)

    def footer_text(self) -> str:
        return self._footer.text()

    def set_snapshot(self, snapshot: Optional[UsageSnapshot]) -> None:
        self._snapshot = snapshot
        self._render_title()
        self._render_categories()
        self._footer.setText(self._build_footer())

    def _render_title(self) -> None:
        snapshot = self._snapshot
        if snapshot is None or snapshot.context_max is None:
            self._title.setText("Context")
            return
        used = fmt_tokens(snapshot.context_tokens)
        total = fmt_tokens(snapshot.context_max)
        percent = snapshot.context_percent
        suffix = f", {percent:.0f}%" if percent is not None else ""
        self._title.setText(f"Context ({used} / {total}{suffix})")

    def _render_categories(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        categories = self._snapshot.context_categories if self._snapshot else ()
        ordered = sorted(categories, key=lambda c: c.tokens, reverse=True)
        largest = max((c.tokens for c in ordered), default=0)

        self.category_rows = [(c.name, fmt_tokens(c.tokens)) for c in ordered]
        for row, category in enumerate(ordered):
            self._grid.addWidget(QLabel(category.name, self._grid_host), row, 0)
            self._grid.addWidget(
                QLabel(fmt_tokens(category.tokens), self._grid_host), row, 1)
            meter = TokenBar(self._grid_host)
            meter.setValue(int(100 * category.tokens / largest) if largest else 0)
            self._grid.addWidget(meter, row, 2)

    def _build_footer(self) -> str:
        snapshot = self._snapshot
        if snapshot is None:
            return ""
        parts: list[str] = []
        if snapshot.num_turns:
            parts.append(
                f"{snapshot.num_turns} turn"
                + ("s" if snapshot.num_turns != 1 else ""))
        duration = fmt_duration(snapshot.duration_api_ms)
        if duration:
            parts.append(f"{duration} api")
        for text in (fmt_cost(snapshot.cost), fmt_carbon(snapshot.carbon)):
            if text:
                parts.append(text)
        return " · ".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --no-xvfb tests/test_agent_info_bar.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/agents/chat/info_bar.py tests/test_agent_info_bar.py
git commit -m "feat(agents): context breakdown popup for the session info strip"
```

---

### Task 5: AgentSettingsPopup and per-backend effort persistence

Moves the model / effort / activity / allow-writes / export controls out of the header. A `Qt.Popup` widget rather than a `QMenu` with `QWidgetAction`s, because combos inside menus swallow clicks and close the menu on interaction.

**Files:**
- Create: `SciQLop/components/agents/chat/settings_popup.py`
- Modify: `SciQLop/components/agents/settings.py` (add `effort` to `AgentChatSettings`)
- Test: `tests/test_agent_settings_popup.py`

**Interfaces:**
- Consumes: `AgentChatSettings` (Task 5's own change).
- Produces: `AgentSettingsPopup(QWidget)` owning `model_combo`, `effort_combo`, `verbosity_combo`, `writes_toggle`, `export_button`; methods `set_effort_values(values, current)`, `current_effort()`; signals `effort_changed(str)`, `export_requested()`. `AgentChatSettings.effort: Dict[str, str]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_settings_popup.py`:

```python
"""The settings popup owns every control that used to crowd the chat header."""
import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


def test_popup_owns_the_relocated_controls(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    for name in ("model_combo", "effort_combo", "verbosity_combo",
                 "writes_toggle", "export_button"):
        widget = getattr(popup, name)
        assert widget is not None
        assert widget.parent() is popup


def test_effort_row_hidden_when_backend_reports_no_values(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    popup.set_effort_values((), None)
    assert not popup.is_effort_row_visible()


def test_effort_row_lists_exactly_the_models_values(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    popup.set_effort_values(("minimal", "low", "medium", "high"), None)
    assert popup.is_effort_row_visible()
    labels = [popup.effort_combo.itemText(i)
              for i in range(popup.effort_combo.count())]
    assert labels == ["Default", "minimal", "low", "medium", "high"]
    assert popup.current_effort() is None      # "Default" means no override


def test_selecting_an_effort_emits_and_reports_it(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    popup.set_effort_values(("low", "medium", "high"), None)
    with qtbot.waitSignal(popup.effort_changed, timeout=1000) as sig:
        popup.effort_combo.setCurrentIndex(3)   # 0=Default, so 3 == "high"
    assert sig.args == ["high"]
    assert popup.current_effort() == "high"


def test_restoring_a_value_absent_from_this_model_falls_back_to_default(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    # "xhigh" is valid for Claude but not for this Gemini-style model.
    popup.set_effort_values(("minimal", "low", "medium", "high"), "xhigh")
    assert popup.current_effort() is None


def test_export_button_emits_export_requested(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    with qtbot.waitSignal(popup.export_requested, timeout=1000):
        popup.export_button.click()


def test_effort_setting_is_per_backend():
    from SciQLop.components.agents.settings import AgentChatSettings

    settings = AgentChatSettings()
    assert settings.effort == {}
    settings.effort = {"Claude": "high", "GitHub Copilot": "minimal"}
    assert settings.effort["Claude"] == "high"
    assert settings.effort["GitHub Copilot"] == "minimal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --no-xvfb tests/test_agent_settings_popup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'SciQLop.components.agents.chat.settings_popup'`

- [ ] **Step 3: Add the per-backend effort setting**

In `SciQLop/components/agents/settings.py`, add to `AgentChatSettings` (keeping the existing fields):

```python
    effort: Dict[str, str] = Field(
        default_factory=dict,
        description="Selected reasoning effort per agent backend, keyed by "
                    "backend display name. Empty string = backend default.",
        json_schema_extra={"widget": "hidden"},
    )
```

Per-backend rather than a single string because the valid value sets differ:
`xhigh` is meaningful to Claude and rejected by a Copilot-hosted Gemini. `Dict` is
already imported at the top of the file.

- [ ] **Step 4: Write the popup**

Create `SciQLop/components/agents/chat/settings_popup.py`:

```python
"""Settings popup for the agent chat dock.

Holds every control that previously crowded the dock header: model, effort,
activity verbosity, allow-writes, export. A `Qt.Popup` widget rather than a
`QMenu` with `QWidgetAction`s — combos inside menus swallow clicks and close the
menu on interaction. Click-away dismissal comes free with the flag.
"""
from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_DEFAULT_LABEL = "Default"


class AgentSettingsPopup(QWidget):
    effort_changed = Signal(str)
    export_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)

        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)
        self._form = form

        self.model_combo = QComboBox(self)
        self.model_combo.setToolTip("Which model the backend should use.")
        form.addRow("Model", self.model_combo)

        self.effort_combo = QComboBox(self)
        self.effort_combo.setToolTip(
            "How much reasoning effort the model should spend. "
            "Available levels depend on the selected model.")
        self.effort_combo.currentIndexChanged.connect(self._on_effort_index_changed)
        form.addRow("Effort", self.effort_combo)

        self.verbosity_combo = QComboBox(self)
        self.verbosity_combo.addItems(
            ["Activity: minimal", "Activity: + inputs", "Activity: + results"])
        self.verbosity_combo.setToolTip(
            "How much of the agent's tool activity to show in the chat.")
        form.addRow("Activity", self.verbosity_combo)

        self.writes_toggle = QCheckBox("Allow write actions", self)
        self.writes_toggle.setToolTip(
            "When enabled, the agent can modify SciQLop state "
            "(set time range, create panels, exec Python, edit notebooks).")
        form.addRow("", self.writes_toggle)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(separator)

        self.export_button = QPushButton("Export transcript ⤓", self)
        self.export_button.setToolTip("Save this transcript as a Markdown file.")
        self.export_button.clicked.connect(self.export_requested)
        outer.addWidget(self.export_button)

        self.set_effort_values((), None)

    def is_effort_row_visible(self) -> bool:
        return self._form.isRowVisible(self.effort_combo)

    def current_effort(self) -> Optional[str]:
        """The selected level, or None when "Default" (no override) is chosen."""
        return self.effort_combo.currentData()

    def set_effort_values(
        self, values: Sequence[str], current: Optional[str]
    ) -> None:
        """Repopulate for the selected model. Empty `values` hides the row.

        A `current` absent from `values` falls back to Default — the persisted
        choice is left alone by the caller so it still applies if the user
        returns to a model that accepts it.
        """
        self.effort_combo.blockSignals(True)
        self.effort_combo.clear()
        self.effort_combo.addItem(_DEFAULT_LABEL, None)
        for value in values:
            self.effort_combo.addItem(value, value)
        if current and current in values:
            self.effort_combo.setCurrentIndex(list(values).index(current) + 1)
        else:
            self.effort_combo.setCurrentIndex(0)
        self.effort_combo.blockSignals(False)
        self._form.setRowVisible(self.effort_combo, bool(values))

    def _on_effort_index_changed(self, _index: int) -> None:
        self.effort_changed.emit(self.effort_combo.currentData() or "")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest --no-xvfb tests/test_agent_settings_popup.py -v`
Expected: PASS — 7 passed

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/agents/chat/settings_popup.py \
        SciQLop/components/agents/settings.py \
        tests/test_agent_settings_popup.py
git commit -m "feat(agents): settings popup with per-model effort selector"
```

---

### Task 6: Usage refresh coordinator and dock rewiring

The dock's header shrinks to four controls, the popup and strip get wired in, and refresh is coordinated by a small class that is testable with fakes — deliberately kept out of the widget so this task does not need a full `main_window` fixture to prove its logic.

**Files:**
- Create: `SciQLop/components/agents/chat/usage_refresh.py`
- Modify: `SciQLop/components/agents/chat_dock.py:77-184` (`_build_ui`), plus `_on_export`, `_on_verbosity_changed`, `_init_tool_verbosity`, `_on_model_changed`, `_bind_to_session`, `_run_turn`
- Test: `tests/test_agent_usage_refresh.py`

**Interfaces:**
- Consumes: `UsageSnapshot` (Task 1), `SessionInfoBar` / `ContextBreakdownPopup` (Tasks 3–4), `AgentSettingsPopup` (Task 5).
- Produces: `UsageRefresher(get_backend, apply_snapshot)` with `async refresh()` and `in_flight` property.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_usage_refresh.py`:

```python
"""Usage refresh must never disturb a turn, and never pile up concurrent calls."""
import asyncio

import pytest


class _Backend:
    def __init__(self, snapshot=None, error=None, delay=0.0):
        self._snapshot = snapshot
        self._error = error
        self._delay = delay
        self.calls = 0

    async def usage_snapshot(self):
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return self._snapshot


def _refresher(backend, applied):
    from SciQLop.components.agents.chat.usage_refresh import UsageRefresher

    return UsageRefresher(lambda: backend, applied.append)


def test_refresh_applies_the_snapshot():
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot

    snapshot = UsageSnapshot(tokens=TokenCounts(input=10))
    backend, applied = _Backend(snapshot=snapshot), []
    asyncio.run(_refresher(backend, applied).refresh())
    assert applied == [snapshot]


def test_backend_without_the_hook_applies_none():
    class Bare:
        pass

    applied = []
    asyncio.run(_refresher(Bare(), applied).refresh())
    assert applied == [None]


def test_missing_backend_applies_none():
    from SciQLop.components.agents.chat.usage_refresh import UsageRefresher

    applied = []
    asyncio.run(UsageRefresher(lambda: None, applied.append).refresh())
    assert applied == [None]


def test_a_raising_backend_is_swallowed_and_applies_none():
    backend, applied = _Backend(error=RuntimeError("CLI gone")), []
    asyncio.run(_refresher(backend, applied).refresh())      # must not raise
    assert applied == [None]


def test_concurrent_refreshes_collapse_to_one_call():
    from SciQLop.components.agents.backend import UsageSnapshot

    backend = _Backend(snapshot=UsageSnapshot(model="m"), delay=0.05)
    applied = []
    refresher = _refresher(backend, applied)

    async def run():
        await asyncio.gather(*(refresher.refresh() for _ in range(4)))

    asyncio.run(run())
    assert backend.calls == 1
    assert len(applied) == 1


def test_in_flight_clears_after_completion():
    from SciQLop.components.agents.backend import UsageSnapshot

    backend, applied = _Backend(snapshot=UsageSnapshot(model="m")), []
    refresher = _refresher(backend, applied)
    asyncio.run(refresher.refresh())
    assert refresher.in_flight is False
    asyncio.run(refresher.refresh())
    assert backend.calls == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --no-xvfb tests/test_agent_usage_refresh.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'SciQLop.components.agents.chat.usage_refresh'`

- [ ] **Step 3: Write the refresher**

Create `SciQLop/components/agents/chat/usage_refresh.py`:

```python
"""Coordinates session-usage refreshes for the chat dock.

Separate from the widget so the two rules that matter — a usage failure never
surfaces as a chat error, and overlapping requests collapse to one — are
testable without a Qt dock.
"""
from __future__ import annotations

from typing import Callable, Optional

from ..backend import UsageSnapshot

GetBackend = Callable[[], Optional[object]]
ApplySnapshot = Callable[[Optional[UsageSnapshot]], None]


class UsageRefresher:
    def __init__(self, get_backend: GetBackend, apply_snapshot: ApplySnapshot):
        self._get_backend = get_backend
        self._apply = apply_snapshot
        self._in_flight = False

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    async def refresh(self) -> None:
        """Fetch and apply. Never raises: a backend that cannot report usage
        must not turn into a chat error."""
        if self._in_flight:
            return
        self._in_flight = True
        try:
            self._apply(await self._fetch())
        finally:
            self._in_flight = False

    async def _fetch(self) -> Optional[UsageSnapshot]:
        backend = self._get_backend()
        hook = getattr(backend, "usage_snapshot", None)
        if hook is None:
            return None
        try:
            return await hook()
        except Exception:
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --no-xvfb tests/test_agent_usage_refresh.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Rewire the dock header**

In `SciQLop/components/agents/chat_dock.py`, replace the header construction in `_build_ui` (currently lines 80–126) with:

```python
        header = QHBoxLayout()
        self._reset_btn = QPushButton("New session")
        self._reset_btn.clicked.connect(self._on_reset)
        header.addWidget(self._reset_btn)

        self._interactive: tuple = ()

        self._backend_combo = QComboBox()
        self._backend_combo.setToolTip("Select which agent backend to chat with.")
        self._backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        header.addWidget(self._backend_combo)

        self._sessions_toggle = QPushButton("☰ Sessions")
        self._sessions_toggle.setCheckable(True)
        self._sessions_toggle.setToolTip("Show or hide the session list.")
        self._sessions_toggle.toggled.connect(self._on_sessions_toggled)
        header.addWidget(self._sessions_toggle)

        self._settings_popup = AgentSettingsPopup(self)
        self._settings_btn = QPushButton(get_icon("settings"), "")
        self._settings_btn.setToolTip("Model, effort, activity and export options.")
        self._settings_btn.clicked.connect(self._show_settings_popup)
        header.addWidget(self._settings_btn)

        # Aliases so the pre-existing wiring and `_interactive` keep working
        # unchanged now that the popup owns construction.
        self._model_combo = self._settings_popup.model_combo
        self._verbosity_combo = self._settings_popup.verbosity_combo
        self._writes_toggle = self._settings_popup.writes_toggle
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        self._verbosity_combo.currentIndexChanged.connect(self._on_verbosity_changed)
        self._writes_toggle.stateChanged.connect(self._on_writes_toggled)
        self._settings_popup.export_requested.connect(self._on_export)
        self._settings_popup.effort_changed.connect(self._on_effort_changed)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray;")
        header.addWidget(self._status_label, 1)
        layout.addLayout(header)
```

Add the import at the top of the file:

```python
from .chat.info_bar import ContextBreakdownPopup, SessionInfoBar
from .chat.settings_popup import AgentSettingsPopup
from .chat.usage_refresh import UsageRefresher
```

- [ ] **Step 6: Add the strip below the input**

The input panel currently has a single horizontal layout (`input_row`) holding the
text box and the Send/Stop buttons. The strip goes underneath it, so the panel needs
a vertical layout wrapping that row. Replace the whole input-panel block in
`_build_ui` — currently lines 135–150, from `input_panel = QWidget(self._splitter)`
through `self._splitter.addWidget(input_panel)` — with:

```python
        input_panel = QWidget(self._splitter)
        input_column = QVBoxLayout(input_panel)
        input_column.setContentsMargins(0, 0, 0, 0)

        input_row_host = QWidget(input_panel)
        input_row = QHBoxLayout(input_row_host)
        input_row.setContentsMargins(0, 0, 0, 0)

        self._input = ChatInput(self._tempdir / "pasted", input_row_host)
        self._input.setMinimumHeight(60)
        input_row.addWidget(self._input, 1)

        self._send_btn = QPushButton("Send", input_row_host)
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        self._stop_btn = QPushButton("Stop", input_row_host)
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._on_stop)
        input_row.addWidget(self._stop_btn)

        input_column.addWidget(input_row_host)

        self._info_bar = SessionInfoBar(input_panel)
        self._info_bar.details_requested.connect(self._show_context_breakdown)
        input_column.addWidget(self._info_bar)

        self._splitter.addWidget(input_panel)
```

Note the `ChatInput` and button parents change from `input_panel` to
`input_row_host`, since that is now the widget owning the horizontal row. The
splitter sizes below (`setSizes([400, 90])`) stay as they are — the strip hides
itself when empty, so it costs no height until a backend reports something.

- [ ] **Step 7: Add the popup, breakdown and refresh methods**

Add to `AgentChatDock`, after `_set_status`:

```python
    def _show_settings_popup(self) -> None:
        origin = self._settings_btn.mapToGlobal(
            self._settings_btn.rect().bottomLeft())
        self._settings_popup.move(origin)
        self._settings_popup.show()

    def _show_context_breakdown(self) -> None:
        if self._breakdown_popup is None:
            self._breakdown_popup = ContextBreakdownPopup(self)
        self._breakdown_popup.set_snapshot(self._info_bar.snapshot)
        origin = self._info_bar.details_button.mapToGlobal(
            self._info_bar.details_button.rect().topLeft())
        self._breakdown_popup.move(origin)
        self._breakdown_popup.show()
        self._spawn(self._usage_refresher.refresh())

    def _on_effort_changed(self, effort: str) -> None:
        backend = self._current_backend()
        if backend is None:
            return
        with AgentChatSettings() as cfg:
            cfg.effort = {**cfg.effort, backend.display_name: effort}
        self._info_bar.set_effort(effort or None)
        setter = getattr(backend, "set_effort", None)
        if setter is not None:
            self._spawn(setter(effort or None))

    def _populate_effort(self, backend) -> None:
        values = ()
        reader = getattr(backend, "effort_values", None)
        if reader is not None:
            try:
                values = reader()
            except Exception:
                values = ()
        stored = AgentChatSettings().effort.get(backend.display_name) or None
        self._settings_popup.set_effort_values(values, stored)
        self._info_bar.set_effort(self._settings_popup.current_effort())
```

In `__init__`, before `self._build_ui()`, add:

```python
        self._breakdown_popup: Optional[ContextBreakdownPopup] = None
        self._usage_refresher = UsageRefresher(
            self._current_backend, self._apply_usage_snapshot)
```

and after `_build_ui`:

```python
    def _apply_usage_snapshot(self, snapshot) -> None:
        self._info_bar.set_snapshot(snapshot)
```

- [ ] **Step 8: Hook the refresh points**

In `_bind_to_session`, after `self._populate_models(be)`, add:

```python
        self._spawn(self._refresh_capabilities_then_effort(be))
        self._spawn(self._usage_refresher.refresh())
```

and add the coroutine that populates the models.dev cache before reading effort
values off it — without this nothing ever writes the cache, so `capabilities_for`
would always return `None` and effort would silently fall back to the unnarrowed
SDK set forever:

```python
    async def _refresh_capabilities_then_effort(self, backend) -> None:
        from .model_capabilities import ensure_registry_fresh

        await ensure_registry_fresh()
        self._populate_effort(backend)
```

In `_on_model_changed`, after the existing `self._set_status(...)` line, add:

```python
        self._populate_effort(backend)
```

In `_run_turn`, in the success path immediately after `self._set_status("Ready.")`, add:

```python
            self._spawn(self._usage_refresher.refresh())
```

Add `QVBoxLayout` to the existing `PySide6.QtWidgets` import if not already present
(it is), and `get_icon` is already imported.

- [ ] **Step 9: Run the full agent test suite**

Run: `uv run pytest --no-xvfb tests/ -k agent -v`
Expected: PASS — all previously-passing agent tests still pass, plus the new files.

- [ ] **Step 10: Verify the dock still builds in the real app**

Run: `uv run pytest --no-xvfb tests/test_agent_and_provider_icons.py -v`
Expected: PASS. If this test builds a `SciQLopMainWindow` and hangs rather than
fails, consult `pitfall-mainwindow-fixture-cold-start-hang` — try a second run
before investigating.

- [ ] **Step 11: Commit**

```bash
git add SciQLop/components/agents/chat/usage_refresh.py \
        SciQLop/components/agents/chat_dock.py \
        tests/test_agent_usage_refresh.py
git commit -m "feat(agents): slim chat header, settings popup and info strip wiring"
```

---

### Task 7: Claude backend reports usage

`ResultMessage` currently reaches `_decode_message` and is dropped — the method
returns `blocks` for `AssistantMessage`/`UserMessage` and ignores everything else.
This task captures it and merges it with `get_context_usage()`.

**Files:**
- Modify: `/home/jeandet/Documents/prog/plugins_sciqlop/sciqlop_claude/sciqlop_claude/backend.py`
- Test: `/home/jeandet/Documents/prog/plugins_sciqlop/sciqlop_claude/sciqlop_claude/tests/test_usage_snapshot.py`

**Interfaces:**
- Consumes: `UsageSnapshot`, `TokenCounts`, `Cost`, `ContextCategory` from `SciQLop.components.agents.backend`.
- Produces: `ClaudeBackend.usage_snapshot()`, and module-level pure mappers `result_to_usage(result)` and `context_to_breakdown(payload)` so the mapping is testable without an SDK client.

- [ ] **Step 1: Write the failing test**

Create `.../sciqlop_claude/tests/test_usage_snapshot.py`:

```python
"""ResultMessage and get_context_usage() map into a UsageSnapshot.

Guarded: this plugin's conftest stubs SciQLop with MagicMock in a Qt-less CI
env, and asserting against a MagicMock would pass vacuously. Skip there.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from SciQLop.components.agents import backend as _agents_backend

pytestmark = pytest.mark.skipif(
    isinstance(_agents_backend, MagicMock),
    reason="SciQLop is stubbed in this environment; usage types are not real",
)


def _result(**kwargs):
    base = dict(
        usage={"input_tokens": 1000, "output_tokens": 250,
               "cache_read_input_tokens": 9000, "cache_creation_input_tokens": 40},
        total_cost_usd=0.42, num_turns=12, duration_api_ms=108_000,
        session_id="abc123", model_usage=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_result_message_maps_tokens_cost_and_turns():
    from sciqlop_claude.backend import result_to_usage

    snapshot = result_to_usage(_result())
    assert snapshot.tokens.input == 1000
    assert snapshot.tokens.output == 250
    assert snapshot.tokens.cache_read == 9000
    assert snapshot.tokens.cache_write == 40
    assert snapshot.cost.amount == 0.42
    assert snapshot.cost.unit == "USD"
    assert snapshot.num_turns == 12
    assert snapshot.duration_api_ms == 108_000
    assert snapshot.session_id == "abc123"


def test_canonical_model_is_preferred_for_display():
    from sciqlop_claude.backend import result_to_usage

    snapshot = result_to_usage(_result(
        model_usage={"claude-opus-4-5-20251101": {"canonicalModel": "Opus 4.5"}}))
    assert snapshot.model == "Opus 4.5"


def test_falls_back_to_the_raw_model_key_without_a_canonical_name():
    from sciqlop_claude.backend import result_to_usage

    snapshot = result_to_usage(_result(
        model_usage={"claude-opus-4-5-20251101": {}}))
    assert snapshot.model == "claude-opus-4-5-20251101"


def test_missing_cost_stays_none_rather_than_zero():
    from sciqlop_claude.backend import result_to_usage

    assert result_to_usage(_result(total_cost_usd=None)).cost is None


def test_context_payload_maps_to_categories_and_totals():
    from sciqlop_claude.backend import context_to_breakdown

    tokens, maximum, categories, model = context_to_breakdown({
        "categories": [
            {"name": "System prompt", "tokens": 3100},
            {"name": "Messages", "tokens": 127000},
        ],
        "totalTokens": 168_000,
        "maxTokens": 500_000,
        "model": "Opus 4.5",
    })
    assert tokens == 168_000
    assert maximum == 500_000
    assert model == "Opus 4.5"
    assert [(c.name, c.tokens) for c in categories] == [
        ("System prompt", 3100), ("Messages", 127000)]


def test_context_payload_tolerates_missing_and_malformed_fields():
    from sciqlop_claude.backend import context_to_breakdown

    assert context_to_breakdown({}) == (None, None, (), None)
    assert context_to_breakdown(None) == (None, None, (), None)
    tokens, maximum, categories, _ = context_to_breakdown(
        {"categories": [{"tokens": 5}, "junk", {"name": "ok", "tokens": 7}]})
    assert [(c.name, c.tokens) for c in categories] == [("", 5), ("ok", 7)]


@pytest.mark.asyncio
async def test_usage_snapshot_merges_result_and_context(monkeypatch):
    from sciqlop_claude import backend as mod

    be = object.__new__(mod.ClaudeBackend)
    be._last_result = _result()
    be._client = SimpleNamespace(
        get_context_usage=lambda: _async({"totalTokens": 1, "maxTokens": 2}))

    snapshot = await mod.ClaudeBackend.usage_snapshot(be)
    assert snapshot.cost.amount == 0.42
    assert snapshot.context_tokens == 1
    assert snapshot.context_max == 2


@pytest.mark.asyncio
async def test_usage_snapshot_survives_a_context_call_failure():
    from sciqlop_claude import backend as mod

    async def boom():
        raise RuntimeError("not connected")

    be = object.__new__(mod.ClaudeBackend)
    be._last_result = _result()
    be._client = SimpleNamespace(get_context_usage=boom)

    snapshot = await mod.ClaudeBackend.usage_snapshot(be)
    assert snapshot.cost.amount == 0.42      # result data still reported
    assert snapshot.context_tokens is None


@pytest.mark.asyncio
async def test_usage_snapshot_is_none_before_any_turn():
    from sciqlop_claude import backend as mod

    be = object.__new__(mod.ClaudeBackend)
    be._last_result = None
    be._client = None
    assert await mod.ClaudeBackend.usage_snapshot(be) is None


async def _async(value):
    return value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/jeandet/Documents/prog/plugins_sciqlop && uv run pytest sciqlop_claude/sciqlop_claude/tests/test_usage_snapshot.py -v`
Expected: FAIL — `ImportError: cannot import name 'result_to_usage'`

- [ ] **Step 3: Add the pure mappers**

Add to `sciqlop_claude/backend.py`, after the `_result_summary` helper:

```python
def result_to_usage(result) -> "UsageSnapshot":
    """Map a ResultMessage into a UsageSnapshot. Pure — no client needed."""
    raw = getattr(result, "usage", None) or {}
    tokens = TokenCounts(
        input=raw.get("input_tokens"),
        output=raw.get("output_tokens"),
        cache_read=raw.get("cache_read_input_tokens"),
        cache_write=raw.get("cache_creation_input_tokens"),
    )
    cost_usd = getattr(result, "total_cost_usd", None)
    return UsageSnapshot(
        model=_display_model(result),
        tokens=tokens,
        cost=Cost(amount=cost_usd) if cost_usd is not None else None,
        num_turns=getattr(result, "num_turns", None),
        duration_api_ms=getattr(result, "duration_api_ms", None),
        session_id=getattr(result, "session_id", None),
    )


def _display_model(result) -> Optional[str]:
    """Prefer `model_usage[...].canonicalModel` — a stable resolved name that
    survives provider-specific aliases (claude-agent-sdk >= 0.2.126)."""
    model_usage = getattr(result, "model_usage", None) or {}
    for key, entry in model_usage.items():
        if isinstance(entry, dict) and entry.get("canonicalModel"):
            return entry["canonicalModel"]
        return key
    return None


def context_to_breakdown(payload):
    """Map a get_context_usage() payload into (tokens, max, categories, model)."""
    if not isinstance(payload, dict):
        return None, None, (), None
    categories = tuple(
        ContextCategory(name=str(item.get("name", "")), tokens=int(item.get("tokens", 0)))
        for item in (payload.get("categories") or [])
        if isinstance(item, dict)
    )
    return (payload.get("totalTokens"), payload.get("maxTokens"),
            categories, payload.get("model"))
```

Extend the SciQLop import at the top of the file:

```python
from SciQLop.components.agents.backend import (
    ContextCategory,
    Cost,
    StreamBlock,
    TokenCounts,
    UsageSnapshot,
)
```

- [ ] **Step 4: Capture ResultMessage and add the hook**

In `ClaudeBackend.__init__`, add `self._last_result = None`.

In `ask()`, inside the `async for message in client.receive_response():` loop,
before the `for block in self._decode_message(message):` line:

```python
                if type(message).__name__ == "ResultMessage":
                    self._last_result = message
```

Add the hook method to `ClaudeBackend`:

```python
    async def usage_snapshot(self) -> Optional[UsageSnapshot]:
        """Merge the last ResultMessage with a fresh /context breakdown."""
        if self._last_result is None:
            return None
        snapshot = result_to_usage(self._last_result)
        client = self._client
        if client is None:
            return snapshot
        try:
            tokens, maximum, categories, model = context_to_breakdown(
                await client.get_context_usage())
        except Exception:
            return snapshot
        return replace(
            snapshot,
            context_tokens=tokens,
            context_max=maximum,
            context_categories=categories,
            model=model or snapshot.model,
        )
```

Add `from dataclasses import replace` to the imports.

In `reset()`, add `self._last_result = None` so a new session starts with a clean
strip.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/jeandet/Documents/prog/plugins_sciqlop && uv run pytest sciqlop_claude/sciqlop_claude/tests/ -v`
Expected: PASS — the new file plus all pre-existing `sciqlop_claude` tests.

- [ ] **Step 6: Commit (in the plugins repo)**

```bash
cd /home/jeandet/Documents/prog/plugins_sciqlop
git add sciqlop_claude/sciqlop_claude/backend.py \
        sciqlop_claude/sciqlop_claude/tests/test_usage_snapshot.py
git commit -m "feat(claude): report session usage and context breakdown"
```

---

### Task 8: Claude backend effort selection

`ClaudeAgentOptions.effort` accepts `low|medium|high|xhigh|max`, but there is **no**
`client.set_effort()` — effort only enters at connect time. So `set_effort` stores and
disconnects, and the next turn reconnects with it. For that not to lose the
conversation, the backend must record `ResultMessage.session_id` into `self._resume`.
That also hardens the existing `set_model` error path, which today drops the session
on reconnect.

**Files:**
- Modify: `/home/jeandet/Documents/prog/plugins_sciqlop/sciqlop_claude/sciqlop_claude/backend.py`
- Test: `/home/jeandet/Documents/prog/plugins_sciqlop/sciqlop_claude/sciqlop_claude/tests/test_effort.py`

**Interfaces:**
- Consumes: `capabilities_for` from `SciQLop.components.agents.model_capabilities`; `result_to_usage` (Task 7).
- Produces: `ClaudeBackend.effort_values()`, `ClaudeBackend.set_effort(effort)`, `SDK_EFFORT_LEVELS`.

- [ ] **Step 1: Write the failing test**

Create `.../sciqlop_claude/tests/test_effort.py`:

```python
"""Effort selection: SDK-accepted levels, narrowed per model, applied on reconnect."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from SciQLop.components.agents import backend as _agents_backend

pytestmark = pytest.mark.skipif(
    isinstance(_agents_backend, MagicMock),
    reason="SciQLop is stubbed in this environment",
)


def _backend(model=None):
    from sciqlop_claude import backend as mod

    be = object.__new__(mod.ClaudeBackend)
    be._model = model
    be._effort = None
    be._client = None
    be._resume = None
    be._lock = asyncio.Lock()
    be._slash_cache = None
    return be


def test_effort_values_default_to_the_full_sdk_set():
    from sciqlop_claude.backend import SDK_EFFORT_LEVELS

    assert _backend().effort_values() == SDK_EFFORT_LEVELS
    assert "xhigh" in SDK_EFFORT_LEVELS


def test_effort_values_are_narrowed_by_the_models_registry(monkeypatch):
    from sciqlop_claude import backend as mod

    monkeypatch.setattr(
        mod, "capabilities_for",
        lambda provider, model, **kw: SimpleNamespace(
            effort_values=("low", "medium", "high", "max")))
    # "xhigh" is in the SDK set but not this model's set — intersection wins,
    # and SDK order is preserved.
    assert _backend("claude-sonnet-4-6").effort_values() == (
        "low", "medium", "high", "max")


def test_unknown_model_keeps_the_sdk_set(monkeypatch):
    from sciqlop_claude import backend as mod
    from sciqlop_claude.backend import SDK_EFFORT_LEVELS

    monkeypatch.setattr(mod, "capabilities_for", lambda *a, **k: None)
    assert _backend("mystery").effort_values() == SDK_EFFORT_LEVELS


def test_set_effort_stores_and_drops_the_client_so_it_reconnects():
    be = _backend()
    disconnected = []

    async def fake_disconnect():
        disconnected.append(True)
        be._client = None

    be._client = SimpleNamespace()
    be._disconnect = fake_disconnect
    asyncio.run(be.set_effort("high"))

    assert be._effort == "high"
    assert disconnected == [True]


def test_set_effort_without_a_client_does_not_disconnect():
    be = _backend()
    called = []
    be._disconnect = lambda: called.append(True)
    asyncio.run(be.set_effort("low"))
    assert be._effort == "low"
    assert called == []


def test_result_message_session_id_is_recorded_for_resume():
    from sciqlop_claude.backend import remember_session

    be = _backend()
    remember_session(be, SimpleNamespace(session_id="sess-42"))
    assert be._resume == "sess-42"


def test_remember_session_ignores_a_blank_session_id():
    from sciqlop_claude.backend import remember_session

    be = _backend()
    be._resume = "existing"
    remember_session(be, SimpleNamespace(session_id=""))
    assert be._resume == "existing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/jeandet/Documents/prog/plugins_sciqlop && uv run pytest sciqlop_claude/sciqlop_claude/tests/test_effort.py -v`
Expected: FAIL — `ImportError: cannot import name 'SDK_EFFORT_LEVELS'`

- [ ] **Step 3: Write the implementation**

Add to `sciqlop_claude/backend.py`:

```python
from SciQLop.components.agents.model_capabilities import capabilities_for

# claude_agent_sdk.types.EffortLevel, in ascending order. This is what the SDK
# will put on the wire; models.dev narrows it per model.
SDK_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


def remember_session(backend, result) -> None:
    """Record the live session id so a reconnect resumes instead of starting over.

    Needed because effort can only be applied at connect time, so changing it
    forces a reconnect. Also hardens `set_model`'s error path, which drops the
    client on failure.
    """
    session_id = getattr(result, "session_id", None)
    if session_id:
        backend._resume = session_id
```

Add to `ClaudeBackend.__init__`: `self._effort: Optional[str] = None`.

Add the two protocol methods:

```python
    def effort_values(self) -> tuple:
        """SDK-accepted levels, narrowed to what the selected model supports."""
        caps = capabilities_for("anthropic", self._model or "")
        if caps is None or not caps.effort_values:
            return SDK_EFFORT_LEVELS
        allowed = set(caps.effort_values)
        return tuple(level for level in SDK_EFFORT_LEVELS if level in allowed)

    async def set_effort(self, effort: Optional[str]) -> None:
        """Store and force a reconnect — the SDK has no live effort setter, so
        effort can only be applied through ClaudeAgentOptions at connect time."""
        async with self._lock:
            self._effort = effort
            if self._client is not None:
                await self._disconnect()
```

In `_ensure_client`, add `effort=self._effort,` to the `ClaudeAgentOptions(...)` call.

In `ask()`, extend the ResultMessage capture added in Task 7:

```python
                if type(message).__name__ == "ResultMessage":
                    self._last_result = message
                    remember_session(self, message)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/jeandet/Documents/prog/plugins_sciqlop && uv run pytest sciqlop_claude/sciqlop_claude/tests/ -v`
Expected: PASS — all `sciqlop_claude` tests.

- [ ] **Step 5: Live verification — run the real app**

The spec lists four claims that specs alone cannot settle. Two are testable now:

Run `uv run sciqlop`, open the Agents dock, and confirm:
1. After one turn, the strip shows model, tokens, context % and cost.
2. ⓘ opens a breakdown whose categories match `/context` in the `claude` CLI.
3. Set effort to `high` in ⚙, send another message, and confirm **the earlier
   conversation is still present in the model's replies** — this is the
   reconnect-resume path, and a silent history loss here is the main risk in this task.
4. Note whether `total_cost_usd` grows across turns (cumulative) or resets
   (per-turn). If per-turn, `result_to_usage` must accumulate; open a follow-up.

Record the outcome of item 4 in the spec's "needs live verification" section.

- [ ] **Step 6: Commit (in the plugins repo)**

```bash
cd /home/jeandet/Documents/prog/plugins_sciqlop
git add sciqlop_claude/sciqlop_claude/backend.py \
        sciqlop_claude/sciqlop_claude/tests/test_effort.py
git commit -m "feat(claude): per-model effort selection with session-preserving reconnect"
```

---

### Task 9: Full suite verification

**Files:** none — verification only.

- [ ] **Step 1: Run the whole SciQLop suite**

Run: `uv run pytest --no-xvfb`
Expected: PASS. Read the actual pass/fail count and exit code — do not infer
success from a partial grep. If it segfaults or hangs, check
`index-pitfalls.md` before bisecting; several known GUI-suite traps look like
new regressions but are not.

- [ ] **Step 2: Run the whole plugins suite**

Run:

```bash
cd /home/jeandet/Documents/prog/plugins_sciqlop && \
PYTHONPATH=/home/jeandet/Documents/prog/plugins_sciqlop/sciqlop_claude \
uv run --no-sync --project /var/home/jeandet/Documents/prog/SciQLop \
  pytest sciqlop_claude -v
```

Expected: PASS with **0 skipped**.

**Do not use a bare `uv run pytest` here.** That resolves the plugins repo's own
environment, where `SciQLop` is absent and `tests/conftest.py` substitutes a
`MagicMock`. The usage tests' skip guard then fires and they report `0 passed,
9 skipped` — a green run that proves nothing. Borrowing SciQLop's venv via
`--no-sync --project` is what makes the real types importable. Check the skip
count on every run, not just the exit code.

- [ ] **Step 3: Report, do not push**

Report the real counts for both suites. Pushing is always a separate explicit
request — do not push.

---

## Deferred to later phases

- **Phase 2** — `components/agents/openai_compat.py` factored out of the ~130
  duplicated lines in Albert and Copilot, then Albert (`include_usage`, the
  `choices: []` guard fix, `/v1/me/usage` for cost and carbon, `/v1/me/info` for
  budget) and Copilot (same guard fix, nano-AIU cost, `max_prompt_tokens`,
  `/copilot_internal/user` quota, models.dev effort).
- **Phase 3** — Opencode: handle `ResultMessage` in `_OpencodeStream.feed`, accept
  `usage` as either a `Usage` dataclass or a bare dict, context via models.dev.
- **`claude-agent-sdk` 0.2.126 → 0.2.128** — its own commit, before Task 1 if you
  want the `PreToolUse` bypass fix in place first.
