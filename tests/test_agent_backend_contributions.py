"""Agent backends are contributions to `sciqlop.agent_backends`; the chat dock follows them live."""
import pytest

from SciQLop.components.agents import (
    AGENT_BACKENDS, AgentBackendEntry, available_backends, create_backend,
    register_agent_backend, unregister_agent_backend)
from SciQLop.core.extensions import owned_by

from .fixtures import *  # noqa: F401,F403
from .test_agent_chat_dock_wiring import _FAKE, _FakeBackend, _settle, dock  # noqa: F401 — fixture

_OWNER = "be_demo"


class _Demo(_FakeBackend):
    display_name = "Fake"


class _Other(_FakeBackend):
    display_name = "AAA-Other"


@pytest.fixture
def clean_backends():
    yield
    AGENT_BACKENDS.remove_owner(_OWNER)
    for name in ("Fake", "Named", "AAA-Other"):
        unregister_agent_backend(name)


def test_register_is_a_contribution(clean_backends):
    with owned_by(_OWNER):
        register_agent_backend(_Demo)
    assert "Fake" in AGENT_BACKENDS
    assert AGENT_BACKENDS.owner_of("Fake") == _OWNER
    assert "Fake" in available_backends()

    AGENT_BACKENDS.remove_owner(_OWNER)
    assert "Fake" not in available_backends()
    with pytest.raises(KeyError):
        create_backend("Fake", None)


def test_legacy_two_arg_form_and_unregister(clean_backends):
    register_agent_backend("Named", _Demo)
    assert AGENT_BACKENDS.get("Named").factory is _Demo
    unregister_agent_backend("Named")
    assert "Named" not in available_backends()
    unregister_agent_backend("Named")


def test_reregistering_replaces(clean_backends):
    register_agent_backend("Named", _Demo)
    register_agent_backend("Named", _Other)
    assert isinstance(create_backend("Named", None), _Other)


def test_missing_display_name_raises_type_error():
    with pytest.raises(TypeError):
        register_agent_backend(lambda ctx: None)


def test_an_empty_name_is_refused():
    with pytest.raises(ValueError):
        AgentBackendEntry("", _Demo)


def test_taking_over_another_owners_name_is_logged(clean_backends, monkeypatch):
    from SciQLop.components.agents import registry
    warnings = []
    monkeypatch.setattr(registry.log, "warning", lambda msg, *a: warnings.append(msg % a if a else msg))
    register_agent_backend(_Demo)
    with owned_by(_OWNER):
        register_agent_backend(_Demo)
    assert AGENT_BACKENDS.owner_of("Fake") == _OWNER
    assert len(warnings) == 1 and "user" in warnings[0] and _OWNER in warnings[0]


def _combo_items(widget):
    combo = widget._backend_combo
    return [combo.itemText(i) for i in range(combo.count())]


def test_the_dock_lists_a_live_installed_backend_without_rebinding(dock, qtbot, monkeypatch, clean_backends):
    session = dock._sessions[_FAKE]
    binds = []
    monkeypatch.setattr(dock, "_bind_to_session", binds.append)

    with owned_by(_OWNER):
        register_agent_backend(_Other)
    _settle(qtbot)

    assert "AAA-Other" in _combo_items(dock)
    assert dock._current == _FAKE
    assert dock._backend_combo.currentText() == _FAKE
    assert dock._sessions[_FAKE] is session
    assert binds == []


def test_withdrawing_the_current_backend(dock, qtbot, clean_backends):
    with owned_by(_OWNER):
        register_agent_backend(_Other)
    dock._select_backend("AAA-Other")
    _settle(qtbot)
    assert dock._current == "AAA-Other"

    AGENT_BACKENDS.remove_owner(_OWNER)
    _settle(qtbot)
    assert "AAA-Other" not in _combo_items(dock)
    assert dock._current == _FAKE
    assert dock._backend_combo.currentText() == _FAKE
    assert dock._send_btn.isEnabled()

    old_backend = dock._current_backend()
    unregister_agent_backend(_FAKE)
    _settle(qtbot)
    assert _combo_items(dock) == []
    assert dock._current is None
    assert dock._sessions == {}
    assert not dock._send_btn.isEnabled()

    register_agent_backend(_FakeBackend)
    _settle(qtbot)
    assert dock._current == _FAKE
    assert dock._current_backend() is not old_backend
    assert dock._send_btn.isEnabled()


def test_a_replaced_backend_takes_effect_for_new_sessions(dock, qtbot, clean_backends):
    class _Replacement(_FakeBackend):
        display_name = _FAKE

    with owned_by(_OWNER):
        register_agent_backend(_Other)
    dock._select_backend("AAA-Other")
    _settle(qtbot)
    live = dock._current_backend()
    assert "AAA-Other" in dock._sessions and _FAKE in dock._sessions

    class _OtherReplacement(_FakeBackend):
        display_name = "AAA-Other"

    with owned_by(_OWNER):
        register_agent_backend(_OtherReplacement)
    register_agent_backend(_Replacement)
    _settle(qtbot)
    assert dock._current_backend() is live
    assert _FAKE not in dock._sessions

    dock._select_backend(_FAKE)
    _settle(qtbot)
    assert isinstance(dock._current_backend(), _Replacement)
    register_agent_backend(_FakeBackend)  # restore the fixture's backend for its teardown


def test_a_destroyed_dock_ignores_backend_signals(qapp, qtbot, main_window, sciqlop_resources, clean_backends):
    import asyncio
    import shiboken6
    from SciQLop.components.agents import ensure_agent_dock
    from SciQLop.core.sciqlop_application import sciqlop_event_loop
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    asyncio.set_event_loop(sciqlop_event_loop())
    previous = qapp.main_window
    second = SciQLopMainWindow()
    try:
        orphan = ensure_agent_dock(second)
    finally:
        destroy_main_window(second)  # noqa: F405
        qapp.main_window = previous
    assert not shiboken6.isValid(orphan)
    orphan._follow_backends(None)

    with owned_by(_OWNER):
        register_agent_backend(_Other)
    AGENT_BACKENDS.remove_owner(_OWNER)
