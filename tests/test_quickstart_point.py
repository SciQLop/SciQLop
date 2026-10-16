"""Quickstart shortcuts are contributions to sciqlop.quickstart (Tier 3 spec §3.1)."""
import pytest

from .fixtures import *  # noqa: F401,F403 — main_window
from SciQLop.core.extensions import DuplicateContribution, owned_by
from SciQLop.core.quickstart import QUICKSTART


@pytest.fixture
def demo(qapp):
    yield
    QUICKSTART.remove_owner("qs_demo")


def _add(qapp, name="QS demo", callback=lambda: None):
    with owned_by("qs_demo"):
        qapp.add_quickstart_shortcut(name, "A demo", None, callback)


def test_a_shortcut_is_owned_by_the_current_plugin(qapp, demo):
    _add(qapp)
    assert QUICKSTART.owner_of("QS demo") == "qs_demo"
    assert "QS demo" in qapp.quickstart_shortcuts
    assert qapp.quickstart_shortcut("QS demo")["description"] == "A demo"


def test_quickstart_shortcut_stays_a_dict_with_its_callback(qapp, demo):
    calls = []
    _add(qapp, callback=lambda: calls.append(1))
    qapp.quickstart_shortcut("QS demo")["callback"]()
    assert calls == [1]
    assert qapp.quickstart_shortcut("No such shortcut") is None


def test_added_keeps_its_name_payload(qapp, demo, qtbot):
    with qtbot.waitSignal(qapp.quickstart_shortcuts_added) as blocker:
        _add(qapp)
    assert blocker.args == ["QS demo"]


def test_withdrawing_the_plugin_removes_its_shortcut_and_says_so(qapp, demo, qtbot):
    _add(qapp)
    with qtbot.waitSignal(qapp.quickstart_shortcuts_removed) as blocker:
        QUICKSTART.remove_owner("qs_demo")
    assert blocker.args == ["QS demo"]
    assert "QS demo" not in qapp.quickstart_shortcuts


def test_the_welcome_page_refreshes_when_a_shortcut_goes(qapp, demo, qtbot):
    from SciQLop.components.welcome.backend import WelcomeBackend
    backend = WelcomeBackend()
    try:
        _add(qapp)
        with qtbot.waitSignal(backend.quickstart_changed):
            QUICKSTART.remove_owner("qs_demo")
    finally:
        backend.deleteLater()


def test_the_main_window_shortcuts_belong_to_the_core(main_window):
    from SciQLop.core.name_follower import CORE_OWNER
    assert QUICKSTART.owner_of("New plot panel") == CORE_OWNER


def test_a_plugin_cannot_take_a_core_shortcut_name(qapp, main_window):
    with owned_by("qs_demo"), pytest.raises(DuplicateContribution):
        qapp.add_quickstart_shortcut("New plot panel", "Mine", None, lambda: None)


def test_a_shortcut_added_from_a_worker_thread_keeps_its_owner(qapp, demo, qtbot, monkeypatch):
    from .helpers import call_from_worker_thread
    call_from_worker_thread(qtbot, monkeypatch, lambda: _add(qapp))
    assert QUICKSTART.owner_of("QS demo") == "qs_demo"
