"""`AcpStreamTranslator` converts ACP session updates into the StreamBlocks
the chat consumer expects: text/thought chunks forwarded as incomplete
blocks, closed on interruption or turn end; tool calls and progress mapped
to ToolActivityBlocks correlated by tool_call_id.
"""
import pytest

pytestmark = pytest.mark.skipif(
    pytest.importorskip("acp") is None, reason="agent-client-protocol not installed"
)

from SciQLop.components.agents.acp.stream import AcpStreamTranslator
from SciQLop.components.agents.chat import (
    ImageBlock,
    TextBlock,
    ThinkingBlock,
    ToolActivityBlock,
)


def _text_chunk(text):
    from acp.helpers import update_agent_message_text
    return update_agent_message_text(text)


def _thought_chunk(text):
    from acp.helpers import update_agent_thought_text
    return update_agent_thought_text(text)


def _feed(stream, update):
    return [b for b in stream.feed(update) if b is not None]


def test_text_chunks_forward_and_close_on_flush(tmp_path):
    stream = AcpStreamTranslator(tmp_path)
    out = _feed(stream, _text_chunk("Hello"))
    out += _feed(stream, _text_chunk(" world"))
    out += [b for b in stream.flush() if b is not None]
    assert out == [
        TextBlock(text="Hello", complete=False),
        TextBlock(text=" world", complete=False),
        TextBlock(text="", complete=True),
    ]


def test_thought_and_text_interleave_close_each_other(tmp_path):
    stream = AcpStreamTranslator(tmp_path)
    out = _feed(stream, _thought_chunk("hmm"))
    out += _feed(stream, _text_chunk("answer"))
    out += [b for b in stream.flush() if b is not None]
    assert out == [
        ThinkingBlock(text="hmm", complete=False),
        ThinkingBlock(text="", complete=True),
        TextBlock(text="answer", complete=False),
        TextBlock(text="", complete=True),
    ]


def _activity(block):
    """ToolActivityBlock carries a random uuid id — compare the stable fields."""
    assert isinstance(block, ToolActivityBlock)
    return (block.tool_name, block.tool_input, block.result, block.tool_use_id)


def test_tool_call_start_closes_text_and_emits_activity(tmp_path):
    from acp import helpers
    stream = AcpStreamTranslator(tmp_path)
    out = _feed(stream, _text_chunk("Working"))
    out += _feed(stream, helpers.start_tool_call(
        "tc1", "sciqlop_screenshot_panel", raw_input={"name": "P1"},
    ))
    assert out[:2] == [
        TextBlock(text="Working", complete=False),
        TextBlock(text="", complete=True),
    ]
    assert _activity(out[2]) == (
        "sciqlop_screenshot_panel", {"name": "P1"}, None, "tc1")


def test_tool_progress_emits_result_only_block(tmp_path):
    from acp import helpers
    stream = AcpStreamTranslator(tmp_path)
    out = _feed(stream, helpers.update_tool_call(
        "tc1", status="completed", raw_output="panel PNG captured",
    ))
    assert len(out) == 1
    assert _activity(out[0]) == ("", {}, "panel PNG captured", "tc1")


def test_tool_progress_with_image_writes_image_block(tmp_path):
    from acp import helpers
    stream = AcpStreamTranslator(tmp_path)
    out = _feed(stream, helpers.update_tool_call(
        "tc1",
        content=[helpers.tool_content(helpers.text_block("screenshot")),
                 helpers.tool_content(helpers.image_block("QUJD", "image/png"))],
    ))
    images = [b for b in out if isinstance(b, ImageBlock)]
    assert images
    for b in images:
        assert (tmp_path / b.path.split("/")[-1]).exists()
    activities = [b for b in out if isinstance(b, ToolActivityBlock)]
    assert activities and _activity(activities[0]) == ("", {}, "screenshot", "tc1")


def test_untracked_updates_emit_nothing(tmp_path):
    from acp import helpers
    stream = AcpStreamTranslator(tmp_path)
    assert _feed(stream, helpers.update_current_mode("yolo")) == []
    assert _feed(stream, helpers.update_plan([])) == []


def test_end_to_end_against_consumer_contract(tmp_path):
    """The translator's deltas, fed through the dock's text append-merge logic,
    reconstruct the final text with no duplication."""
    stream = AcpStreamTranslator(tmp_path)

    def append_block(blocks, block):  # mirrors AgentChatDock._append_block (text path)
        if isinstance(block, TextBlock):
            last = blocks[-1] if blocks else None
            if type(last) is TextBlock and not last.complete:
                last.text += block.text
                last.complete = block.complete
                return
        blocks.append(block)

    rendered = []
    for delta in ["Hello", " world", ", plotting now."]:
        for b in _feed(stream, _text_chunk(delta)):
            append_block(rendered, b)
    for b in stream.flush():
        if b is not None:
            append_block(rendered, b)
    text = "".join(b.text for b in rendered if isinstance(b, TextBlock))
    assert text == "Hello world, plotting now."
    assert sum(1 for b in rendered if isinstance(b, TextBlock)) == 1
