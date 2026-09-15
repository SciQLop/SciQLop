"""Live-streamed agent messages must render the same markdown as session replay.

Backends that emit complete per-message texts (e.g. Claude: one AssistantMessage
per API round) had every text glued onto the previous one with no separator
("…done.## Results"), corrupting markdown during live streaming — while session
replay (one TextBlock per stored block, each rendered as its own markdown
document) was fine. Stream blocks now carry a ``complete`` flag: complete
blocks stay separate, delta blocks keep merging. ThinkingBlock surfaces the
model's thinking in the transcript instead of dropping it.
"""
import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


@pytest.fixture
def append_block(qapp):
    from SciQLop.components.agents.chat_dock import AgentChatDock

    return AgentChatDock._append_block


@pytest.fixture
def assistant_message():
    from SciQLop.components.agents.chat import ChatMessage

    return ChatMessage(role="assistant", blocks=[])


def test_complete_text_blocks_stay_separate(append_block, assistant_message):
    from SciQLop.components.agents.chat import TextBlock

    append_block(assistant_message, TextBlock(text="Done.", complete=True))
    append_block(assistant_message, TextBlock(text="## Results", complete=True))
    assert [b.text for b in assistant_message.blocks] == ["Done.", "## Results"]


def test_delta_text_blocks_merge(append_block, assistant_message):
    from SciQLop.components.agents.chat import TextBlock

    append_block(assistant_message, TextBlock(text="Hel"))
    append_block(assistant_message, TextBlock(text="lo"))
    assert [b.text for b in assistant_message.blocks] == ["Hello"]


def test_delta_after_complete_block_starts_a_new_block(append_block, assistant_message):
    from SciQLop.components.agents.chat import TextBlock

    append_block(assistant_message, TextBlock(text="first", complete=True))
    append_block(assistant_message, TextBlock(text="second"))
    assert [b.text for b in assistant_message.blocks] == ["first", "second"]


def test_thinking_blocks_merge_but_never_mix_with_text(append_block, assistant_message):
    from SciQLop.components.agents.chat import TextBlock, ThinkingBlock

    append_block(assistant_message, ThinkingBlock(text="hmm "))
    append_block(assistant_message, ThinkingBlock(text="ok", complete=True))
    append_block(assistant_message, TextBlock(text="Answer", complete=True))
    thinking, text = assistant_message.blocks
    assert isinstance(thinking, ThinkingBlock) and thinking.text == "hmm ok"
    assert isinstance(text, TextBlock) and text.text == "Answer"


def _heading_levels(doc) -> set:
    return {
        doc.findBlockByNumber(i).blockFormat().headingLevel()
        for i in range(doc.blockCount())
    }


def test_streamed_heading_renders_as_a_heading(qapp, append_block):
    """The user-visible symptom: a '## …' message streamed right after a
    sentence must render as a real heading, not fuse into the paragraph."""
    from SciQLop.components.agents.chat import ChatMessage, TextBlock, TranscriptView

    message = ChatMessage(role="assistant", blocks=[])
    append_block(message, TextBlock(text="Let me check the panel.", complete=True))
    append_block(message, TextBlock(text="## Results\nAll good.", complete=True))

    view = TranscriptView()
    view.render_messages([message])
    view.flush_now()
    assert 2 in _heading_levels(view.document())


def test_thinking_appears_in_transcript(qapp):
    from SciQLop.components.agents.chat import ChatMessage, ThinkingBlock, TranscriptView

    message = ChatMessage(
        role="assistant", blocks=[ThinkingBlock(text="pondering the data", complete=True)]
    )
    view = TranscriptView()
    view.render_messages([message])
    view.flush_now()
    assert "pondering the data" in view.document().toPlainText()


def test_angle_brackets_in_prose_do_not_swallow_the_rest(qapp):
    """`sciqlop_api_reference('<module>')` outside a code span read as an HTML
    tag and everything after it vanished (empty bullets in the transcript)."""
    from SciQLop.components.agents.chat import ChatMessage, TextBlock, TranscriptView
    message = ChatMessage(role="user", blocks=[TextBlock(
        text="- call sciqlop_api_reference('<module>') first\n- then plot <T> things\n- and finish",
        complete=True)], done=True)
    view = TranscriptView()
    view.render_messages([message])
    view.flush_now()
    text = view.document().toPlainText()
    assert "<module>" in text and "<T> things" in text and "and finish" in text
