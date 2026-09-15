"""The web transcript renderer works off a JSON-serialisable model built from
the same message/block dataclasses as the native `TranscriptView`. These
tests pin down its shape without touching any Qt widget."""
import json

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


def _model(messages, verbosity=1, expanded=None):
    from SciQLop.components.agents.chat.render_model import transcript_model
    return transcript_model(
        messages, verbosity=verbosity, expanded=expanded or set(),
        role_labels={"user": "You", "assistant": "Assistant", "error": "Error"})


def test_text_thinking_and_tool_parts_in_order():
    from SciQLop.components.agents.chat import (
        ChatMessage, TextBlock, ThinkingBlock, ToolActivityBlock)

    message = ChatMessage(role="assistant", blocks=[
        ThinkingBlock(text="pondering", complete=True),
        TextBlock(text="Hello **world**", complete=True),
        ToolActivityBlock(tool_name="exec_python", tool_input={"code": "1+1"},
                          result="2", id="g1"),
    ], done=True)

    [entry] = _model([message])
    assert entry["role"] == "assistant"
    assert entry["label"] == "Assistant"
    assert entry["done"] is True
    types = [p["type"] for p in entry["parts"]]
    assert types == ["thinking", "text", "tools"]
    assert entry["parts"][0]["text"] == "pondering"
    assert entry["parts"][1]["markdown"] == "Hello **world**"


def test_consecutive_tool_blocks_group_into_one_tools_part():
    from SciQLop.components.agents.chat import ChatMessage, ToolActivityBlock

    message = ChatMessage(role="assistant", blocks=[
        ToolActivityBlock(tool_name="a", id="g1"),
        ToolActivityBlock(tool_name="b", id="g2"),
    ], done=True)

    [entry] = _model([message])
    assert len(entry["parts"]) == 1
    part = entry["parts"][0]
    assert part["type"] == "tools"
    assert part["id"] == "g1"                 # first block's id
    assert [s["name"] for s in part["steps"]] == ["a", "b"]


def test_tool_group_running_reflects_message_done():
    from SciQLop.components.agents.chat import ChatMessage, ToolActivityBlock

    running_msg = ChatMessage(
        role="assistant", blocks=[ToolActivityBlock(tool_name="a", id="g1")], done=False)
    finished_msg = ChatMessage(
        role="assistant", blocks=[ToolActivityBlock(tool_name="a", id="g1")], done=True)

    assert _model([running_msg])[0]["parts"][0]["running"] is True
    assert _model([finished_msg])[0]["parts"][0]["running"] is False


def test_tool_group_expanded_tracks_the_expanded_set():
    from SciQLop.components.agents.chat import ChatMessage, ToolActivityBlock

    message = ChatMessage(
        role="assistant", blocks=[ToolActivityBlock(tool_name="a", id="g1")], done=True)

    assert _model([message], expanded=set())[0]["parts"][0]["expanded"] is False
    assert _model([message], expanded={"g1"})[0]["parts"][0]["expanded"] is True


def test_input_only_shown_at_verbosity_2_and_above():
    from SciQLop.components.agents.chat import ChatMessage, ToolActivityBlock

    message = ChatMessage(role="assistant", blocks=[
        ToolActivityBlock(tool_name="a", tool_input={"path": "amda"}, id="g1")
    ], done=True)

    step1 = _model([message], verbosity=1)[0]["parts"][0]["steps"][0]
    step2 = _model([message], verbosity=2)[0]["parts"][0]["steps"][0]
    assert step1["input"] is None
    assert step2["input"] == "path=amda"


def test_result_only_shown_at_verbosity_3_and_truncated_at_200_chars():
    from SciQLop.components.agents.chat import ChatMessage, ToolActivityBlock

    long_result = "x" * 250
    message = ChatMessage(role="assistant", blocks=[
        ToolActivityBlock(tool_name="a", result=long_result, id="g1")
    ], done=True)

    step2 = _model([message], verbosity=2)[0]["parts"][0]["steps"][0]
    step3 = _model([message], verbosity=3)[0]["parts"][0]["steps"][0]
    assert step2["result"] is None
    assert step3["result"] == "x" * 199 + "…"
    assert len(step3["result"]) == 200


def test_empty_text_and_thinking_blocks_are_skipped():
    from SciQLop.components.agents.chat import ChatMessage, TextBlock, ThinkingBlock

    message = ChatMessage(role="assistant", blocks=[
        TextBlock(text="", complete=True),
        ThinkingBlock(text="", complete=True),
        TextBlock(text="real content", complete=True),
    ], done=True)

    [entry] = _model([message])
    assert len(entry["parts"]) == 1
    assert entry["parts"][0]["markdown"] == "real content"


def test_missing_image_path_yields_a_placeholder_text_part(tmp_path):
    from SciQLop.components.agents.chat import ChatMessage, ImageBlock

    message = ChatMessage(
        role="assistant",
        blocks=[ImageBlock(path=str(tmp_path / "does_not_exist.png"))], done=True)

    [entry] = _model([message])
    assert entry["parts"] == [{"type": "text", "markdown": "*[missing image]*"}]


def test_a_real_image_becomes_a_png_data_url(tmp_path):
    from PySide6.QtGui import QImage

    from SciQLop.components.agents.chat import ChatMessage, ImageBlock

    path = tmp_path / "shot.png"
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(0xFF0000)
    assert image.save(str(path), "PNG")

    message = ChatMessage(role="assistant", blocks=[ImageBlock(path=str(path))], done=True)
    [entry] = _model([message])
    [part] = entry["parts"]
    assert part["type"] == "image"
    assert part["data_url"].startswith("data:image/png;base64,")


def test_model_output_survives_json_dumps():
    from SciQLop.components.agents.chat import ChatMessage, TextBlock, ToolActivityBlock

    messages = [
        ChatMessage(role="user", blocks=[TextBlock(text="hi", complete=True)], done=True),
        ChatMessage(role="assistant", blocks=[
            ToolActivityBlock(tool_name="a", tool_input={"x": 1}, result="ok", id="g1"),
            TextBlock(text="done", complete=True),
        ], done=True),
    ]
    serialized = json.dumps(_model(messages, verbosity=3, expanded={"g1"}))
    restored = json.loads(serialized)
    assert restored[0]["role"] == "user"
    assert restored[1]["parts"][0]["expanded"] is True
