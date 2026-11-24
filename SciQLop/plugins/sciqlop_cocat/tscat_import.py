"""The person's tscat catalogues brought into a CoCat project.

tscat reads its database (in a process of its own, on a copy: see tscat_dump.py) and cocat-rs
converts it. Uuids are kept, so importing again updates what an earlier import wrote. What a
project cannot hold as tscat had it is said in the result's notes, never dropped quietly.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .tscat_dump import BUSY, NO_DATABASE

DUMP_SCRIPT = Path(__file__).with_name("tscat_dump.py")
DUMP_TIMEOUT_S = 120  # 116 000 events are read in 2 s
# A project keeps a time as nanoseconds since 1970 in 64 bits.
EARLIEST, LATEST = datetime(1677, 9, 21, 0, 12, 44), datetime(2262, 4, 11, 23, 47, 16)
# The keys cocat-rs reads as its own, with the type it expects: tscat's attribute of that name
# and another type would stop the whole import, so it comes in under the second name.
RESERVED = {"events": ("shape", list, "tscat_shape"), "catalogues": ("shape_axis", dict, "tscat_shape_axis")}


class TscatUnreadable(Exception):
    """tscat could not read its database."""


class TscatBusy(TscatUnreadable):
    """Another program keeps the database to itself: tscat does, for as long as it has it open."""

    def __init__(self):
        super().__init__("another program is using the tscat database: an older SciQLop, or another "
                         "tscat tool, keeps it to itself while it runs. Close it: SciQLop tries again "
                         "at each start")


_reading: set[subprocess.Popen] = set()  # the reads under way, so that closing SciQLop can stop them


def stop_reading() -> None:
    """SciQLop waits for its threads at exit: a read still running must not keep it open."""
    for process in list(_reading):
        process.kill()


def _run_dump(output: Path, database: Path) -> subprocess.CompletedProcess:
    process = subprocess.Popen([sys.executable, str(DUMP_SCRIPT), str(output), str(database)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    _reading.add(process)
    try:
        _, errors = process.communicate(timeout=DUMP_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise TscatUnreadable(f"reading it took more than {DUMP_TIMEOUT_S} s")
    finally:
        _reading.discard(process)
    return subprocess.CompletedProcess(process.args, process.returncode, "", errors)


NOT_IN_ANY_CATALOGUE = "Not in any catalogue"
UNLISTED_RULE = {"filter": {"all": True}, "where": {"in_catalogue": None}}


@dataclass(frozen=True)
class Imported:
    catalogues: int = 0
    events: int = 0
    unlisted: int = 0             # events no catalogue lists: imported all the same
    notes: tuple[str, ...] = ()   # what did not come across as tscat had it

    def __bool__(self) -> bool:
        return bool(self.catalogues or self.events)

    def summary(self, destination: str) -> str:
        text = (f"{self.catalogues} catalogue(s) and {self.events} event(s) imported from tscat into "
                f"{destination}.")
        if self.unlisted:
            text += f" {self.unlisted} event(s) are in no catalogue."
        if self.notes:
            text += (f" {len(self.notes)} thing(s) did not come across as they were (all are in the log): "
                     + "; ".join(self.notes[:3]) + ("…" if len(self.notes) > 3 else ""))
        return text


def tscat_database() -> Path | None:
    """Where tscat keeps its database, None without tscat."""
    try:
        from tscat.orm_sqlalchemy import user_data_dir
    except ImportError:
        return None
    return Path(user_data_dir("tscat")) / "backend.sqlite"


def _dump(database: Path | None) -> str | None:
    database = database or tscat_database()
    if database is None:
        return None
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "tscat.json"
        done = _run_dump(output, database)
        if done.returncode == NO_DATABASE:
            return None
        if done.returncode == BUSY:
            raise TscatBusy()
        if done.returncode < 0:
            raise TscatUnreadable("the read was stopped")
        if done.returncode != 0:
            raise TscatUnreadable((done.stderr.strip().splitlines() or ["no reason given"])[-1])
        return output.read_text(encoding="utf-8")


async def read_tscat_database(database: Path | None = None) -> str | None:
    """The tscat database as the JSON text cocat-rs imports; None when there is no database."""
    return await asyncio.to_thread(_dump, database)


def _in_range(text: str) -> bool:
    time = datetime.fromisoformat(text)
    if time.tzinfo is not None:
        time = time.astimezone(timezone.utc).replace(tzinfo=None)
    return EARLIEST <= time <= LATEST


def _event_in_range(event: dict) -> bool:
    return _in_range(event["start"]) and _in_range(event["stop"])


def _without(uuids: list[str], gone: dict) -> list[str]:
    return [uuid for uuid in uuids if uuid not in gone]


def _without_out_of_range_events(data: dict) -> tuple[dict, list[str]]:
    gone = {e["uuid"]: e for e in data["events"] if not _event_in_range(e)}
    if not gone:
        return data, []
    names = {uuid: [c["name"] for c in data["catalogues"] if uuid in c["events"]] for uuid in gone}
    notes = [f"event {e['start']} to {e['stop']} of {', '.join(names[uuid]) or 'no catalogue'} is left out: "
             f"a project holds the years 1677 to 2262" for uuid, e in gone.items()]
    return {**data,
            "events": [e for e in data["events"] if e["uuid"] not in gone],
            "catalogues": [{**c, "events": _without(c["events"], gone)} for c in data["catalogues"]],
            "members": {c: _without(uuids, gone) for c, uuids in data.get("members", {}).items()},
            "removed": _without(data.get("removed", []), gone)}, notes


def _renamed(item: dict, key: str, expected: type, new_key: str) -> dict:
    if key not in item or isinstance(item[key], expected):
        return item
    return {new_key if k == key else k: v for k, v in item.items()}


def _without_reserved_keys(data: dict) -> tuple[dict, list[str]]:
    notes = []
    for kind, (key, expected, new_key) in RESERVED.items():
        renamed = [_renamed(item, key, expected, new_key) for item in data[kind]]
        count = sum(new is not old for new, old in zip(renamed, data[kind]))
        if count:
            notes.append(f"the attribute '{key}' of {count} {kind[:-1]}(s) is imported as '{new_key}': "
                         f"CoCat keeps '{key}' for its own use")
            data = {**data, kind: renamed}
    return data, notes


def _unlisted(data: dict) -> int:
    """The events no catalogue lists, the trash aside. (A dynamic catalogue may still select them.)"""
    accounted_for = {uuid for c in data["catalogues"] for uuid in c["events"]} | set(data.get("removed", []))
    return sum(1 for e in data["events"] if e["uuid"] not in accounted_for)


@dataclass(frozen=True)
class TscatContent:
    """What a tscat database holds, as a project can take it."""
    data: dict
    notes: tuple[str, ...] = ()   # what had to be left out or renamed for that

    def __bool__(self) -> bool:
        return bool(self.data["events"] or self.data["catalogues"])

    def write_into(self, project) -> Imported:
        with warnings.catch_warnings(record=True) as said:
            warnings.simplefilter("always")
            catalogues = project.import_tscat_json(json.dumps(self.data))
        notes = (*self.notes, *dict.fromkeys(str(warning.message) for warning in said))
        unlisted = show_unlisted(project) if _unlisted(self.data) else 0
        return Imported(len(catalogues), len(self.data["events"]), unlisted, notes)


def show_unlisted(project) -> int:
    """One smart catalogue showing the events no catalogue lists, kept only when it shows some; found
    by its rule, so a renamed one still counts. Returns how many it shows: counted on the project,
    since a tscat dynamic catalogue cocat-rs cannot say as a rule keeps its events listed."""
    smart = next((c for c in project.catalogues() if c.rule == UNLISTED_RULE), None)
    made = smart is None
    if made:
        smart = project.create_catalogue(name=NOT_IN_ANY_CATALOGUE)
        smart.rule = UNLISTED_RULE
    shown = len(smart.event_arrays()["uuid"])
    if made and not shown:
        smart.delete()
        smart.purge()
    return shown


def tscat_content(text: str) -> TscatContent:
    """`text` is what `read_tscat_database` read."""
    data, left_out = _without_out_of_range_events(json.loads(text))
    data, renamed = _without_reserved_keys(data)
    return TscatContent(data, (*left_out, *renamed))


def import_tscat_text(project, text: str) -> Imported:
    return tscat_content(text).write_into(project)
