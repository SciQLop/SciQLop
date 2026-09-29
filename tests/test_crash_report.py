"""Crash-report material handed to the agent, and the issue it publishes.

See docs/superpowers/specs/2026-09-29-crash-report-agent-design.md.
"""
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from SciQLop.components.crash_report import backend


def _write_ips(path: Path, pid: int, crashed_frames=None, mtime=None) -> Path:
    header = {"app_name": "python3.14", "bug_type": "309"}
    body = {
        "pid": pid,
        "procName": "python3.14",
        "exception": {"type": "EXC_BAD_ACCESS", "signal": "SIGSEGV"},
        "termination": {"indicator": "Segmentation fault: 11"},
        "usedImages": [{"name": "QtWidgets"}, {"name": "SciQLopPlotsBindings.so"}],
        "threads": [
            {"name": "idle", "frames": [{"imageIndex": 0, "symbol": "nothing"}]},
            {"triggered": True, "queue": "com.apple.main-thread",
             "frames": crashed_frames or [
                 {"imageIndex": 0, "symbol": "QWidget::sharedPainter() const"},
                 {"imageIndex": 1, "imageOffset": 4096},
             ]},
        ],
    }
    path.write_text(json.dumps(header) + "\n" + json.dumps(body, indent=2))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_find_ips_matches_the_pid_inside_the_report(tmp_path):
    _write_ips(tmp_path / "python3.14-2026-09-29-100000.ips", pid=111)
    wanted = _write_ips(tmp_path / "python3.14-2026-09-29-100100.ips", pid=222)
    assert backend.find_ips(222, tmp_path, since=0) == wanted


def test_find_ips_ignores_reports_older_than_the_crash(tmp_path):
    _write_ips(tmp_path / "old.ips", pid=222, mtime=time.time() - 3600)
    assert backend.find_ips(222, tmp_path, since=time.time() - 60) is None


def test_find_ips_skips_unreadable_reports(tmp_path):
    (tmp_path / "broken.ips").write_text("not json at all")
    wanted = _write_ips(tmp_path / "good.ips", pid=5)
    assert backend.find_ips(5, tmp_path, since=0) == wanted


def test_find_ips_without_a_reports_directory(tmp_path):
    assert backend.find_ips(5, tmp_path / "missing", since=0) is None


def test_ips_summary_keeps_the_crashed_thread_with_image_names(tmp_path):
    summary = backend.ips_summary(_write_ips(tmp_path / "r.ips", pid=1))
    assert summary["exception"]["signal"] == "SIGSEGV"
    assert summary["crashed_thread"] == "com.apple.main-thread"
    assert summary["frames"] == [
        "QtWidgets  QWidget::sharedPainter() const",
        "SciQLopPlotsBindings.so  +0x1000",
    ]


def test_scrub_removes_home_and_user_name(monkeypatch):
    monkeypatch.setattr(backend, "_home", lambda: "/Users/alice")
    monkeypatch.setattr(backend, "_user", lambda: "alice")
    text = "open /Users/alice/Library/x failed for alice"
    assert backend.scrub(text) == "open ~/Library/x failed for <user>"


def test_scrub_leaves_short_user_names_alone(monkeypatch):
    monkeypatch.setattr(backend, "_home", lambda: "/home/al")
    monkeypatch.setattr(backend, "_user", lambda: "al")
    assert backend.scrub("a normal line") == "a normal line"


def test_issue_url_prefills_title_and_body():
    url = urlparse(backend.issue_url("Crash in X", "details"))
    query = parse_qs(url.query)
    assert url.netloc == "github.com"
    assert url.path == "/SciQLop/SciQLop/issues/new"
    assert query["title"] == ["Crash in X"]
    assert query["body"] == ["details"]


def test_issue_url_truncates_a_long_body():
    url = backend.issue_url("t", "x" * 50_000)
    assert len(url) < 9000


