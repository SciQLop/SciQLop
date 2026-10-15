"""Agent skills SciQLop ships, published into the workspace's `.claude/skills/`.

Each subdirectory here is one skill (`SKILL.md` plus its reference files).
Claude Code and opencode load skills from `.claude/skills/` in their cwd, and
cwd is the workspace. Agents that don't load skills get a pointer to the file
in the `AGENTS.md` guidance instead.

Only the bundled skills' own files are written: the user's other skills in the
same folder are never touched.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path

from SciQLop.core.extensions import ExtensionPoint, NotRegistered, declare

BUNDLED_SKILLS_DIR = Path(__file__).parent
SKILLS_SUBDIR = Path(".claude") / "skills"
PUBLISHED_RECORD = ".sciqlop-published"
_CORE_OWNER = "sciqlop"
_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class AgentSkill:
    name: str
    directory: Path

    def __post_init__(self):
        if not _NAME.match(self.name):
            raise ValueError(f"agent skill name {self.name!r} must match {_NAME.pattern}")
        if not (Path(self.directory) / "SKILL.md").is_file():
            raise ValueError(f"agent skill {self.name!r}: {self.directory} has no SKILL.md")


AGENT_SKILLS = declare(ExtensionPoint(
    "sciqlop.agent_skills", AgentSkill, what="agent skill", key=attrgetter("name"),
    doc="Agent skills published into each workspace's .claude/skills/."))


def _bundled_names() -> list[str]:
    return sorted(p.parent.name for p in BUNDLED_SKILLS_DIR.glob("*/SKILL.md"))


def contribute_core_skills() -> None:
    """Main thread only. Idempotent."""
    for name in _bundled_names():
        if name not in AGENT_SKILLS:
            AGENT_SKILLS.contribute(AgentSkill(name, BUNDLED_SKILLS_DIR / name), owner=_CORE_OWNER)


def _plugin_skills() -> list[AgentSkill]:
    """Any thread: `keys()` is a snapshot, and a key may vanish before it is read."""
    found = []
    for name in AGENT_SKILLS.keys():
        try:
            if AGENT_SKILLS.owner_of(name) != _CORE_OWNER:
                found.append(AGENT_SKILLS.get(name))
        except NotRegistered:
            continue
    return found


def _bundled_files() -> list[Path]:
    return [p for p in BUNDLED_SKILLS_DIR.rglob("*.md") if p.parent != BUNDLED_SKILLS_DIR]


def _write_if_changed(source: Path, target: Path) -> None:
    content = source.read_text(encoding="utf-8")
    if target.is_file() and target.read_text(encoding="utf-8") == content:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _publish(skill: AgentSkill, destination: Path) -> None:
    for source in Path(skill.directory).rglob("*.md"):
        _write_if_changed(source, destination / skill.name / source.relative_to(skill.directory))


def _recorded_names(record: Path) -> set[str]:
    if not record.is_file():
        return set()
    return {line for line in record.read_text(encoding="utf-8").splitlines() if _NAME.match(line)}


def _remove_withdrawn(destination: Path, recorded: set[str], current: set[str]) -> None:
    for name in recorded - current - set(_bundled_names()):
        shutil.rmtree(destination / name, ignore_errors=True)


def sync_skills(workspace_dir: Path) -> None:
    """Publish the bundled and contributed skills into `<workspace_dir>/.claude/skills/`, and remove the
    ones SciQLop published earlier that are no longer contributed. Best-effort, like `sync_agents_md`:
    a read-only or missing workspace must never break chat.

    May run off the main thread, so it only reads the extension point and never contributes: the core
    skills are contributed by `contribute_core_skills` at startup, and published here from the bundle."""
    workspace_dir = Path(workspace_dir)
    if not workspace_dir.is_dir():
        return
    destination = workspace_dir / SKILLS_SUBDIR
    try:
        for source in _bundled_files():
            _write_if_changed(source, destination / source.relative_to(BUNDLED_SKILLS_DIR))
        skills = [s for s in _plugin_skills() if s.name not in _bundled_names()]
        for skill in skills:
            _publish(skill, destination)
        record = destination / PUBLISHED_RECORD
        current = {s.name for s in skills}
        _remove_withdrawn(destination, _recorded_names(record), current)
        record.write_text("".join(f"{n}\n" for n in sorted(current)), encoding="utf-8")
    except OSError:
        pass
