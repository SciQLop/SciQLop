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
