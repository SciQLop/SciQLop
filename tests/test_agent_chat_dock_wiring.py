"""The slimmed chat header, the relocated controls and the info strip.

The dock keeps four controls in its header; model, effort, activity verbosity,
write-actions and export moved into the settings popup, and session usage is
reported by a strip under the input.
"""
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
        return ("low", "high") if self.model == "smart" else ()

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
def dock(qtbot, sciqlop_resources, monkeypatch):
    """A chat dock bound to a fake backend.

    Both the registry and the persisted chat settings are global, so each is
    restored on teardown — the dock writes effort and verbosity as the tests
    drive it.
    """
    from SciQLop.components.agents import model_capabilities
    from SciQLop.components.agents.chat_dock import AgentChatDock
    from SciQLop.components.agents.registry import (
        register_agent_backend, unregister_agent_backend)
    from SciQLop.components.agents.settings import AgentChatSettings

    async def _no_network():
        return None

    monkeypatch.setattr(model_capabilities, "ensure_registry_fresh", _no_network)
    saved = AgentChatSettings()
    restore = (dict(saved.effort), saved.tool_verbosity)
    register_agent_backend(_FakeBackend)
    try:
        widget = AgentChatDock(main_window=None)
        qtbot.addWidget(widget)
        _settle(qtbot)
        yield widget
    finally:
        unregister_agent_backend(_FAKE)
        with AgentChatSettings() as cfg:
            cfg.effort, cfg.tool_verbosity = restore


def _header_widgets(dock):
    header = dock.layout().itemAt(0).layout()
    return [header.itemAt(i).widget() for i in range(header.count())]


def test_header_keeps_only_four_controls_and_the_status_label(dock):
    assert _header_widgets(dock) == [
        dock._reset_btn, dock._backend_combo, dock._sessions_toggle,
        dock._settings_btn, dock._status_label]


def test_relocated_controls_live_in_the_popup(dock):
    popup = dock._settings_popup
    assert dock._model_combo is popup.model_combo
    assert dock._verbosity_combo is popup.verbosity_combo
    assert dock._writes_combo is popup.writes_combo
    # the enable/disable contract still points at live widgets
    assert dock._model_combo in dock._interactive
    assert dock._writes_combo in dock._interactive


def test_no_backend_disables_the_relocated_controls_too(dock):
    dock._set_enabled()
    assert all(w.isEnabled() for w in dock._interactive)
    dock._set_empty("no backends registered")
    assert not any(w.isEnabled() for w in dock._interactive)


def test_verbosity_still_drives_the_settings_from_the_popup(dock):
    from SciQLop.components.agents.settings import AgentChatSettings

    dock._verbosity_combo.setCurrentIndex(2)
    assert AgentChatSettings().tool_verbosity == 3
    dock._verbosity_combo.setCurrentIndex(0)
    assert AgentChatSettings().tool_verbosity == 1


def test_write_mode_combo_reaches_the_backend_and_persists(dock):
    from SciQLop.components.agents.settings import AgentChatSettings, AgentWriteMode

    backend = dock._current_backend()
    combo = dock._writes_combo

    # switch to yolo
    combo.setCurrentIndex(combo.findData(AgentWriteMode.YOLO))
    assert dock._write_mode == AgentWriteMode.YOLO
    assert backend.write_mode == AgentWriteMode.YOLO
    assert AgentChatSettings().write_mode == AgentWriteMode.YOLO
    assert "Yolo" in dock._status_label.text()

    # switch to none
    combo.setCurrentIndex(combo.findData(AgentWriteMode.NONE))
    assert dock._write_mode == AgentWriteMode.NONE
    assert backend.write_mode == AgentWriteMode.NONE
    assert AgentChatSettings().write_mode == AgentWriteMode.NONE
    assert "disabled" in dock._status_label.text()

    # switch back to confirm
    combo.setCurrentIndex(combo.findData(AgentWriteMode.CONFIRM))
    assert dock._write_mode == AgentWriteMode.CONFIRM
    assert backend.write_mode == AgentWriteMode.CONFIRM
    assert AgentChatSettings().write_mode == AgentWriteMode.CONFIRM
    assert "confirm" in dock._status_label.text().lower()


def test_export_still_reaches_the_dock_from_the_popup(dock, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    seen = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *args, **kw: seen.append(args[2])))
    dock._settings_popup.export_requested.emit()
    assert seen == ["Nothing to export yet."]


def test_model_choices_populate_the_popup_combo(dock):
    combo = dock._model_combo
    assert [combo.itemText(i) for i in range(combo.count())] == ["Fast", "Smart"]


