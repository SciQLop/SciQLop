from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class HistoryEntry:
    command_id: str
    resolved_args: dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0

    def _key(self) -> tuple:
        return (self.command_id, tuple(sorted(self.resolved_args.items())))


class LRUHistory:
    def __init__(self, path: str, max_size: int = 50):
        self._path = path
        self._max_size = max_size
        self._entries: list[HistoryEntry] | None = None

    def _load(self) -> list[HistoryEntry]:
        if self._entries is not None:
            return self._entries
        self._entries = []
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    raw = json.load(f)
                self._entries = [
                    HistoryEntry(
                        command_id=e["command_id"],
                        resolved_args=e.get("resolved_args", {}),
                        timestamp=e.get("timestamp", 0.0),
                    )
                    for e in raw
                ]
            except (json.JSONDecodeError, KeyError, TypeError):
                self._entries = []
        return self._entries

    def _save(self):
        entries = self._load()
        with open(self._path, "w") as f:
            json.dump(
                [
                    {
                        "command_id": e.command_id,
                        "resolved_args": e.resolved_args,
                        "timestamp": e.timestamp,
                    }
                    for e in entries
                ],
                f,
            )

    def add(self, command_id: str, resolved_args: dict[str, str]) -> None:
        entries = self._load()
        entry = HistoryEntry(
            command_id=command_id,
            resolved_args=resolved_args,
            timestamp=time.time(),
        )
        key = entry._key()
        entries[:] = [e for e in entries if e._key() != key]
        entries.insert(0, entry)
        if len(entries) > self._max_size:
            entries[:] = entries[: self._max_size]
        self._save()

    def entries(self) -> list[HistoryEntry]:
        return list(self._load())
