"""Agent skills are contributions to `sciqlop.agent_skills`; withdrawn ones leave the workspace."""
import pytest

import SciQLop.components.agents.skills as skills_module
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


def _logged(monkeypatch, level):
    messages = []
    monkeypatch.setattr(skills_module.log, level, messages.append)
    return messages


def test_a_plugin_skill_never_overwrites_a_user_folder(tmp_path, monkeypatch):
    warnings = _logged(monkeypatch, "warning")
    mine = _published(tmp_path) / "clash" / "SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("mine", encoding="utf-8")
    with owned_by(_OWNER):
        AGENT_SKILLS.contribute(AgentSkill("clash", _skill_folder(tmp_path, "clash")))
    sync_skills(tmp_path)
    assert mine.read_text(encoding="utf-8") == "mine"
    assert not (mine.parent / "references").exists()
    assert len(warnings) == 1 and "clash" in warnings[0] and _OWNER in warnings[0]
    AGENT_SKILLS.remove_owner(_OWNER)
    sync_skills(tmp_path)
    assert mine.read_text(encoding="utf-8") == "mine"


def test_a_plugin_skill_named_like_a_bundled_one_is_logged(tmp_path, monkeypatch):
    """Only reachable when the core skills are not contributed (sync without the app): otherwise the
    extension point itself refuses the duplicate."""
    errors = _logged(monkeypatch, "error")
    bundled = _CORE[0]
    AGENT_SKILLS.remove_owner("sciqlop")
    try:
        with owned_by(_OWNER):
            AGENT_SKILLS.contribute(AgentSkill(bundled, _skill_folder(tmp_path, bundled)))
        sync_skills(tmp_path)
    finally:
        AGENT_SKILLS.remove_owner(_OWNER)
        contribute_core_skills()
    assert len(errors) == 1 and bundled in errors[0] and _OWNER in errors[0]
    assert (_published(tmp_path) / bundled / "SKILL.md").read_text(encoding="utf-8") != "# demo"


def test_a_corrupted_record_removes_nothing_outside(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = tmp_path / ".claude" / "sentinel.txt"
    sync_skills(tmp_path)
    sentinel.write_text("keep", encoding="utf-8")
    record = _published(tmp_path) / ".sciqlop-published"
    record.write_text(f"..\na/b\n{outside}\n\n{_CORE[0]}\n", encoding="utf-8")
    sync_skills(tmp_path)
    assert outside.is_dir() and sentinel.is_file()
    for name in _CORE:
        assert (_published(tmp_path) / name / "SKILL.md").is_file()


def test_a_failed_removal_is_retried(tmp_path, monkeypatch):
    with owned_by(_OWNER):
        AGENT_SKILLS.contribute(AgentSkill("demo-skill", _skill_folder(tmp_path)))
    sync_skills(tmp_path)
    AGENT_SKILLS.remove_owner(_OWNER)
    with monkeypatch.context() as m:
        m.setattr(skills_module.shutil, "rmtree", lambda *a, **k: None)
        sync_skills(tmp_path)
    assert (_published(tmp_path) / "demo-skill").exists()
    sync_skills(tmp_path)
    assert not (_published(tmp_path) / "demo-skill").exists()


def test_a_failing_publish_does_not_skip_the_bookkeeping(tmp_path, monkeypatch):
    real = skills_module._publish

    def flaky(skill, destination):
        if skill.name == "broken-skill":
            raise OSError("disk says no")
        real(skill, destination)

    monkeypatch.setattr(skills_module, "_publish", flaky)
    with owned_by(_OWNER):
        AGENT_SKILLS.contribute(AgentSkill("broken-skill", _skill_folder(tmp_path, "broken-skill")))
        AGENT_SKILLS.contribute(AgentSkill("demo-skill", _skill_folder(tmp_path)))
    sync_skills(tmp_path)
    assert "demo-skill" in (_published(tmp_path) / ".sciqlop-published").read_text(encoding="utf-8").split()
    AGENT_SKILLS.remove_owner(_OWNER)
    sync_skills(tmp_path)
    assert not (_published(tmp_path) / "demo-skill").exists()


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
