"""Agent skills SciQLop ships, published into the workspace's `.claude/skills/`.

Each subdirectory here is one skill (`SKILL.md` plus its reference files).
Claude Code and opencode load skills from `.claude/skills/` in their cwd, and
cwd is the workspace. Agents that don't load skills get a pointer to the file
in the `AGENTS.md` guidance instead.

Only the bundled skills' own files are written: the user's other skills in the
same folder are never touched.
"""
from __future__ import annotations

from pathlib import Path

BUNDLED_SKILLS_DIR = Path(__file__).parent
SKILLS_SUBDIR = Path(".claude") / "skills"


def _bundled_files() -> list[Path]:
    return [p for p in BUNDLED_SKILLS_DIR.rglob("*.md") if p.parent != BUNDLED_SKILLS_DIR]


def _write_if_changed(source: Path, target: Path) -> None:
    content = source.read_text(encoding="utf-8")
    if target.is_file() and target.read_text(encoding="utf-8") == content:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def sync_skills(workspace_dir: Path) -> None:
    """Publish the bundled skills into `<workspace_dir>/.claude/skills/`. Best-effort,
    like `sync_agents_md`: a read-only or missing workspace must never break chat."""
    workspace_dir = Path(workspace_dir)
    if not workspace_dir.is_dir():
        return
    destination = workspace_dir / SKILLS_SUBDIR
    try:
        for source in _bundled_files():
            _write_if_changed(source, destination / source.relative_to(BUNDLED_SKILLS_DIR))
    except OSError:
        pass