def test_effort_is_read_back_only_once_the_model_switch_lands(dock, qtbot):
    """`effort_values()` answers for the model the backend currently holds, so
    the levels must be repopulated *after* `set_model` completes — repopulating
    while the switch is still an unawaited task narrows against the old model."""
    backend, popup = dock._current_backend(), dock._settings_popup
    assert not popup.is_effort_row_visible()   # nothing selected yet

    dock._model_combo.setCurrentIndex(1)       # "Smart"
    _settle(qtbot)
    assert backend.model == "smart"
    assert popup.is_effort_row_visible()
    assert [popup.effort_combo.itemText(i)
            for i in range(popup.effort_combo.count())] == ["Default", "low", "high"]

    dock._model_combo.setCurrentIndex(0)       # "Fast" offers no levels
    _settle(qtbot)
    assert not popup.is_effort_row_visible()


def test_choosing_an_effort_persists_it_tells_the_backend_and_shows(dock, qtbot):
    from SciQLop.components.agents.backend import UsageSnapshot
    from SciQLop.components.agents.settings import AgentChatSettings

    backend = dock._current_backend()
    backend.snapshot = UsageSnapshot(model="smart")
    dock._spawn(dock._usage_refresher.refresh())
    dock._model_combo.setCurrentIndex(1)
    _settle(qtbot)
    assert dock._info_bar.text() == "smart"

    dock._settings_popup.effort_combo.setCurrentIndex(2)   # "high"
    _settle(qtbot)
    assert AgentChatSettings().effort.get(_FAKE) == "high"
    assert backend.effort == "high"
    assert dock._info_bar.text() == "smart · high"


