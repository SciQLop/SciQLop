"""Prompt history with fuzzy search for the agent chat input."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score

_DEFAULT_PATH = Path("~/.config/sciqlop/agent_prompt_history.json").expanduser()
_MAX_ENTRIES = 200


class PromptHistory:
    def __init__(self, path: Path = _DEFAULT_PATH, max_size: int = _MAX_ENTRIES):
        self._path = path
        self._max_size = max_size
        self._entries: list[str] | None = None

    def _load(self) -> list[str]:
        if self._entries is not None:
            return self._entries
        self._entries = []
        if self._path.exists():
            try:
                with open(self._path) as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    self._entries = [s for s in raw if isinstance(s, str)]
            except (json.JSONDecodeError, OSError):
                self._entries = []
        return self._entries

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._load(), f)

    def add(self, prompt: str) -> None:
        prompt = prompt.strip()
        if not prompt:
            return
        entries = self._load()
        # Move to front if already present (dedup)
        try:
            entries.remove(prompt)
        except ValueError:
            pass
        entries.insert(0, prompt)
        if len(entries) > self._max_size:
            del entries[self._max_size:]
        self._save()

    def entries(self) -> List[str]:
        return list(self._load())

    def search(self, query: str, limit: int = 20) -> List[str]:
        if not query:
            return self.entries()[:limit]
        scored = [
            (fuzzy_score(query, entry), entry)
            for entry in self._load()
        ]
        scored = [(s, e) for s, e in scored if s > 0]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [e for _, e in scored[:limit]]
