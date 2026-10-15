"""Agent skills are contributions to `sciqlop.agent_skills`; withdrawn ones leave the workspace."""
import pytest

from SciQLop.components.agents import AGENT_SKILLS, AgentSkill
from SciQLop.components.agents.skills import BUNDLED_SKILLS_DIR, contribute_core_skills, sync_skills
from SciQLop.core.extensions import owned_by

_OWNER = "skill_demo"
_CORE = sorted(p.parent.name for p in BUNDLED_SKILLS_DIR.glob("*/SKILL.md"))


@pytest.fixture(autouse=True)
def clean_skills():
    yield
    AGENT_SKILLS.remove_owner(_OWNER)


def _skill_folder(root, name="demo-skill"):
    folder = root / "src" / name
    (folder / "references").mkdir(parents=True)
    (folder / "SKILL.md").write_text("# demo", encoding="utf-8")
    (folder / "references" / "x.md").write_text("x", encoding="utf-8")
    return folder


def _published(ws):
    return ws / ".claude" / "skills"


def test_core_skills_are_contributions():
    contribute_core_skills()
    assert len(_CORE) == 6
    for name in _CORE:
        assert name in AGENT_SKILLS
        assert AGENT_SKILLS.owner_of(name) == "sciqlop"


def test_a_plugin_skill_is_published(tmp_path):
    with owned_by(_OWNER):
        AGENT_SKILLS.contribute(AgentSkill("demo-skill", _skill_folder(tmp_path)))
    sync_skills(tmp_path)
    assert (_published(tmp_path) / "demo-skill" / "SKILL.md").is_file()
    assert (_published(tmp_path) / "demo-skill" / "references" / "x.md").is_file()


def test_a_withdrawn_skill_is_removed_but_user_skills_stay(tmp_path):
    mine = _published(tmp_path) / "my-own" / "SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("mine", encoding="utf-8")
    contribute_core_skills()
    with owned_by(_OWNER):
        AGENT_SKILLS.contribute(AgentSkill("demo-skill", _skill_folder(tmp_path)))
    sync_skills(tmp_path)
    AGENT_SKILLS.remove_owner(_OWNER)
    sync_skills(tmp_path)
    assert not (_published(tmp_path) / "demo-skill").exists()
    assert mine.read_text(encoding="utf-8") == "mine"
    for name in _CORE:
        assert (_published(tmp_path) / name / "SKILL.md").is_file()


def test_existing_workspace_without_a_record(tmp_path):
    sync_skills(tmp_path)
    (_published(tmp_path) / ".sciqlop-published").unlink(missing_ok=True)
    mine = _published(tmp_path) / "my-own" / "SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("mine", encoding="utf-8")
    sync_skills(tmp_path)
    assert mine.is_file()
    for name in _CORE:
        assert (_published(tmp_path) / name / "SKILL.md").is_file()


def test_a_user_folder_named_like_a_withdrawn_skill_is_not_removed_without_a_record(tmp_path):
    clash = _published(tmp_path) / "demo-skill" / "SKILL.md"
    clash.parent.mkdir(parents=True)
    clash.write_text("mine", encoding="utf-8")
    sync_skills(tmp_path)
    assert clash.is_file()


@pytest.mark.parametrize("name", ["Bad Name", "", "-lead", "UPPER", "a" * 65])
def test_bad_name_is_refused(tmp_path, name):
    with pytest.raises(ValueError):
        AgentSkill(name, _skill_folder(tmp_path))


def test_folder_without_skill_md_is_refused(tmp_path):
    with pytest.raises(ValueError):
        AgentSkill("demo-skill", tmp_path)


def test_read_only_workspace_never_raises(tmp_path):
    (tmp_path / ".claude").write_text("a file where a directory is expected")
    with owned_by(_OWNER):
        AGENT_SKILLS.contribute(AgentSkill("demo-skill", _skill_folder(tmp_path)))
    sync_skills(tmp_path)
