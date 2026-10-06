"""Every tool the published guidance names must exist (needs QApplication → qtbot).

The guidance and the bundled skills are prose written by hand; a renamed or
removed tool would leave agents calling something that is not there.

A tool is referenced as inline code, `sciqlop_fetch` or `sciqlop_fetch(...)`.
Plugin package names share the `sciqlop_` prefix but only appear in code
blocks and folder trees, so they are not mistaken for tools.
"""
import re
from unittest.mock import MagicMock

import pytest

from SciQLop.components.agents.guidance import SCIQLOP_GUIDANCE
from SciQLop.components.agents.skills import BUNDLED_SKILLS_DIR

_TOOL_NAME = re.compile(r"`(sciqlop_[a-z_]+)[`(]")

_DOCUMENTS = {"AGENTS.md": SCIQLOP_GUIDANCE} | {
    str(p.relative_to(BUNDLED_SKILLS_DIR)): p.read_text(encoding="utf-8")
    for p in sorted(BUNDLED_SKILLS_DIR.rglob("*.md"))
}


@pytest.fixture(scope="module")
def registered_tools():
    import SciQLop.components.agents.tools._builder as builder
    return {t["name"] for t in builder.build_sciqlop_tools(MagicMock())}


@pytest.mark.parametrize("document", sorted(_DOCUMENTS))
def test_every_named_tool_is_registered(qtbot, registered_tools, document):
    named = set(_TOOL_NAME.findall(_DOCUMENTS[document]))
    assert named <= registered_tools, f"{document} names unknown tools: {sorted(named - registered_tools)}"
