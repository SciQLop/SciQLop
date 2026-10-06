"""`merge_guidance` owns one marker-delimited block inside a user-owned file."""

import pytest

from SciQLop.components.agents.guidance import (
    BEGIN_MARKER,
    END_MARKER,
    SCIQLOP_GUIDANCE,
    load_guidance,
    merge_guidance,
    sync_agents_md,
)


def _managed(text: str) -> str:
    body = text.split(BEGIN_MARKER, 1)[1]
    return body.split(END_MARKER, 1)[0].strip()


def test_merge_into_empty_file_emits_a_single_marked_block():
    out = merge_guidance("", "hello")
    assert out.count(BEGIN_MARKER) == 1
    assert out.count(END_MARKER) == 1
    assert _managed(out) == "hello"


def test_merge_appends_below_unmarked_user_content():
    out = merge_guidance("# My notes\n\nkeep me\n", "hello")
    assert out.startswith("# My notes\n\nkeep me\n")
    assert _managed(out) == "hello"


def test_merge_replaces_only_the_managed_block():
    first = merge_guidance("# My notes\n", "old guidance")
    second = merge_guidance(first, "new guidance")
    assert _managed(second) == "new guidance"
    assert "old guidance" not in second
    assert second.startswith("# My notes\n")
    assert second.count(BEGIN_MARKER) == 1


def test_merge_preserves_user_content_written_after_the_block():
    with_block = merge_guidance("", "old guidance")
    edited = with_block + "\n## Project rules\n\nalways use SI units\n"
    out = merge_guidance(edited, "new guidance")
    assert "## Project rules" in out
    assert "always use SI units" in out
    assert _managed(out) == "new guidance"
    assert "old guidance" not in out


def test_merge_is_idempotent():
    once = merge_guidance("# My notes\n", "guidance")
    assert merge_guidance(once, "guidance") == once


def test_merge_tolerates_a_begin_marker_with_no_end():
    # A user truncating the file mid-block must not lose their own content.
    out = merge_guidance(f"# My notes\n{BEGIN_MARKER}\ntruncated", "guidance")
    assert out.count(BEGIN_MARKER) == 1
    assert out.count(END_MARKER) == 1
    assert _managed(out) == "guidance"
    assert out.startswith("# My notes\n")


def test_sync_creates_agents_md_with_the_guidance(tmp_path):
    sync_agents_md(tmp_path)
    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert _managed(text) == SCIQLOP_GUIDANCE.strip()


def test_sync_keeps_user_content_and_rewrites_the_block(tmp_path):
    target = tmp_path / "AGENTS.md"
    target.write_text("# House rules\n\nno emoji\n", encoding="utf-8")
    sync_agents_md(tmp_path)
    text = target.read_text(encoding="utf-8")
    assert "no emoji" in text
    assert _managed(text) == SCIQLOP_GUIDANCE.strip()


def test_sync_does_not_rewrite_an_already_current_file(tmp_path):
    sync_agents_md(tmp_path)
    target = tmp_path / "AGENTS.md"
    before = target.stat().st_mtime_ns
    sync_agents_md(tmp_path)
    assert target.stat().st_mtime_ns == before


def test_sync_never_raises_on_an_unwritable_workspace(tmp_path):
    # Chat must survive a read-only workspace; guidance is best-effort.
    target = tmp_path / "AGENTS.md"
    target.mkdir()  # a directory where a file is expected
    sync_agents_md(tmp_path)


def test_sync_never_raises_on_a_missing_workspace(tmp_path):
    sync_agents_md(tmp_path / "does-not-exist")


def test_guidance_mentions_the_workflow_and_conduct_rules():
    assert "sciqlop_products_tree" in SCIQLOP_GUIDANCE
    assert "sciqlop_wait_for_plot_data" in SCIQLOP_GUIDANCE
    assert "sciqlop_api_reference" in SCIQLOP_GUIDANCE


def test_guidance_scopes_the_tools_to_sciqlop_and_warns_about_editing_the_block():
    # The same workspace opened with a bare CLI must not read these as its own
    # tools, and a user editing inside the markers must know it gets overwritten.
    assert "only" in SCIQLOP_GUIDANCE and "SciQLop" in SCIQLOP_GUIDANCE
    assert "overwritten" in SCIQLOP_GUIDANCE


