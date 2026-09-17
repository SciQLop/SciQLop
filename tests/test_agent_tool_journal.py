"""Tool-call journal: crash-attribution file rewritten before/after each
call, so a native crash still leaves behind which tool was in flight.

Pure filesystem tests — SciQLop.components.agents.tools._journal has no Qt
dependency and does not need qtbot/main_window.
"""
import asyncio
import inspect
import json
import logging

import pytest


def _run(coro):
    return asyncio.run(coro)


def test_unfinished_entry_is_on_disk_while_handler_runs(tmp_path):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    journal = ToolCallJournal(path=path)
    seen = {}

    async def handler(payload):
        seen.update(json.loads(path.read_text(encoding="utf-8"))[-1])
        return {"ok": True}

    wrapped = journal.wrap(handler, "sciqlop_test_tool")
    result = _run(wrapped({"x": 1}))

    assert result == {"ok": True}
    assert seen["name"] == "sciqlop_test_tool"
    assert seen["finished"] is None
    assert seen["args"] == {"x": 1}


def test_finished_entry_recorded_after_handler_returns(tmp_path):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    journal = ToolCallJournal(path=path)

    async def handler(payload):
        return "done"

    _run(journal.wrap(handler, "sciqlop_test_tool")({}))

    entries = json.loads(path.read_text(encoding="utf-8"))
    assert len(entries) == 1
    assert entries[0]["finished"] is not None
    assert entries[0]["error"] is None


def test_exception_in_handler_is_recorded_and_still_propagates(tmp_path):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    journal = ToolCallJournal(path=path)

    async def handler(payload):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _run(journal.wrap(handler, "sciqlop_test_tool")({}))

    entries = json.loads(path.read_text(encoding="utf-8"))
    assert "boom" in entries[0]["error"]
    assert entries[0]["finished"] is not None


def test_ring_keeps_only_20_entries(tmp_path):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    journal = ToolCallJournal(path=path)

    async def handler(payload):
        return None

    wrapped = journal.wrap(handler, "sciqlop_test_tool")
    for i in range(25):
        _run(wrapped({"i": i}))

    entries = json.loads(path.read_text(encoding="utf-8"))
    assert len(entries) == 20
    assert entries[-1]["args"]["i"] == 24
    assert entries[0]["args"]["i"] == 5


def test_long_string_args_are_truncated(tmp_path):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    journal = ToolCallJournal(path=path)

    async def handler(payload):
        return None

    _run(journal.wrap(handler, "sciqlop_test_tool")({"code": "x" * 5000}))

    entries = json.loads(path.read_text(encoding="utf-8"))
    assert len(entries[0]["args"]["code"]) < 2100


def test_wrap_always_returns_a_coroutine_function_even_for_a_sync_handler(tmp_path):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    journal = ToolCallJournal(path=path)

    def handler(payload):
        return "sync result"

    wrapped = journal.wrap(handler, "sciqlop_test_tool")
    assert inspect.iscoroutinefunction(wrapped)
    assert _run(wrapped({})) == "sync result"


def test_journal_io_failure_never_fails_the_call(tmp_path, monkeypatch):
    from SciQLop.components.agents.tools import _journal

    journal = _journal.ToolCallJournal(path=tmp_path / "journal.json")
    monkeypatch.setattr(
        _journal.Path, "mkdir",
        lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))

    async def handler(payload):
        return "ok"

    assert _run(journal.wrap(handler, "sciqlop_test_tool")({})) == "ok"


def test_warns_when_previous_session_left_an_unfinished_entry(tmp_path, caplog):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    path.write_text(json.dumps([
        {"name": "sciqlop_screenshot_panel", "args": {}, "started": "2026-01-01T00:00:00+00:00",
         "finished": None, "error": None},
    ]), encoding="utf-8")

    caplog.set_level(logging.WARNING)
    ToolCallJournal(path=path)

    assert any("sciqlop_screenshot_panel" in r.message for r in caplog.records)
    assert any(str(path) in r.message for r in caplog.records)


def test_no_warning_when_previous_session_ended_cleanly(tmp_path, caplog):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    path.write_text(json.dumps([
        {"name": "sciqlop_screenshot_panel", "args": {}, "started": "2026-01-01T00:00:00+00:00",
         "finished": "2026-01-01T00:00:01+00:00", "error": None},
    ]), encoding="utf-8")

    caplog.set_level(logging.WARNING)
    ToolCallJournal(path=path)

    assert not any("sciqlop_screenshot_panel" in r.message for r in caplog.records)


def test_warns_about_an_unfinished_call_followed_by_a_finished_one(tmp_path, caplog):
    from SciQLop.components.agents.tools._journal import ToolCallJournal

    path = tmp_path / "journal.json"
    path.write_text(json.dumps([
        {"name": "sciqlop_exec_python", "args": {}, "started": "2026-01-01T00:00:00+00:00",
         "finished": None, "error": None},
        {"name": "sciqlop_list_panels", "args": {}, "started": "2026-01-01T00:00:01+00:00",
         "finished": "2026-01-01T00:00:02+00:00", "error": None},
    ]), encoding="utf-8")

    caplog.set_level(logging.WARNING)
    ToolCallJournal(path=path)

    assert any("sciqlop_exec_python" in r.message for r in caplog.records)
