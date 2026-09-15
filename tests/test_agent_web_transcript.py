"""The web transcript renderer: a QWebEngineView-backed view with the same
public surface as the native TranscriptView, driven by a QWebChannel bridge.
Runs browser-free (SCIQLOP_TEST_NO_WEBENGINE=1, set in conftest.py): the
QWebEngineView itself is swapped for a plain placeholder widget, but the
backend QObject and channel exist, so the Python-side model computation and
signal emission are fully exercised here.
"""
import asyncio
import json

import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures

_FAKE = "FakeAgent"


class _FakeBackend:
    display_name = _FAKE
    model_choices = [("Fast", "fast"), ("Smart", "smart")]
    supports_sessions = False

    def __init__(self, ctx=None):
        self.model = None
        self.effort = "unset"
        self.write_mode = None
        self.snapshot = None

    async def usage_snapshot(self):
        return self.snapshot

    def effort_values(self):
        return ()

    async def set_effort(self, effort):
        self.effort = effort

    async def set_model(self, model):
        self.model = model

    def set_write_mode(self, mode):
        self.write_mode = mode

    async def list_slash_commands(self):
        return []

    def list_sessions(self):
        return []

    def load_session(self, session_id, image_tempdir):
        return []

    async def reset(self):
        pass

    async def cancel(self):
        pass

    async def resume(self, session_id):
        pass

    def current_session_id(self):
        return None

    def ask(self, prompt, image_paths=None):
        raise NotImplementedError


def _settle(qtbot):
    """Let the dock's spawned tasks run — qasync steps them from the Qt loop."""
    qtbot.wait(20)


@pytest.fixture
def dock(qtbot, sciqlop_resources, monkeypatch):  # noqa: F811 — pytest fixture injection
    """A chat dock bound to a fake backend (copied from
    test_agent_chat_dock_wiring.py::dock — not imported, so this file's
    setup does not depend on that module's fixtures changing)."""
    from SciQLop.components.agents import model_capabilities
    from SciQLop.components.agents.chat_dock import AgentChatDock
    from SciQLop.components.agents.registry import (
        register_agent_backend, unregister_agent_backend)
    from SciQLop.components.agents.settings import AgentChatSettings

    async def _no_network():
        return None

    monkeypatch.setattr(model_capabilities, "ensure_registry_fresh", _no_network)
    saved = AgentChatSettings()
    restore = (dict(saved.effort), saved.tool_verbosity, saved.transcript_renderer)
    register_agent_backend(_FakeBackend)
    from SciQLop.core.sciqlop_application import sciqlop_event_loop
    loop = sciqlop_event_loop()
    asyncio.set_event_loop(loop)
    try:
        asyncio.events._set_running_loop(loop)
        widget = AgentChatDock(main_window=None)
        qtbot.addWidget(widget)
        _settle(qtbot)
        yield widget
        widget.close()
        _settle(qtbot)
    finally:
        asyncio.events._set_running_loop(None)
        unregister_agent_backend(_FAKE)
        with AgentChatSettings() as cfg:
            cfg.effort, cfg.tool_verbosity, cfg.transcript_renderer = restore


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


def test_dock_uses_the_web_view_when_the_setting_says_so(dock):
    from SciQLop.components.agents.chat.web_view import WebTranscriptView
    from SciQLop.components.agents.settings import AgentChatSettings

    with AgentChatSettings() as cfg:
        cfg.transcript_renderer = "web"
    assert isinstance(dock._make_transcript(dock._splitter), WebTranscriptView)


def test_dock_uses_the_native_view_when_the_setting_says_so(dock):
    from SciQLop.components.agents.chat import TranscriptView
    from SciQLop.components.agents.settings import AgentChatSettings

    with AgentChatSettings() as cfg:
        cfg.transcript_renderer = "native"
    assert type(dock._make_transcript(dock._splitter)) is TranscriptView


def test_a_failing_web_view_falls_back_to_native_with_a_status_message(dock, monkeypatch):
    from SciQLop.components.agents.chat import TranscriptView
    from SciQLop.components.agents.chat import web_view as web_view_mod
    from SciQLop.components.agents.settings import AgentChatSettings

    def _boom(*args, **kwargs):
        raise RuntimeError("no QtWebEngine")

    monkeypatch.setattr(web_view_mod, "WebTranscriptView", _boom)
    with AgentChatSettings() as cfg:
        cfg.transcript_renderer = "web"

    transcript = dock._make_transcript(dock._splitter)
    assert type(transcript) is TranscriptView
    assert "native" in dock._status_label.text().lower()


def test_switching_the_setting_swaps_the_widget_and_rerenders_the_session(dock, qtbot):
    from SciQLop.components.agents.chat import ChatMessage, TextBlock
    from SciQLop.components.agents.chat.web_view import WebTranscriptView
    from SciQLop.components.agents.settings import AgentChatSettings

    session = dock._sessions[dock._current]
    session.messages.append(ChatMessage(
        role="user", blocks=[TextBlock(text="hello web", complete=True)], done=True))

    with AgentChatSettings() as cfg:
        cfg.transcript_renderer = "web"
    dock._apply_transcript_renderer()
    _settle(qtbot)

    assert isinstance(dock._transcript, WebTranscriptView)
    assert dock._splitter.widget(0) is dock._transcript

    with qtbot.waitSignal(dock._transcript.backend.transcript_changed, timeout=1000) as blocker:
        dock._transcript.render_messages(session.messages)
        dock._transcript.flush_now()
    model = json.loads(blocker.args[0])
    assert any(
        part.get("markdown") == "hello web"
        for msg in model for part in msg["parts"] if part["type"] == "text")


def test_settings_notifier_triggers_the_live_swap(dock, qtbot):
    from SciQLop.components.agents.chat import TranscriptView
    from SciQLop.components.agents.chat.web_view import WebTranscriptView
    from SciQLop.components.agents.settings import AgentChatSettings

    assert type(dock._transcript) is TranscriptView
    with AgentChatSettings() as cfg:
        cfg.transcript_renderer = "web"
    _settle(qtbot)
    assert isinstance(dock._transcript, WebTranscriptView)
