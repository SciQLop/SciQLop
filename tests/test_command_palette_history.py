import json
from tests.fixtures import *


def test_history_add_and_list(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory
    h = LRUHistory(path=str(tmp_path / "history.json"), max_size=5)
    h.add("cmd.a", {"arg": "val"})
    h.add("cmd.b", {})
    entries = h.entries()
    assert len(entries) == 2
    assert entries[0].command_id == "cmd.b"
    assert entries[1].command_id == "cmd.a"


def test_history_lru_promotes_existing(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory
    h = LRUHistory(path=str(tmp_path / "history.json"), max_size=5)
    h.add("cmd.a", {"arg": "1"})
    h.add("cmd.b", {})
    h.add("cmd.a", {"arg": "1"})
    entries = h.entries()
    assert len(entries) == 2
    assert entries[0].command_id == "cmd.a"


def test_history_evicts_oldest(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory
    h = LRUHistory(path=str(tmp_path / "history.json"), max_size=3)
    h.add("cmd.1", {})
    h.add("cmd.2", {})
    h.add("cmd.3", {})
    h.add("cmd.4", {})
    entries = h.entries()
    assert len(entries) == 3
    ids = [e.command_id for e in entries]
    assert "cmd.1" not in ids


def test_history_persists_to_disk(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory
    path = str(tmp_path / "history.json")
    h1 = LRUHistory(path=path, max_size=5)
    h1.add("cmd.a", {"x": "1"})
    h2 = LRUHistory(path=path, max_size=5)
    entries = h2.entries()
    assert len(entries) == 1
    assert entries[0].command_id == "cmd.a"
    assert entries[0].resolved_args == {"x": "1"}


def test_history_handles_missing_file(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory
    h = LRUHistory(path=str(tmp_path / "nonexistent.json"), max_size=5)
    assert h.entries() == []
