"""The web transcript's JavaScript, run in a real browser (opt-in: it starts
Chromium). Set SCIQLOP_WEBENGINE_TESTS=1 to run it."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("SCIQLOP_WEBENGINE_TESTS") != "1",
                                reason="starts Chromium; set SCIQLOP_WEBENGINE_TESTS=1")


@pytest.fixture(scope="module")
def report():
    env = {k: v for k, v in os.environ.items() if k != "SCIQLOP_NO_WEBENGINE"}
    child = Path(__file__).with_name("_web_transcript_child.py")
    run = subprocess.run([sys.executable, str(child)], env=env, capture_output=True,
                         text=True, timeout=120, cwd=Path(__file__).parent.parent)
    lines = [line for line in run.stdout.splitlines() if line.startswith("{")]
    assert lines, run.stdout + run.stderr
    return json.loads(lines[-1])


def test_a_markdown_image_does_not_fetch_a_remote_url(report):
    assert report["remote_hits"] == []


def test_an_expanded_tool_group_stays_expanded(report):
    assert report["expanded_after_toggle"] is True


def test_a_theme_reload_keeps_expanded_tool_groups(report):
    assert report["expanded_after_reload"] is True


def test_a_resize_keeps_the_readers_scroll_position(report):
    assert report["scroll_y_after_resize"] == 100


def test_dollars_in_a_tilde_fence_stay_code(report):
    assert report["tilde_code"].strip() == "ls $HOME/$USER"


def test_dollars_in_a_double_backtick_span_stay_code(report):
    assert "a $b$ c" in report["double_tick"]


def test_math_in_a_link_title_does_not_break_the_link(report):
    assert report["link_title"] == "$y$"


def test_ordinary_math_still_renders_with_katex(report):
    assert report["katex_count"] == 1


def test_dollars_in_an_indented_code_block_stay_code(report):
    assert "total = $a$ + $b$" in report["indented_code"]


def test_an_unchanged_part_is_not_rebuilt_when_its_message_changes(report):
    """Parts were compared by outerHTML, which the browser normalises (<br/>
    becomes <br>, quotes in text are re-escaped), so thinking parts never
    matched and were rebuilt on every streamed tick."""
    assert report["unchanged_part_kept"] is True
