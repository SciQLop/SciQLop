"""The transcript keeps the reader's place: bottom stays bottom while streaming,
a scrolled-back reader stays where they are, and toggling a tool node never
teleports the view."""
from PySide6.QtCore import QUrl

from .fixtures import *


def _long_transcript(n=40):
    from SciQLop.components.agents.chat import ChatMessage, TextBlock, ToolActivityBlock
    messages = []
    for i in range(n):
        messages.append(ChatMessage(role="user", blocks=[TextBlock(text=f"question {i}\n" * 3, complete=True)], done=True))
        messages.append(ChatMessage(role="assistant", blocks=[
            ToolActivityBlock(tool_name="exec_python", tool_input={"code": f"x={i}"}, result="ok" * 40, tool_use_id=f"t{i}", id=f"g{i}"),
            TextBlock(text=f"answer {i}\n" * 3, complete=True)], done=True))
    return messages


def _view(qtbot, messages):
    from SciQLop.components.agents.chat import TranscriptView
    view = TranscriptView()
    view.resize(400, 300)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)
    view.render_messages(messages)
    view.flush_now()
    qtbot.wait(50)
    return view


def _at_bottom(view) -> bool:
    bar = view.verticalScrollBar()
    return bar.maximum() > 0 and bar.value() == bar.maximum()


def test_first_render_lands_at_the_bottom(qtbot):
    view = _view(qtbot, _long_transcript())
    assert _at_bottom(view)


def test_streaming_keeps_the_view_pinned_to_the_bottom(qtbot):
    messages = _long_transcript()
    view = _view(qtbot, messages)
    for i in range(5):
        messages[-1].blocks[-1].text += f"more text {i}\n" * 4
        view.render_messages(messages)
        view.flush_now()
        qtbot.wait(30)
        assert _at_bottom(view), f"lost the bottom on update {i}"


def test_toggling_a_tool_node_keeps_the_scroll_position(qtbot):
    view = _view(qtbot, _long_transcript())
    bar = view.verticalScrollBar()
    bar.setValue(bar.maximum() // 3)
    qtbot.wait(30)
    before = bar.value()
    view._on_anchor_clicked(QUrl("toggle:g5"))
    view.flush_now()
    qtbot.wait(50)
    assert abs(bar.value() - before) <= 2, (before, bar.value())
    assert not _at_bottom(view)


def test_streaming_leaves_a_scrolled_back_reader_alone(qtbot):
    messages = _long_transcript()
    view = _view(qtbot, messages)
    bar = view.verticalScrollBar()
    bar.setValue(bar.maximum() // 3)
    qtbot.wait(30)
    before = bar.value()
    messages[-1].blocks[-1].text += "more\n" * 20
    view.render_messages(messages)
    view.flush_now()
    qtbot.wait(50)
    assert abs(bar.value() - before) <= 2, (before, bar.value())


def test_scrolling_back_to_the_bottom_re_arms_following(qtbot):
    messages = _long_transcript()
    view = _view(qtbot, messages)
    bar = view.verticalScrollBar()
    bar.setValue(bar.maximum() // 3)
    qtbot.wait(30)
    bar.setValue(bar.maximum())
    qtbot.wait(30)
    messages[-1].blocks[-1].text += "more\n" * 20
    view.render_messages(messages)
    view.flush_now()
    qtbot.wait(50)
    assert _at_bottom(view)
