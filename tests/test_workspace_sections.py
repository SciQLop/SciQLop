import pytest
from pydantic import BaseModel

from SciQLop.components.workspaces.backend import workspace_manifest
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_sections import WORKSPACE_SECTIONS, WorkspaceSection


class Demo(BaseModel):
    n: int = 0
    names: list[str] = []


class Other(BaseModel):
    x: int = 0


@pytest.fixture
def demo_section(qapp):
    WORKSPACE_SECTIONS.contribute(WorkspaceSection("demo", Demo), owner="test")
    yield
    if "demo" in WORKSPACE_SECTIONS:
        WORKSPACE_SECTIONS.remove("demo")


def test_a_section_reads_and_writes_its_table(demo_section, tmp_path):
    p = tmp_path / "workspace.sciqlop"
    m = WorkspaceManifest.default_manifest("w")
    m.set_section("demo", Demo(n=3, names=["a"]))
    m.save(p)
    assert WorkspaceManifest.load(p).section("demo") == Demo(n=3, names=["a"])


def test_no_section_contributed_returns_none_and_keeps_the_table(qapp, tmp_path):
    p = tmp_path / "workspace.sciqlop"
    p.write_text('[workspace]\nname = "w"\n\n[demo]\nn = 2\n')
    m = WorkspaceManifest.load(p)
    assert m.section("demo") is None
    m.save(tmp_path / "again.sciqlop")
    assert WorkspaceManifest.load(tmp_path / "again.sciqlop").extra_tables["demo"] == {"n": 2}


def test_invalid_table_is_kept_and_logged_once(demo_section, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(workspace_manifest.log, "warning", lambda *a, **k: warnings.append(a))
    p = tmp_path / "workspace.sciqlop"
    p.write_text('[workspace]\nname = "w"\n\n[demo]\nn = "not an int"\n')
    m = WorkspaceManifest.load(p)
    assert m.section("demo") is None
    assert m.section("demo") is None
    assert len(warnings) == 1
    m.save(tmp_path / "again.sciqlop")
    assert WorkspaceManifest.load(tmp_path / "again.sciqlop").extra_tables["demo"] == {"n": "not an int"}


@pytest.mark.parametrize("table", ["plugins", "workspace", "dependencies", "examples", "a.b", "", "a b"])
def test_core_and_malformed_table_names_are_refused(table):
    with pytest.raises(ValueError):
        WorkspaceSection(table, Demo)


def test_set_section_with_the_wrong_model_is_refused(demo_section):
    m = WorkspaceManifest.default_manifest("w")
    with pytest.raises(ValueError):
        m.set_section("demo", Other())
    with pytest.raises(ValueError):
        m.set_section("nothing", Demo())
