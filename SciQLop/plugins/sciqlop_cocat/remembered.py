"""What the plugin keeps between sessions, next to the projects' caches: the projects listed last
time (to open them while the server is unreachable) and the ones the person chose to leave.
For the projects kept on this computer only: the list, and whether moving them was offered.

Every SciQLop window of the person shares the file. So nothing read is kept: each question reads
it, and each change reads, changes and writes it while holding its lock."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import cocat_rs

from SciQLop.components.sciqlop_logging import getLogger

from .locks import lock_on

log = getLogger(__name__)

FILE_NAME = "sciqlop_state.json"
LOCK_WAIT_MS = 2000  # a change holds the lock for a few milliseconds


def _as_dict(info) -> dict:
    return {"id": info.id, "name": info.name, "role": info.role, "personal": info.personal,
            "editors_can_share": info.editors_can_share}


def _as_info(data: dict):
    return cocat_rs.ProjectInfo(data["id"], data["name"], data["role"], personal=data["personal"],
                                editors_can_share=data["editors_can_share"])


class Remembered:
    def __init__(self, folder: Path | None):
        self._path = Path(folder) / FILE_NAME if folder is not None else None
        self._lock = lock_on(self._path.with_name(f"{FILE_NAME}.lock")) if folder is not None else None
        self._unsaved: dict = {}  # without a folder, it lasts the session

    def _load(self) -> dict:
        if self._path is None:
            return self._unsaved
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except (OSError, ValueError) as error:
            log.warning("Cannot read %s, starting afresh: %s", self._path, error)
            return {}

    @contextmanager
    def _locked(self):
        if self._lock is None:
            yield
            return
        if not self._lock.tryLock(LOCK_WAIT_MS):
            log.warning("%s is locked by another SciQLop window for too long: going on without", self._path)
        try:
            yield
        finally:
            self._lock.unlock()

    def _read(self) -> dict:
        with self._locked():
            return self._load()

    @contextmanager
    def _changing(self):
        """The state as it is now, to change in place: written back before any other window reads it."""
        with self._locked():
            data = self._load()
            yield data
            if self._path is not None:
                self._path.write_text(json.dumps(data, indent=1))

    def _set(self, key: str, value) -> None:
        with self._changing() as data:
            data[key] = value

    @property
    def projects(self) -> list:
        return [_as_info(d) for d in self._read().get("projects", [])]

    @projects.setter
    def projects(self, infos) -> None:
        """The whole list: for the one the server gives."""
        self._set("projects", [_as_dict(i) for i in infos])

    def add_project(self, info) -> None:
        with self._changing() as data:
            listed = data.setdefault("projects", [])
            if all(d["id"] != info.id for d in listed):
                listed.append(_as_dict(info))

    def remove_project(self, project_id: str) -> None:
        with self._changing() as data:
            data["projects"] = [d for d in data.get("projects", []) if d["id"] != project_id]

    def projects_with_a_first(self, make) -> list:
        """The projects; `make()` gives the first one when there is none yet."""
        with self._changing() as data:
            if not data.get("projects"):
                data["projects"] = [_as_dict(make())]
            return [_as_info(d) for d in data["projects"]]

    @property
    def left(self) -> set[str]:
        return set(self._read().get("left", []))

    def set_left(self, project_id: str, left: bool) -> None:
        with self._changing() as data:
            ids = set(data.get("left", []))
            data["left"] = sorted(ids | {project_id} if left else ids - {project_id})

    @property
    def author(self) -> str | None:
        return self._read().get("author")

    @author.setter
    def author(self, email: str) -> None:
        self._set("author", email)

    @property
    def move_offered(self) -> bool:
        return self._read().get("move_offered", False)

    def note_move_offered(self) -> None:
        self._set("move_offered", True)

    def offer_move_again(self) -> None:
        """The offer is made once; catalogues that came to this computer after it are still unasked for."""
        self._set("move_offered", False)

    @property
    def tscat_imported(self) -> bool:
        """The tscat catalogues were brought in, or there were none: it is done once."""
        return self._read().get("tscat_imported", False)

    def note_tscat_imported(self) -> None:
        self._set("tscat_imported", True)

    @property
    def followed(self) -> list[dict]:
        """The public catalogues followed live, as the server listed them."""
        return list(self._read().get("followed", []))

    def follow(self, row: dict) -> None:
        with self._changing() as data:
            rows = data.setdefault("followed", [])
            if all(r["id"] != row["id"] for r in rows):
                rows.append(row)

    def unfollow(self, project_id: str) -> None:
        with self._changing() as data:
            data["followed"] = [r for r in data.get("followed", []) if r["id"] != project_id]
