"""What the plugin keeps between sessions, next to the projects' caches: the projects listed last
time (to open them while the server is unreachable) and the ones the person chose to leave.
For the projects kept on this computer only: the list, and whether moving them was offered."""
from __future__ import annotations

import json
from pathlib import Path

import cocat_rs

from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

FILE_NAME = "sciqlop_state.json"


def _as_dict(info) -> dict:
    return {"id": info.id, "name": info.name, "role": info.role, "personal": info.personal,
            "editors_can_share": info.editors_can_share}


def _as_info(data: dict):
    return cocat_rs.ProjectInfo(data["id"], data["name"], data["role"], personal=data["personal"],
                                editors_can_share=data["editors_can_share"])


class Remembered:
    def __init__(self, folder: Path | None):
        self._path = Path(folder) / FILE_NAME if folder is not None else None
        self._data = self._load()

    def _load(self) -> dict:
        if self._path is None or not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except (OSError, ValueError) as error:
            log.warning("Cannot read %s, starting afresh: %s", self._path, error)
            return {}

    def _save(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=1))

    @property
    def projects(self) -> list:
        return [_as_info(d) for d in self._data.get("projects", [])]

    @projects.setter
    def projects(self, infos) -> None:
        self._data["projects"] = [_as_dict(i) for i in infos]
        self._save()

    @property
    def left(self) -> set[str]:
        return set(self._data.get("left", []))

    def set_left(self, project_id: str, left: bool) -> None:
        ids = self.left | {project_id} if left else self.left - {project_id}
        self._data["left"] = sorted(ids)
        self._save()

    @property
    def author(self) -> str | None:
        return self._data.get("author")

    @author.setter
    def author(self, email: str) -> None:
        self._data["author"] = email
        self._save()

    @property
    def move_offered(self) -> bool:
        return self._data.get("move_offered", False)

    def note_move_offered(self) -> None:
        self._data["move_offered"] = True
        self._save()

    def offer_move_again(self) -> None:
        """The offer is made once; catalogues that came to this computer after it are still unasked for."""
        self._data["move_offered"] = False
        self._save()

    @property
    def tscat_imported(self) -> bool:
        """The tscat catalogues were brought in, or there were none: it is done once."""
        return self._data.get("tscat_imported", False)

    def note_tscat_imported(self) -> None:
        self._data["tscat_imported"] = True
        self._save()

    @property
    def followed(self) -> list[dict]:
        """The public catalogues followed live, as the server listed them."""
        return list(self._data.get("followed", []))

    @followed.setter
    def followed(self, rows: list[dict]) -> None:
        self._data["followed"] = rows
        self._save()
