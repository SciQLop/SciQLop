"""Run as a script: writes a tscat database as the JSON text cocat-rs imports.

    python tscat_dump.py OUTPUT [DATABASE]

It runs in a process of its own because tscat keeps one database open per process, and SciQLop's
tscat catalogues are using it. It reads a copy because opening a database with tscat upgrades it
in place. cocat-rs does the reading (`cocat_rs.tscat.import_database`); this only hands it a copy.
"""
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

NO_DATABASE = 3  # exit code: there is no tscat database


def default_database() -> Path:
    from tscat.orm_sqlalchemy import user_data_dir
    return Path(user_data_dir("tscat")) / "backend.sqlite"


def snapshot(database: Path, folder: Path) -> Path:
    """sqlite's own backup through a read-only connection: a consistent copy, even of a database
    SciQLop is writing to."""
    copy = folder / database.name
    with closing(sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)) as source, \
            closing(sqlite3.connect(copy)) as target:
        source.backup(target)
    return copy


def _superseded(versions: list[str]) -> list[str]:
    """The versions that another of them was upgraded from, by tscat's own chain of upgrades."""
    import tscat.orm_sqlalchemy
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    config = Config()
    config.set_main_option("script_location", str(Path(tscat.orm_sqlalchemy.__file__).with_name("migrations")))
    script = ScriptDirectory.from_config(config)
    earlier = {v: {r.revision for r in script.iterate_revisions(v, "base")} - {v} for v in versions}
    return [v for v in versions if any(v in earlier[other] for other in versions)]


def drop_superseded_versions(copy: Path) -> None:
    """A database can name an old version next to its current one, and tscat then refuses to open
    it ("more than one head"). The old mark says nothing the current one does not: it is dropped,
    here on the copy only."""
    with closing(sqlite3.connect(copy)) as database, database:
        if not database.execute("SELECT 1 FROM sqlite_master WHERE name = 'alembic_version'").fetchone():
            return
        versions = [row[0] for row in database.execute("SELECT version_num FROM alembic_version")]
        if len(versions) > 1:
            database.executemany("DELETE FROM alembic_version WHERE version_num = ?",
                                 [(version,) for version in _superseded(versions)])


class _CapturedText:
    """Stands for the project cocat-rs imports into: keeps the text instead."""
    text = ""

    def import_tscat_json(self, text: str) -> list:
        self.text = text
        return []


def as_json(database: Path) -> str:
    import cocat_rs.tscat
    import tscat.base
    from tscat.orm_sqlalchemy import Backend
    backend = tscat.base._backend = Backend(testing=str(database))  # tscat works on its own copy
    try:
        captured = _CapturedText()
        cocat_rs.tscat.import_database(captured)
        return captured.text
    finally:
        backend.close()
        shutil.rmtree(backend._tmp_dir, ignore_errors=True)


def main(output: str, database: str | None = None) -> int:
    source = Path(database) if database else default_database()
    if not source.exists():
        return NO_DATABASE
    with tempfile.TemporaryDirectory() as folder:
        copy = snapshot(source, Path(folder))
        drop_superseded_versions(copy)
        Path(output).write_text(as_json(copy), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
