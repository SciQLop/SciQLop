"""Crash material for the agent, and the GitHub issue it drafts.

The agent does the diagnosis; this only gathers what it needs to read (the
session log tail, the macOS crash report's crashed thread, versions) and
builds the prefilled issue page the user submits themselves.
"""
from __future__ import annotations

import getpass
import json
import platform
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

DIAGNOSTIC_REPORTS = Path.home() / "Library" / "Logs" / "DiagnosticReports"
ISSUES_URL = "https://github.com/SciQLop/SciQLop/issues/new"
LOG_TAIL_LINES = 300
MAX_FRAMES = 40
MAX_TOOL_CALLS = 10
# GitHub rejects prefilled issue URLs past ~8 kB.
MAX_BODY_CHARS = 6000
_VERSIONED = ("SciQLop", "SciQLopPlots", "speasy", "PySide6", "jupyqt")

_pending: Optional[dict] = None


def set_pending(marker: Optional[dict]) -> None:
    global _pending
    _pending = marker


def pending_crash_context() -> Optional[str]:
    return crash_context(_pending) if _pending else None


def tool_journal_path() -> Path:
    from SciQLop.components.agents.tools._journal import default_path
    return default_path()


def previous_tool_calls(journal: Path) -> list:
    """The crashed session's last agent tool calls. Read it before any new
    call: the journal is rewritten as soon as the next one starts."""
    try:
        calls = json.loads(journal.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return calls[-MAX_TOOL_CALLS:] if isinstance(calls, list) else []


def crash_context(marker: dict) -> str:
    marker = dict(marker)
    tool_calls = marker.pop("tool_calls", [])
    sections = [
        ("Crash marker", json.dumps(marker, indent=1)),
        ("Versions (running now)", json.dumps(_versions(), indent=1)),
        (f"Session log, last {LOG_TAIL_LINES} lines", _log_tail(Path(marker["log"]))),
    ]
    if tool_calls:
        sections.append(("Agent tool calls before the crash (UTC, finished=null means "
                         "in flight)", json.dumps(tool_calls, indent=1)))
    ips = find_ips(marker["pid"], DIAGNOSTIC_REPORTS, since=_crash_time(marker) - 60)
    if ips is not None:
        sections.append((f"macOS crash report {ips.name}", json.dumps(ips_summary(ips), indent=1)))
    return scrub("\n\n".join(f"## {title}\n{text}" for title, text in sections))


def find_ips(pid: int, directory: Path, since: float) -> Optional[Path]:
    """The pid is only inside the report (file names carry the process name,
    `python3.x` for SciQLop), so each recent report has to be read."""
    if not directory.is_dir():
        return None
    recent = [p for p in directory.glob("*.ips") if p.stat().st_mtime >= since]
    for path in sorted(recent, key=lambda p: p.stat().st_mtime, reverse=True):
        report = _ips_body(path)
        if report is not None and report.get("pid") == pid:
            return path
    return None


def ips_summary(path: Path) -> dict:
    report = _ips_body(path) or {}
    images = report.get("usedImages", [])
    crashed = next((t for t in report.get("threads", []) if t.get("triggered")), {})
    return {
        "exception": report.get("exception"),
        "termination": report.get("termination"),
        "crashed_thread": crashed.get("name") or crashed.get("queue"),
        "frames": [_frame(f, images) for f in crashed.get("frames", [])[:MAX_FRAMES]],
        "report_path": str(path),
    }


def scrub(text: str) -> str:
    """Mechanical backstop to the agent's own redaction: nothing that names
    the user's home or account leaves the machine."""
    text = text.replace(_home(), "~")
    user = _user()
    return text.replace(user, "<user>") if len(user) >= 3 else text


def issue_url(title: str, body: str) -> str:
    body = scrub(body)
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS] + "\n\n(truncated)"
    return f"{ISSUES_URL}?{urlencode({'title': scrub(title), 'body': body})}"


def _ips_body(path: Path) -> Optional[dict]:
    """macOS 12+ .ips: one JSON header line, then the JSON report."""
    try:
        _header, _, body = path.read_text(encoding="utf-8", errors="replace").partition("\n")
        report = json.loads(body)
    except (OSError, ValueError):
        return None
    return report if isinstance(report, dict) else None


def _frame(frame: dict, images: list) -> str:
    index = frame.get("imageIndex", -1)
    image = images[index].get("name", "?") if 0 <= index < len(images) else "?"
    return f"{image}  {frame.get('symbol') or hex(frame.get('imageOffset', 0)).replace('0x', '+0x')}"


def _log_tail(log: Path) -> str:
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        return f"(log unreadable: {e})"
    return "\n".join(lines[-LOG_TAIL_LINES:])


def _crash_time(marker: dict) -> float:
    try:
        return datetime.fromisoformat(marker["time"]).timestamp()
    except (KeyError, ValueError):
        return 0.0


def _versions() -> dict:
    def _version(name: str) -> str:
        try:
            return version(name)
        except PackageNotFoundError:
            return "not installed"

    return {"platform": platform.platform(), "python": platform.python_version(),
            **{name: _version(name) for name in _VERSIONED}}


def _home() -> str:
    return str(Path.home())


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""
