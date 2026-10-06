"""Bundled agent skills are published into the workspace next to `AGENTS.md`."""

import re

from SciQLop.components.agents.guidance import SCIQLOP_GUIDANCE, load_guidance
from SciQLop.components.agents.skills import BUNDLED_SKILLS_DIR, sync_skills

SKILL = "sciqlop-plugin-design"


def _published(workspace):
    return workspace / ".claude" / "skills"


def _frontmatter(text: str) -> dict:
    block = text.split("---", 2)[1]
    return dict(line.split(":", 1) for line in block.strip().splitlines())


def test_bundled_skill_has_a_valid_frontmatter():
    fields = _frontmatter((BUNDLED_SKILLS_DIR / SKILL / "SKILL.md").read_text(encoding="utf-8"))
    assert fields["name"].strip() == SKILL
    description = fields["description"].strip()
    assert description.startswith("Use when")
    assert len(description) <= 1024


def test_bundled_skill_links_only_to_files_it_ships():
    skill_dir = BUNDLED_SKILLS_DIR / SKILL
    links = re.findall(r"\]\(([^)#:]+)\)", (skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    assert links, "the skill should point at its reference files"
    for link in links:
        assert (skill_dir / link).is_file(), link


def test_sync_copies_every_bundled_file(tmp_path):
    sync_skills(tmp_path)
    for source in (BUNDLED_SKILLS_DIR / SKILL).rglob("*.md"):
        target = _published(tmp_path) / source.relative_to(BUNDLED_SKILLS_DIR)
        assert target.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_sync_overwrites_a_stale_copy_and_keeps_the_users_own_skills(tmp_path):
    stale = _published(tmp_path) / SKILL / "SKILL.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")
    mine = _published(tmp_path) / "my-skill" / "SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("mine", encoding="utf-8")
    sync_skills(tmp_path)
    assert stale.read_text(encoding="utf-8") != "old"
    assert mine.read_text(encoding="utf-8") == "mine"


def test_sync_does_not_rewrite_current_files(tmp_path):
    sync_skills(tmp_path)
    target = _published(tmp_path) / SKILL / "SKILL.md"
    before = target.stat().st_mtime_ns
    sync_skills(tmp_path)
    assert target.stat().st_mtime_ns == before


def test_sync_never_raises_on_an_unwritable_workspace(tmp_path):
    (tmp_path / ".claude").write_text("a file where a directory is expected")
    sync_skills(tmp_path)


def test_sync_never_raises_on_a_missing_workspace(tmp_path):
    sync_skills(tmp_path / "does-not-exist")


def test_load_guidance_publishes_the_skills(tmp_path):
    load_guidance(tmp_path)
    assert (_published(tmp_path) / SKILL / "SKILL.md").is_file()


def test_guidance_points_agents_that_do_not_load_skills_at_the_file():
    assert f".claude/skills/{SKILL}/SKILL.md" in SCIQLOP_GUIDANCE
