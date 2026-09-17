"""Tool-call journal for crash attribution.

A native crash (Qt/C++ segfault) inside a tool call can't be caught by
Python, so nothing else records which call was in flight. This journal
rewrites a small JSON file to disk before each call starts and again when
it finishes, so the file left behind after a crash names the culprit.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Optional

log = logging.getLogger(__name__)

_MAX_ENTRIES = 20
_MAX_STRING_LEN = 2000
_FILENAME = "agent_tool_calls.json"


def default_path() -> Path:
    from SciQLop.components.storage import user_data_dir
    return user_data_dir("diagnostics") / _FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncated(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= _MAX_STRING_LEN:
            return value
        return value[:_MAX_STRING_LEN] + f"...(truncated, {len(value)} chars)"
    if isinstance(value, dict):
        return {k: _truncated(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncated(v) for v in value]
    return value


class ToolCallJournal:
    """Keeps the last `_MAX_ENTRIES` tool calls and mirrors them to *path*.

    One instance is meant to live for the whole process (see
    `default_journal()`); tests construct their own with an injected tmp
    path instead of touching the real diagnostics directory.
    """

    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path is not None else default_path()
        self._entries: Deque[Dict[str, Any]] = deque(maxlen=_MAX_ENTRIES)
        self._warn_if_previous_session_crashed()

    def _warn_if_previous_session_crashed(self) -> None:
        try:
            if not self._path.exists():
                return
            entries = json.loads(self._path.read_text(encoding="utf-8"))
            for entry in entries:
                if entry.get("finished") is None:
                    log.warning(
                        "previous session ended during tool call %r started at %s (journal: %s)",
                        entry.get("name"), entry.get("started"), self._path)
        except Exception:
            log.debug("agent tool journal startup check failed", exc_info=True)

    def _write(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(list(self._entries), indent=1)
            with open(self._path, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            log.debug("agent tool journal write failed", exc_info=True)

    def wrap(self, handler: Callable[[Dict[str, Any]], Any], name: str
             ) -> Callable[[Dict[str, Any]], Any]:
        """Wrap *handler* so every call is journaled. Always returns a
        coroutine function, matching every other tool handler."""

        async def _run(payload: Dict[str, Any]) -> Any:
            entry: Dict[str, Any] = {
                "name": name,
                "args": _truncated(payload),
                "started": _now_iso(),
                "finished": None,
                "error": None,
            }
            self._entries.append(entry)
            self._write()
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
            except Exception as e:
                entry["error"] = f"{type(e).__name__}: {e}"
                raise
            finally:
                entry["finished"] = _now_iso()
                self._write()

        return _run


_default_journal: Optional[ToolCallJournal] = None


def default_journal() -> ToolCallJournal:
    """The process-wide journal instance, created on first use."""
    global _default_journal
    if _default_journal is None:
        _default_journal = ToolCallJournal()
    return _default_journal
