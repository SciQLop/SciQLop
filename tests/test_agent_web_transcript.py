"""The web transcript renderer: a QWebEngineView-backed view with the same
public surface as the native TranscriptView, driven by a QWebChannel bridge.
Runs browser-free (SCIQLOP_TEST_NO_WEBENGINE=1, set in conftest.py): the
QWebEngineView itself is swapped for a plain placeholder widget, but the
backend QObject and channel exist, so the Python-side model computation and
signal emission are fully exercised here.
"""
import json

import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


@pytest.fixture
def view(qtbot, sciqlop_resources):  # noqa: F811 — pytest fixture injection
    from SciQLop.components.agents.chat.web_view import WebTranscriptView

    v = WebTranscriptView()
    qtbot.addWidget(v)
    return v


def _one_message():
    from SciQLop.components.agents.chat import ChatMessage, TextBlock
    return [ChatMessage(role="user", blocks=[TextBlock(text="hello", complete=True)], done=True)]


def test_exposes_the_same_public_surface_as_the_native_view(view):
    assert hasattr(view, "render_messages")
    assert hasattr(view, "flush_now")
    assert hasattr(view, "set_tool_verbosity")
    assert hasattr(view, "set_assistant_label")


def test_flush_now_emits_transcript_changed_matching_the_render_model(view, qtbot):
    from SciQLop.components.agents.chat.render_model import transcript_model

    messages = _one_message()
    with qtbot.waitSignal(view.backend.transcript_changed, timeout=1000) as blocker:
        view.render_messages(messages)
        view.flush_now()

    expected = transcript_model(
        messages, verbosity=1, expanded=set(),
        role_labels={"user": "You", "assistant": "Assistant", "error": "Error"})
    assert json.loads(blocker.args[0]) == expected


def test_toggle_flips_expansion_and_re_emits(view, qtbot):
    from SciQLop.components.agents.chat import ChatMessage, ToolActivityBlock

    messages = [ChatMessage(role="assistant",
                            blocks=[ToolActivityBlock(tool_name="a", id="g1")], done=True)]
    view.render_messages(messages)
    view.flush_now()

    with qtbot.waitSignal(view.backend.transcript_changed, timeout=1000) as blocker:
        view.backend.toggle("g1")
    model = json.loads(blocker.args[0])
    assert model[0]["parts"][0]["expanded"] is True

    with qtbot.waitSignal(view.backend.transcript_changed, timeout=1000) as blocker:
        view.backend.toggle("g1")
    model = json.loads(blocker.args[0])
    assert model[0]["parts"][0]["expanded"] is False


def test_open_link_opens_http_and_https(view, monkeypatch):
    from SciQLop.components.agents.chat import web_view as mod

    opened = []
    monkeypatch.setattr(mod.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))

    view.backend.open_link("https://example.com")
    view.backend.open_link("http://example.com")
    assert opened == ["https://example.com", "http://example.com"]


def test_open_link_ignores_non_http_schemes(view, monkeypatch):
    from SciQLop.components.agents.chat import web_view as mod

    opened = []
    monkeypatch.setattr(mod.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))

    view.backend.open_link("file:///etc/passwd")
    view.backend.open_link("javascript:alert(1)")
    assert opened == []


def test_current_state_returns_the_last_json(view):
    messages = _one_message()
    view.render_messages(messages)
    view.flush_now()

    from SciQLop.components.agents.chat.render_model import transcript_model
    expected = transcript_model(
        messages, verbosity=1, expanded=set(),
        role_labels={"user": "You", "assistant": "Assistant", "error": "Error"})
    assert json.loads(view.backend.current_state()) == expected


def test_set_tool_verbosity_reflows_the_last_render(view, qtbot):
    from SciQLop.components.agents.chat import ChatMessage, ToolActivityBlock

    messages = [ChatMessage(role="assistant", blocks=[
        ToolActivityBlock(tool_name="a", tool_input={"x": "y"}, id="g1")], done=True)]
    view.render_messages(messages)
    view.flush_now()

    with qtbot.waitSignal(view.backend.transcript_changed, timeout=1000) as blocker:
        view.set_tool_verbosity(2)
    model = json.loads(blocker.args[0])
    assert model[0]["parts"][0]["steps"][0]["input"] == "x=y"


def test_set_assistant_label_changes_the_assistant_role_label(view, qtbot):
    from SciQLop.components.agents.chat import ChatMessage

    view.set_assistant_label("Claude")
    messages = [ChatMessage(role="assistant", blocks=[], done=True)]
    with qtbot.waitSignal(view.backend.transcript_changed, timeout=1000) as blocker:
        view.render_messages(messages)
        view.flush_now()
    model = json.loads(blocker.args[0])
    assert model[0]["label"] == "Claude"
