"""Catalogue files in and out of a CoCat project: VOTable, tscat's JSON and TFCat, all written and
read by cocat-rs. Also the one-off import of the local tscat database."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cocat_rs
import cocat_rs.tscat


@dataclass(frozen=True)
class Format:
    name: str
    suffix: str
    filter: str
    write: Callable  # (project, catalogue, path, value_range)
    read: Callable   # (project, path)


FORMATS = (
    Format("VOTable", ".xml", "VOTable (*.xml *.vot)",
           lambda project, catalogue, path, _: cocat_rs.export_votable([catalogue], path),
           lambda project, path: project.import_votable(str(path))),
    Format("tscat JSON", ".json", "tscat JSON (*.json)",
           lambda project, catalogue, path, _: cocat_rs.tscat.export_json(project, [catalogue], path),
           lambda project, path: cocat_rs.tscat.import_json(project, path)),
    Format("TFCat", ".json", "TFCat (*.json *.tfcat)",
           lambda project, catalogue, path, value_range: cocat_rs.export_tfcat(catalogue, path, value_range),
           lambda project, path: project.import_tfcat(str(path))),
)
FILE_FILTERS = ";;".join(f.filter for f in FORMATS)


def format_for_filter(chosen: str) -> Format | None:
    return next((f for f in FORMATS if f.filter == chosen), None)


class NeedsValueRange(Exception):
    """TFCat draws every event as an area: events with no shape need a band on the second axis."""


def export_catalogue(fmt: Format, project, catalogue, path: str | Path, value_range=None) -> None:
    try:
        fmt.write(project, catalogue, Path(path), value_range)
    except ValueError as error:
        if fmt.name == "TFCat" and value_range is None:
            raise NeedsValueRange(str(error)) from error
        raise


def import_file(fmt: Format, project, path: str | Path):
    """What the format's reader returns: empty (0, []) when the file held no catalogue."""
    return fmt.read(project, Path(path))


def tscat_available() -> bool:
    try:
        import tscat  # noqa: F401
    except ImportError:
        return False
    return True


def import_tscat_database(project) -> list:
    """Uuids are kept, so importing again updates what an earlier import wrote."""
    return cocat_rs.tscat.import_database(project)
