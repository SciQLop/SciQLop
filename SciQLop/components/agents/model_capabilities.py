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
import threading
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


def _read_registry() -> Optional[dict]:
    """The cached document, or None when absent/unreadable/unparseable."""
    try:
        data = json.loads(registry_path().read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) and data else None


def load_registry() -> dict:
    return _read_registry() or {}


def registry_is_stale() -> bool:
    # An unparseable cache must read as stale, not as fresh-and-empty: mtime
    # alone would keep a corrupt file authoritative for a week while every
    # effort selector silently stayed hidden.
    if _read_registry() is None:
        return True
    return (time.time() - registry_path().stat().st_mtime) > _MAX_AGE_SECONDS


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
    # One temp file per writer: `os.replace` is atomic w.r.t. the target, but a
    # shared source name lets one refresh publish a file another is still
    # writing — concurrent binds and two SciQLop processes both do this.
    tmp = target.with_suffix(f".json.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, target)     # atomic — a torn file would poison the cache
    except OSError:
        tmp.unlink(missing_ok=True)
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
