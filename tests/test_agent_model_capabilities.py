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


def test_corrupt_cache_is_stale_so_it_self_heals():
    """`registry_is_stale` keys off mtime, so a freshly-written corrupt file
    would otherwise count as current for a week while `load_registry` returned
    {} — every effort selector silently gone, with no recovery."""
    from SciQLop.components.agents.model_capabilities import (
        load_registry, registry_is_stale, registry_path)

    registry_path().write_text("{ this is not jso")     # just published, torn
    assert load_registry() == {}
    assert registry_is_stale() is True
    registry_path().unlink()


def test_concurrent_refreshes_use_distinct_temp_files(monkeypatch):
    """A single fixed `.json.tmp` lets one refresh `os.replace` a file another
    is still writing — several binds on a stale cache spawn several workers,
    and two SciQLop processes race the same way."""
    import json
    import threading

    from SciQLop.components.agents import model_capabilities as mc

    import sys

    seen: list = []
    real_replace = mc.os.replace

    def _record(src, dst):
        if str(src).endswith(".tmp"):
            seen.append(str(src))
        real_replace(src, dst)

    monkeypatch.setattr(mc.os, "replace", _record)
    monkeypatch.setitem(
        sys.modules, "httpx",
        type("httpx", (), {"get": staticmethod(lambda *a, **k: _FakeResponse())}))

    workers = [threading.Thread(target=mc.refresh_registry) for _ in range(4)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()

    assert len(seen) == 4
    assert len(set(seen)) == 4          # no two writers shared a source file
    assert json.loads(mc.registry_path().read_text())     # and the result parses
    mc.registry_path().unlink()


class _FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"anthropic": {"models": {"m": {"limit": {"context": 1}}}}}


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