def test_load_guidance_publishes_then_returns_the_merged_file(tmp_path):
    text = load_guidance(tmp_path)
    assert _managed(text) == SCIQLOP_GUIDANCE.strip()
    assert text == (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_load_guidance_returns_the_users_own_sections_too(tmp_path):
    # The whole point of the file: backends without a filesystem still get the
    # workspace-specific rules the user wrote.
    (tmp_path / "AGENTS.md").write_text(
        "# House rules\n\nMMS burst intervals only\n", encoding="utf-8")
    text = load_guidance(tmp_path)
    assert "MMS burst intervals only" in text
    assert _managed(text) == SCIQLOP_GUIDANCE.strip()


def test_load_guidance_falls_back_to_the_constant_when_the_file_is_unusable(tmp_path):
    (tmp_path / "AGENTS.md").mkdir()  # unwritable and unreadable as a file
    assert load_guidance(tmp_path) == SCIQLOP_GUIDANCE.strip()


def test_guidance_pushes_the_declarative_virtual_product_form():
    assert "Depends(" in SCIQLOP_GUIDANCE
    assert "%%vp" in SCIQLOP_GUIDANCE
    assert "Scalar[" in SCIQLOP_GUIDANCE
    assert "spz.get_data` in the body" in SCIQLOP_GUIDANCE


def test_guidance_names_the_panel_layout_tools():
    for tool in ("sciqlop_plot_product", "sciqlop_describe_panel",
                 "sciqlop_remove_graph", "sciqlop_remove_plot", "sciqlop_move_plot"):
        assert tool in SCIQLOP_GUIDANCE, tool


def test_guidance_forbids_calling_qt_object_methods_generically():
    # GH #145: an agent looped over a graph component's zero-argument methods
    # from the kernel thread, called deleteLater() and segfaulted SciQLop.
    assert "kernel thread" in SCIQLOP_GUIDANCE
    assert "_impl" in SCIQLOP_GUIDANCE
    assert "deleteLater" in SCIQLOP_GUIDANCE
    assert "sciqlop_describe_panel" in SCIQLOP_GUIDANCE


def test_guidance_explains_speasy_numpy_layer():
    assert "NumPy-compatible" in SCIQLOP_GUIDANCE
    assert "v.values" in SCIQLOP_GUIDANCE


def test_guidance_column_selection_example_is_not_a_hallucinated_label():
    # `b["Bx"]` raises on real products (e.g. MMS FGM labels are 'Bx GSE', ...);
    # guidance must tell agents to check v.columns instead of assuming a label.
    assert 'b["Bx"]' not in SCIQLOP_GUIDANCE
    assert ".columns" in SCIQLOP_GUIDANCE


def test_guidance_asks_agents_to_settle_open_choices_before_acting():
    # An agent asked for |V_alpha - V_p| started fetching and building before
    # anyone confirmed what the user meant; one question up front is cheaper.
    assert "### Before you start" in SCIQLOP_GUIDANCE
    assert "at most three" in SCIQLOP_GUIDANCE
    assert SCIQLOP_GUIDANCE.index("### Before you start") < SCIQLOP_GUIDANCE.index("### Plotting workflow")


def test_guidance_tells_agents_to_try_the_maths_before_writing_a_vp():
    # An agent spent ~10 tool calls hunting speasy uids to test its maths,
    # unaware sciqlop_fetch loads `//` tree paths into the kernel.
    assert "sciqlop_fetch" in SCIQLOP_GUIDANCE
    assert ".claude/skills/sciqlop-virtual-products/SKILL.md" in SCIQLOP_GUIDANCE


def _bundled_skills():
    from SciQLop.components.agents.skills import BUNDLED_SKILLS_DIR
    return sorted(p.parent for p in BUNDLED_SKILLS_DIR.glob("*/SKILL.md"))


def _frontmatter(skill_md):
    head = skill_md.read_text(encoding="utf-8").split("---", 2)[1]
    return dict(line.split(":", 1) for line in head.strip().splitlines())


def test_the_virtual_products_skill_is_bundled():
    assert "sciqlop-virtual-products" in [d.name for d in _bundled_skills()]


def test_every_skill_agents_md_points_at_is_bundled():
    import re
    named = set(re.findall(r"(sciqlop-[a-z-]+)/SKILL\.md", SCIQLOP_GUIDANCE))
    assert named and named <= {d.name for d in _bundled_skills()}, sorted(named)


@pytest.mark.parametrize("skill_dir", _bundled_skills(), ids=lambda d: d.name)
def test_agents_md_points_at_every_bundled_skill(skill_dir):
    # Agents that do not load skills (Albert, Copilot, ...) only find a skill
    # through the file path written in AGENTS.md.
    assert f"{skill_dir.name}/SKILL.md" in SCIQLOP_GUIDANCE


@pytest.mark.parametrize("skill_dir", _bundled_skills(), ids=lambda d: d.name)
def test_bundled_skill_frontmatter_matches_the_agent_skills_format(skill_dir):
    # opencode rejects a skill whose name differs from its directory or is not
    # lowercase-hyphenated, and needs a description to decide when to load it.
    import re
    meta = _frontmatter(skill_dir / "SKILL.md")
    assert meta["name"].strip() == skill_dir.name
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", skill_dir.name)
    assert meta["description"].strip().startswith("Use when")
    assert len(meta["description"].strip()) <= 1024


def test_load_guidance_publishes_every_bundled_skill(tmp_path):
    load_guidance(tmp_path)
    for skill_dir in _bundled_skills():
        published = tmp_path / ".claude" / "skills" / skill_dir.name / "SKILL.md"
        assert published.read_text(encoding="utf-8") == (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_strip_legacy_alignment_removes_only_the_old_preamble():
    from SciQLop.components.agents.guidance import LEGACY_ALIGNMENT, strip_legacy_alignment
    assert strip_legacy_alignment(f"{LEGACY_ALIGNMENT}\nplot B") == "plot B"
    assert strip_legacy_alignment("plot B") == "plot B"
    assert strip_legacy_alignment(LEGACY_ALIGNMENT) == ""


def test_strip_legacy_alignment_also_after_a_version_reminder():
    """0.13.0 sent `version_reminder + ALIGNMENT + prompt` when a session was
    resumed across an update; the preamble wasn't at the start of those."""
    from SciQLop.components.agents.guidance import LEGACY_ALIGNMENT, strip_legacy_alignment
    reminder = ("Note: SciQLop was updated from 0.12.2 to 0.13.0 since this session started. "
                "API capabilities may have changed; verify the current API with "
                "sciqlop_api_reference before assuming limitations.\n")
    assert strip_legacy_alignment(f"{reminder}{LEGACY_ALIGNMENT}\nplot B") == f"{reminder}plot B"