def test_crash_context_includes_the_log_tail_and_the_marker(tmp_path, monkeypatch):
    log = tmp_path / "session.log"
    log.write_text("".join(f"line {i}\n" for i in range(1000)) + "Fatal Python error: Segmentation fault\n")
    marker = {"time": "2026-09-29T17:19:03+02:00", "pid": 42, "platform": "linux",
              "signal": 11, "ntstatus": None, "log": str(log)}
    context = backend.crash_context(marker)
    assert "Fatal Python error: Segmentation fault" in context
    assert "line 999" in context
    assert "line 10\n" not in context
    assert '"signal": 11' in context
    assert "SciQLop" in context


def test_crash_context_attaches_the_macos_report(tmp_path, monkeypatch):
    log = tmp_path / "session.log"
    log.write_text("boom\n")
    _write_ips(tmp_path / "r.ips", pid=42)
    monkeypatch.setattr(backend, "DIAGNOSTIC_REPORTS", tmp_path)
    marker = {"time": "2000-01-01T00:00:00+00:00", "pid": 42, "platform": "darwin",
              "signal": 11, "ntstatus": None, "log": str(log)}
    context = backend.crash_context(marker)
    assert "QWidget::sharedPainter() const" in context


def test_previous_tool_calls_reads_the_last_entries_of_the_journal(tmp_path):
    journal = tmp_path / "agent_tool_calls.json"
    journal.write_text(json.dumps([{"name": f"tool{i}", "started": "t", "finished": "t"}
                                   for i in range(15)]))
    calls = backend.previous_tool_calls(journal)
    assert [c["name"] for c in calls] == [f"tool{i}" for i in range(5, 15)]


def test_previous_tool_calls_without_a_journal(tmp_path):
    assert backend.previous_tool_calls(tmp_path / "missing.json") == []
    (tmp_path / "broken.json").write_text("{nope")
    assert backend.previous_tool_calls(tmp_path / "broken.json") == []


def test_crash_context_lists_the_agent_tool_calls_before_the_crash(tmp_path):
    # GH #139: the last tool call is usually what identifies the trigger.
    log = tmp_path / "session.log"
    log.write_text("boom\n")
    marker = {"time": "2026-09-29T17:19:03+02:00", "pid": 42, "platform": "linux",
              "signal": 11, "ntstatus": None, "log": str(log),
              "tool_calls": [{"name": "sciqlop_exec_python", "args": {"code": "g.deleteLater()"},
                              "started": "2026-09-29T15:19:01+00:00", "finished": None}]}
    context = backend.crash_context(marker)
    assert "sciqlop_exec_python" in context
    assert "g.deleteLater()" in context


def test_no_pending_crash_means_no_context():
    backend.set_pending(None)
    assert backend.pending_crash_context() is None


def _tool(name):
    from unittest.mock import MagicMock
    import SciQLop.components.agents.tools._builder as builder
    return next(t for t in builder.build_sciqlop_tools(MagicMock()) if t["name"] == name)


def _text(result) -> str:
    return result["content"][0]["text"]


def test_read_crash_report_tool_works_even_with_writes_disabled(qtbot, tmp_path):
    import asyncio

    log = tmp_path / "session.log"
    log.write_text("Fatal Python error: Segmentation fault\n")
    backend.set_pending({"time": "2026-09-29T17:19:03+02:00", "pid": 42, "platform": "linux",
                         "signal": 11, "ntstatus": None, "log": str(log)})
    try:
        tool = _tool("sciqlop_read_crash_report")
        assert tool["gated"] is False
        assert "Segmentation fault" in _text(asyncio.run(tool["handler"]({})))
    finally:
        backend.set_pending(None)


def test_read_crash_report_tool_without_a_crash(qtbot):
    import asyncio

    backend.set_pending(None)
    text = _text(asyncio.run(_tool("sciqlop_read_crash_report")["handler"]({})))
    assert "No crash" in text


def test_open_bug_report_tool_opens_a_scrubbed_prefilled_issue(qtbot, monkeypatch):
    import asyncio
    from PySide6.QtGui import QDesktopServices

    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    monkeypatch.setattr(backend, "_home", lambda: "/Users/alice")
    tool = _tool("sciqlop_open_bug_report")
    assert tool["gated"] is False
    asyncio.run(tool["handler"]({"title": "Crash", "body": "in /Users/alice/x"}))
    assert len(opened) == 1
    query = parse_qs(urlparse(opened[0]).query)
    assert query["body"] == ["in ~/x"]
