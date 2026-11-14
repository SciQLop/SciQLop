"""A CoCat project's saved versions, or those of one of its catalogues, and the calls on them.

The server keeps the history: every version names who made it, when, and what it changed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import cocat_rs


@dataclass(frozen=True)
class Version:
    id: int
    when: datetime | None  # None for a version the server has not closed and has no start for
    who: str
    name: str
    changes: str
    named: bool = False       # a person named it; else `name` is the server's automatic one, if any
    colour: str = ""          # the author's colour, as the web app shows it
    restore: bool = False     # the version brought back an earlier one


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def describe_changes(entry: dict) -> str:
    if entry.get("restored_from") is not None:
        return f"restored version {entry['restored_from']}"
    parts = [f"{_plural(entry[key], 'event')} {verb}"
             for key, verb in (("events_added", "added"), ("events_changed", "changed"),
                               ("events_removed", "removed")) if entry.get(key)]
    if entry.get("rules_changed"):
        parts.append(f"{_plural(len(entry['rules_changed']), 'rule')} changed")
    if not parts and entry.get("catalogues"):
        parts.append(f"{_plural(len(entry['catalogues']), 'catalogue')} changed")
    return ", ".join(parts) or "no change"


def _when(entry: dict) -> datetime | None:
    """A version still being written has no end yet: its start stands in."""
    ms = entry.get("ended_ms") or entry.get("started_ms")
    return datetime.fromtimestamp(ms / 1000) if ms else None


def when_text(when: datetime | None) -> str:
    return f"{when:%Y-%m-%d %H:%M}" if when is not None else ""


def version_of(entry: dict) -> Version:
    return Version(id=entry["id"], when=_when(entry),
                   who=entry.get("author_email") or "", name=entry.get("name") or entry.get("auto_name") or "",
                   changes=describe_changes(entry), named=bool(entry.get("name")),
                   colour=entry.get("author_color") or "", restore=entry.get("restored_from") is not None)


class ProjectHistory:
    """With `catalogue`, only the versions that changed it, and restoring brings back just it."""

    def __init__(self, session, project_id: str, catalogue: str | None = None):
        self._session = session
        self.project_id = project_id
        self.catalogue = catalogue

    async def load(self) -> list[Version]:
        entries = await self._session.call(cocat_rs.raw.history, self.project_id, self.catalogue)
        return [version_of(e) for e in entries]

    async def restore(self, version: int) -> None:
        await self._session.call(cocat_rs.raw.restore, self.project_id, version, self.catalogue)

    async def name(self, version: int, name: str | None) -> None:
        await self._session.call(cocat_rs.raw.name_version, self.project_id, version, name or None)

    async def copy(self, version: int, name: str) -> str:
        """A new project of the person's own holding that version; its id."""
        return await self._session.call(cocat_rs.raw.copy_version, self.project_id, version, name)
