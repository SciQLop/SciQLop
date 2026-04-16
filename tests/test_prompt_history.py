"""Tests for the agent chat prompt history with fuzzy search."""
import importlib.util
import sys
from pathlib import Path

import pytest

# Load history.py directly to avoid the agents/__init__.py import chain
_MOD_PATH = (
    Path(__file__).resolve().parents[1]
    / "SciQLop" / "components" / "agents" / "chat" / "history.py"
)
_PKG = "SciQLop.components.agents.chat"
_MOD_NAME = f"{_PKG}.history"


@pytest.fixture()
def PromptHistory():
    spec = importlib.util.spec_from_file_location(_MOD_NAME, _MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG
    spec.loader.exec_module(mod)
    return mod.PromptHistory


@pytest.fixture()
def history(tmp_path, PromptHistory):
    return PromptHistory(path=tmp_path / "history.json", max_size=10)


def test_empty_history(history):
    assert history.entries() == []


def test_add_and_retrieve(history):
    history.add("plot ACE data")
    assert history.entries() == ["plot ACE data"]


def test_most_recent_first(history):
    history.add("first")
    history.add("second")
    assert history.entries() == ["second", "first"]


def test_dedup_moves_to_front(history):
    history.add("alpha")
    history.add("beta")
    history.add("alpha")
    assert history.entries() == ["alpha", "beta"]


def test_blank_ignored(history):
    history.add("")
    history.add("   ")
    assert history.entries() == []


def test_max_size_enforced(history):
    for i in range(15):
        history.add(f"prompt {i}")
    assert len(history.entries()) == 10
    assert history.entries()[0] == "prompt 14"


def test_persists_to_disk(tmp_path, PromptHistory):
    path = tmp_path / "history.json"
    h1 = PromptHistory(path=path)
    h1.add("saved")

    h2 = PromptHistory(path=path)
    assert h2.entries() == ["saved"]


def test_search_empty_query_returns_all(history):
    history.add("alpha")
    history.add("beta")
    results = history.search("")
    assert results == ["beta", "alpha"]


def test_search_exact_match(history):
    history.add("plot ACE magnetic field")
    history.add("set time range")
    history.add("screenshot panel")
    results = history.search("ACE")
    assert "plot ACE magnetic field" in results
    assert "set time range" not in results


def test_search_fuzzy(history):
    history.add("plot ACE magnetic field")
    history.add("plot MMS ion data")
    history.add("screenshot panel")
    results = history.search("plt ACE")
    assert results[0] == "plot ACE magnetic field"


def test_search_limit(history):
    for i in range(10):
        history.add(f"prompt {i}")
    results = history.search("", limit=3)
    assert len(results) == 3


def test_corrupt_file_handled(tmp_path, PromptHistory):
    path = tmp_path / "history.json"
    path.write_text("not valid json{{{")
    h = PromptHistory(path=path)
    assert h.entries() == []
