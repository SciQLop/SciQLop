"""The next start after a crash offers to investigate and report it."""
import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


@pytest.fixture
def parent(qtbot):
    from PySide6.QtWidgets import QWidget
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def crashed(tmp_path, monkeypatch):
    from SciQLop.core import session_log
    from SciQLop.components.crash_report import backend

    monkeypatch.setattr(session_log, "launcher_data_dir", lambda: tmp_path)
    log = tmp_path / "session.log"
    log.write_text("Fatal Python error: Segmentation fault\n")
    session_log.write_crash_marker(session_log.crash_marker(-11, 42, log), directory=tmp_path)
    yield log
    backend.set_pending(None)


def _buttons(box):
    return [b.text() for b in box.buttons()]


def test_nothing_is_offered_after_a_clean_exit(parent, tmp_path, monkeypatch):
    from SciQLop.core import session_log
    from SciQLop.components.crash_report import offer

    monkeypatch.setattr(session_log, "launcher_data_dir", lambda: tmp_path)
    assert offer.offer_crash_report(parent) is None


def test_the_offer_is_shown_once_and_keeps_the_crash_for_the_agent(parent, crashed, monkeypatch):
    from SciQLop.components.crash_report import backend, offer

    monkeypatch.setattr(offer, "available_backends", lambda: ["FakeAgent"])
    box = offer.offer_crash_report(parent)
    assert box is not None and box.isVisible()
    assert "Segmentation fault" in backend.pending_crash_context()
    assert offer.offer_crash_report(parent) is None


def test_the_offer_snapshots_the_tool_calls_before_any_new_one_overwrites_them(
        parent, crashed, monkeypatch, tmp_path):
    """The journal is rewritten before every tool call, including the agent's
    own sciqlop_read_crash_report: read it when the offer is shown."""
    import json
    from SciQLop.components.crash_report import backend, offer

    journal = tmp_path / "journal.json"
    journal.write_text(json.dumps([{"name": "sciqlop_exec_python", "started": "t", "finished": None}]))
    monkeypatch.setattr(backend, "tool_journal_path", lambda: journal)
    monkeypatch.setattr(offer, "available_backends", lambda: [])
    offer.offer_crash_report(parent)
    journal.write_text("[]")
    assert "sciqlop_exec_python" in backend.pending_crash_context()


def test_without_an_agent_only_the_log_is_offered(parent, crashed, monkeypatch):
    from SciQLop.components.crash_report import offer

    monkeypatch.setattr(offer, "available_backends", lambda: [])
    box = offer.offer_crash_report(parent)
    assert "Investigate and report" not in _buttons(box)
    assert "Open log" in _buttons(box)


def test_investigate_starts_an_agent_conversation(parent, crashed, monkeypatch):
    from SciQLop.components.crash_report import offer

    started = []
    monkeypatch.setattr(offer, "available_backends", lambda: ["FakeAgent"])
    monkeypatch.setattr(offer, "draft_agent_conversation",
                        lambda window, prompt, backend=None: started.append((window, prompt)) or True)
    box = offer.offer_crash_report(parent)
    investigate = next(b for b in box.buttons() if b.text() == "Investigate and report")
    investigate.click()
    assert len(started) == 1
    window, prompt = started[0]
    assert window is parent
    assert "sciqlop_read_crash_report" in prompt
    assert "sciqlop_open_bug_report" in prompt


def _investigate_button(box):
    return next(b for b in box.buttons() if b.text() == "Investigate and report")


def test_with_several_agents_the_user_picks_which_one_investigates(parent, crashed, monkeypatch):
    from SciQLop.components.crash_report import offer

    started = []
    monkeypatch.setattr(offer, "available_backends", lambda: ["Claude", "OpenCode"])
    monkeypatch.setattr(offer, "current_agent_backend", lambda window: "OpenCode")
    monkeypatch.setattr(offer, "draft_agent_conversation",
                        lambda window, prompt, backend=None: started.append(backend) or True)
    box = offer.offer_crash_report(parent)
    menu = _investigate_button(box).menu()
    assert [a.text() for a in menu.actions()] == ["OpenCode", "Claude"]
    next(a for a in menu.actions() if a.text() == "Claude").trigger()
    assert started == ["Claude"]
    assert not box.isVisible()


def test_with_one_agent_there_is_nothing_to_pick(parent, crashed, monkeypatch):
    from SciQLop.components.crash_report import offer

    monkeypatch.setattr(offer, "available_backends", lambda: ["Claude"])
    box = offer.offer_crash_report(parent)
    assert _investigate_button(box).menu() is None


def test_the_offer_says_the_log_goes_to_the_model_provider(parent, crashed, monkeypatch):
    from SciQLop.components.crash_report import offer

    monkeypatch.setattr(offer, "available_backends", lambda: ["FakeAgent"])
    box = offer.offer_crash_report(parent)
    assert "model provider" in box.informativeText()