def test_usage_refresh_fills_the_strip(dock, qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot

    backend = dock._current_backend()
    assert dock._info_bar.text() == ""          # nothing reported on bind

    backend.snapshot = UsageSnapshot(
        model="smart", tokens=TokenCounts(input=1000, output=200),
        context_tokens=50_000, context_max=200_000)
    dock._spawn(dock._usage_refresher.refresh())
    _settle(qtbot)

    text = dock._info_bar.text()
    assert "smart" in text and "1.2k" in text and "25%" in text
    assert not dock._info_bar.isHidden()


def _context_snapshot(tokens):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot

    return UsageSnapshot(
        context_tokens=tokens, context_max=100_000,
        context_categories=(ContextCategory("Tools", tokens),))


def test_an_open_breakdown_popup_follows_the_refresh(dock, qtbot):
    """The ⓘ button refreshes usage, so the popup it was opened from must show
    the new numbers — not the figures it was seeded with."""
    backend = dock._current_backend()
    backend.snapshot = _context_snapshot(1000)
    dock._spawn(dock._usage_refresher.refresh())
    _settle(qtbot)

    dock._show_context_breakdown()
    _settle(qtbot)
    assert dock._breakdown_popup.category_rows == [("Tools", "1.0k")]

    backend.snapshot = _context_snapshot(2000)
    dock._spawn(dock._usage_refresher.refresh())
    _settle(qtbot)
    assert dock._breakdown_popup.category_rows == [("Tools", "2.0k")]
    dock._breakdown_popup.hide()


def test_a_late_capability_refresh_for_an_abandoned_backend_is_dropped(dock, qtbot):
    """`ensure_registry_fresh` can block for ~20s on a cold cache. A switch
    inside that window must not let the old backend's levels land in the single
    shared settings popup."""
    stale = _FakeBackend()
    stale.model = "smart"                      # would offer ("low", "high")
    assert stale is not dock._current_backend()

    dock._spawn(dock._refresh_capabilities_then_effort(stale))
    _settle(qtbot)
    assert not dock._settings_popup.is_effort_row_visible()


def test_binding_a_new_backend_clears_the_previous_effort_row(dock, qtbot):
    """The repopulate is deferred behind `ensure_registry_fresh` (up to ~20s on
    a cold cache) but ⚙ stays reachable, so the row must be emptied on the near
    side of the spawn — otherwise the user can pick a level from backend A and
    have it persisted against backend B."""
    from SciQLop.components.agents.backend import UsageSnapshot

    backend = dock._current_backend()
    backend.model = "smart"                    # offers ("low", "high")
    # a snapshot is what puts the strip on screen at all: `info_segments`
    # renders nothing for a None snapshot, so effort alone would be invisible
    # and the "high" assertion below could not distinguish cleared from empty.
    backend.snapshot = UsageSnapshot(model="smart")
    dock._spawn(dock._usage_refresher.refresh())
    dock._populate_effort(backend)
    dock._settings_popup.effort_combo.setCurrentIndex(2)   # "high"
    _settle(qtbot)
    assert dock._settings_popup.is_effort_row_visible()
    assert dock._info_bar.text() == "smart · high"

    from SciQLop.components.agents.chat_dock import _AgentSession

    other = _AgentSession(backend=_FakeBackend())   # no model → no levels
    dock._bind_to_session(other)
    assert not dock._settings_popup.is_effort_row_visible()   # *before* settling
    assert dock._settings_popup.current_effort() is None
    assert "high" not in dock._info_bar.text()


def test_closing_the_dock_cancels_its_background_tasks(dock, qtbot):
    """A continuation that resumes after teardown writes to deleted C++ objects
    (RuntimeError from Shiboken, surfacing as an unretrieved task exception)."""
    import asyncio

    # A future nothing ever resolves. `asyncio.sleep` cannot be used here:
    # qasync steps spawned tasks from the Qt loop without asyncio considering a
    # loop "running", so sleep's `get_running_loop()` raises and the task would
    # finish immediately — passing the precondition below for the wrong reason.
    # A bare `yield` is no good either: the Task reschedules it and it completes.
    pending = asyncio.get_event_loop().create_future()

    async def _slow():
        await pending

    task = dock._spawn(_slow())
    _settle(qtbot)
    assert not task.done()

    dock.close()
    _settle(qtbot)
    assert task.cancelled()


def test_a_failing_background_task_is_logged_not_left_unretrieved(
        dock, qtbot, monkeypatch):
    """Nothing awaits a spawned task, so an unconsumed exception would only ever
    appear as a bare "Task exception was never retrieved" at GC time."""
    from SciQLop.components.agents import chat_dock as mod

    seen = []
    monkeypatch.setattr(mod.log, "error", lambda *args: seen.append(args))

    async def _boom():
        raise RuntimeError("backend went away")

    task = dock._spawn(_boom())
    _settle(qtbot)
    assert task.done() and task not in dock._bg_tasks
    assert seen and "backend went away" in repr(seen[0])


def test_a_late_model_switch_for_an_abandoned_backend_is_dropped(dock, qtbot):
    stale = _FakeBackend()

    dock._spawn(dock._apply_model(stale, "smart"))
    _settle(qtbot)
    assert stale.model == "smart"              # the switch still reaches it
    assert not dock._settings_popup.is_effort_row_visible()   # but the UI is untouched


def test_a_restored_effort_is_applied_to_the_backend_not_just_shown(dock, qtbot):
    """Persisted effort lives in the dock's settings, which the backend cannot
    read — so the dock must push the restored level, or the strip advertises a
    level the backend is not running at."""
    from SciQLop.components.agents.settings import AgentChatSettings

    backend = dock._current_backend()
    backend.model = "smart"                    # offers ("low", "high")
    with AgentChatSettings() as cfg:
        cfg.effort = {**cfg.effort, _FAKE: "high"}

    dock._populate_effort(backend)
    _settle(qtbot)
    assert dock._settings_popup.current_effort() == "high"   # shown…
    assert backend.effort == "high"                          # …and actually applied


def test_a_backend_with_no_stored_effort_is_left_at_its_default(dock, qtbot):
    backend = dock._current_backend()
    backend.model = "smart"

    dock._populate_effort(backend)
    _settle(qtbot)
    assert dock._settings_popup.current_effort() is None
    assert backend.effort == "unset"           # never pushed


def test_a_backend_reporting_nothing_clears_the_strip(dock, qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot

    backend = dock._current_backend()
    backend.snapshot = UsageSnapshot(tokens=TokenCounts(input=10))
    dock._spawn(dock._usage_refresher.refresh())
    _settle(qtbot)
    assert dock._info_bar.text() != ""

    backend.snapshot = None
    dock._spawn(dock._usage_refresher.refresh())
    _settle(qtbot)
    assert dock._info_bar.text() == ""
    assert dock._info_bar.isHidden()


def test_usage_is_refreshed_again_once_the_backend_has_connected(dock, qtbot):
    """`list_slash_commands` is what first connects the SDK client, and a
    backend can only report context once connected. Refreshing only at bind
    races that connection and loses the pre-turn context every time."""
    from SciQLop.components.agents.backend import UsageSnapshot

    backend = dock._current_backend()
    backend.snapshot = None                      # nothing reportable yet

    async def _connect_then_report():
        backend.snapshot = UsageSnapshot(model="smart", context_tokens=34_000,
                                         context_max=500_000)
        return []

    backend.list_slash_commands = _connect_then_report
    dock._info_bar.set_snapshot(None)

    dock._spawn(dock._refresh_completions_then_usage())
    _settle(qtbot)

    assert dock._info_bar.text() == "smart · 7%"


class _AlphaBackend(_FakeBackend):
    """Sorts before FakeAgent, and reports no usage — like Albert in a real
    install, which is what `available_backends()`'s sort actually selects."""
    display_name = "AlphaAgent"
    usage_snapshot = None          # implements none of the usage protocol
    effort_values = None


def _with_two_backends(dock):
    from SciQLop.components.agents.registry import register_agent_backend
    register_agent_backend(_AlphaBackend)
    dock.refresh_backends()


def test_the_last_used_backend_is_restored_rather_than_the_alphabetical_first(
        dock, qtbot):
    """`available_backends()` is sorted, so binding to names[0] always lands on
    whichever backend sorts first — "Albert" in a real install — no matter which
    one the user actually chats with. That backend implements none of the usage
    protocol, so the strip stays blank and looks broken."""
    from SciQLop.components.agents.registry import unregister_agent_backend
    from SciQLop.components.agents.settings import AgentChatSettings

    try:
        with AgentChatSettings() as cfg:
            cfg.last_backend = _FAKE
        _with_two_backends(dock)
        assert dock._backend_combo.itemText(0) == "AlphaAgent"   # sorts first
        assert dock._current == _FAKE                            # remembered wins
        assert dock._backend_combo.currentText() == _FAKE
    finally:
        unregister_agent_backend("AlphaAgent")


def test_choosing_a_backend_records_it_for_next_time(dock, qtbot):
    from SciQLop.components.agents.registry import unregister_agent_backend
    from SciQLop.components.agents.settings import AgentChatSettings

    try:
        with AgentChatSettings() as cfg:
            cfg.last_backend = _FAKE
        _with_two_backends(dock)

        dock._backend_combo.setCurrentIndex(
            dock._backend_combo.findText("AlphaAgent"))
        _settle(qtbot)
        assert AgentChatSettings().last_backend == "AlphaAgent"
    finally:
        unregister_agent_backend("AlphaAgent")


def test_an_unknown_remembered_backend_falls_back_to_the_first(dock, qtbot):
    from SciQLop.components.agents.registry import unregister_agent_backend
    from SciQLop.components.agents.settings import AgentChatSettings

    try:
        with AgentChatSettings() as cfg:
            cfg.last_backend = "UninstalledAgent"
        # cold start: nothing is bound yet, which is when the fallback applies.
        # On a live refresh the active backend is kept instead, so that adding a
        # plugin cannot yank the backend out from under an open conversation.
        dock._current = None
        _with_two_backends(dock)
        assert dock._current == "AlphaAgent"
    finally:
        unregister_agent_backend("AlphaAgent")


def test_loading_an_existing_session_refreshes_the_strip(dock, qtbot):
    """`resume()` drops the client so the next turn reconnects on the resumed
    session — but nothing reconnected or re-read usage afterwards, so the strip
    kept whatever it had from before. Opening a session left it blank."""
    from SciQLop.components.agents.backend import UsageSnapshot

    backend = dock._current_backend()
    backend.supports_sessions = True
    resumed = []

    async def _resume(session_id):
        resumed.append(session_id)
        backend.snapshot = UsageSnapshot(model="resumed", context_tokens=10,
                                         context_max=100)

    backend.resume = _resume
    dock._info_bar.set_snapshot(None)

    dock._on_session_selected("sess-42")
    _settle(qtbot)

    assert resumed == ["sess-42"]
    assert dock._info_bar.text() == "resumed · 10%"


def test_a_failed_resume_still_leaves_the_strip_consistent(dock, qtbot):
    from SciQLop.components.agents.backend import UsageSnapshot

    backend = dock._current_backend()
    backend.supports_sessions = True
    backend.snapshot = UsageSnapshot(model="stale")
    dock._spawn(dock._usage_refresher.refresh())
    _settle(qtbot)
    assert dock._info_bar.text() == "stale"

    async def _boom(session_id):
        backend.snapshot = None
        raise RuntimeError("resume failed")

    backend.resume = _boom
    dock._on_session_selected("sess-99")
    _settle(qtbot)
    # the stale model must not linger as if it described the resumed session
    assert dock._info_bar.text() == ""


def test_loading_a_session_does_not_block_the_gui(dock, qtbot):
    """`load_session` may spawn a subprocess and block for seconds. The dock
    must return to the Qt event loop immediately and render the messages once
    the load finishes."""
    import time

    from SciQLop.components.agents.chat.view import ChatMessage

    backend = dock._current_backend()
    backend.supports_sessions = True
    loaded = []

    def _slow_load(session_id, image_tempdir):
        time.sleep(0.15)                       # blocks the worker thread, not Qt
        loaded.append(session_id)
        return [ChatMessage(role="assistant", blocks=[], done=True)]

    backend.load_session = _slow_load

    dock._on_session_selected("sess-block")
    # The handler must return instantly; the loading status is already visible.
    assert "Loading" in dock._status_label.text()
    assert dock._load_task is not None and not dock._load_task.done()

    qtbot.waitUntil(lambda: "Resumed" in dock._status_label.text(), timeout=3000)
    assert loaded == ["sess-block"]
    assert len(dock._sessions[dock._current].messages) == 1


def test_switching_session_supersedes_the_previous_load(dock, qtbot):
    """Clicking another session while the first is still loading must cancel
    the first load and show the second one."""
    import time

    from SciQLop.components.agents.chat.view import ChatMessage

    backend = dock._current_backend()
    backend.supports_sessions = True
    started, finished = [], []

    def _load(session_id, image_tempdir):
        started.append(session_id)
        if session_id == "first":
            time.sleep(0.5)                    # still loading when second lands
        finished.append(session_id)
        return [ChatMessage(role="assistant", blocks=[], done=True)]

    backend.load_session = _load

    dock._on_session_selected("first")
    _settle(qtbot)
    first_task = dock._load_task
    assert not first_task.done()

    dock._on_session_selected("second")
    qtbot.waitUntil(
        lambda: dock._status_label.text().startswith("Resumed"), timeout=3000)

    assert started == ["first", "second"]
    assert finished == ["second"]             # superseded load never completed
    assert first_task.cancelled()
    assert dock._sessions[dock._current].messages


def test_switching_session_again_supersedes_the_previous_load(dock, qtbot):
    """Clicking down a session list starts a resume per click. Left running,
    they race over one backend and whichever finishes last wins — which is not
    necessarily the session the user is now looking at."""
    import asyncio

    from SciQLop.components.agents.backend import UsageSnapshot

    backend = dock._current_backend()
    backend.supports_sessions = True
    started, finished = [], []
    # a future nothing resolves: `asyncio.sleep` needs a running loop, and
    # qasync steps these tasks without asyncio considering one to be running.
    never = asyncio.get_event_loop().create_future()

    async def _resume(session_id):
        started.append(session_id)
        if session_id == "first":
            await never                       # still resuming when the next click lands
        finished.append(session_id)
        backend.snapshot = UsageSnapshot(model=session_id)

    backend.resume = _resume

    dock._on_session_selected("first")
    _settle(qtbot)
    first_task = dock._resume_task
    assert not first_task.done()

    dock._on_session_selected("second")
    qtbot.waitUntil(lambda: dock._info_bar.text() == "second", timeout=3000)

    assert started == ["first", "second"]
    assert finished == ["second"]             # the superseded one never completed
    assert first_task.cancelled()


def test_alignment_prompt_warns_against_stale_api_assumptions():
    from SciQLop.components.agents import chat_dock as mod
    assert "verify the current API" in mod._AGENT_ALIGNMENT
    assert "sciqlop_api_reference" in mod._AGENT_ALIGNMENT


def test_version_reminder_is_prefixed_on_next_turn_after_resume(dock, qtbot):
    from SciQLop.components.agents.chat_dock import _AgentSession
    from SciQLop.components.agents.settings import AgentSessionMeta
    import SciQLop

    captured = []

    class _CapturingBackend:
        display_name = _FAKE
        model_choices = []
        supports_sessions = True
        snapshot = None

        def current_session_id(self):
            return "session-123"

        async def ask(self, prompt, image_paths=None):
            captured.append(prompt)
            if False:
                yield None

        async def usage_snapshot(self):
            return None

        def effort_values(self):
            return ()

        async def set_effort(self, effort):
            pass

        async def set_model(self, model):
            pass

        def set_write_mode(self, mode):
            pass

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

    session = _AgentSession(backend=_CapturingBackend())
    session.version_reminder = (
        "Note: SciQLop was updated from 0.11.0 to 0.12.0 since this session started. "
        "API capabilities may have changed; verify the current API with "
        "sciqlop_api_reference before assuming limitations.\n"
    )
    dock._sessions[dock._current] = session

    dock._spawn(dock._run_turn(session, "plot something", []))
    _settle(qtbot)

    assert len(captured) == 1
    assert captured[0].startswith("Note: SciQLop was updated from 0.11.0 to 0.12.0")
    assert "plot something" in captured[0]
    assert AgentSessionMeta().get_sciqlop_version(_FAKE, "session-123") == SciQLop.__version__
