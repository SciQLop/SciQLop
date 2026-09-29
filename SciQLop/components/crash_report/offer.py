"""Offer, once, to investigate and report the previous session's crash."""
from __future__ import annotations

from pathlib import Path

from SciQLop.components.agents.chat_dock import current_agent_backend, draft_agent_conversation
from SciQLop.components.agents.registry import available_backends
from SciQLop.core.session_log import take_crash_marker

from . import backend

_PROMPT = Path(__file__).parent / "resources" / "investigate_crash.md"


def investigation_prompt() -> str:
    return _PROMPT.read_text(encoding="utf-8")


def offer_crash_report(main_window):
    """Returns the (non-modal) offer box, or None when the last session did
    not crash. The marker is consumed here, so the offer shows once."""
    marker = take_crash_marker()
    if marker is None:
        return None
    backend.set_pending(marker)
    return _show_offer(main_window, marker)


def _show_offer(main_window, marker: dict):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox

    box = QMessageBox(QMessageBox.Icon.Warning, "SciQLop closed unexpectedly",
                      "SciQLop closed unexpectedly last time.", parent=main_window)
    investigate = None
    agents = _agents_current_first(main_window)
    if agents:
        box.setInformativeText(
            "An agent can investigate the crash and draft a bug report for you to "
            "review. The request is prepared in the agent panel: pick the model, then "
            "send it. The agent will read the end of the session log, which goes to "
            "your model provider.")
        investigate = box.addButton("Investigate and report", QMessageBox.ButtonRole.AcceptRole)
        if len(agents) > 1:
            investigate.setMenu(_agent_menu(box, agents, main_window))
    open_log = box.addButton("Open log", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Dismiss", QMessageBox.ButtonRole.RejectRole)

    def _on_clicked(button) -> None:
        if investigate is not None and button is investigate:
            draft_agent_conversation(main_window, investigation_prompt())
        elif button is open_log:
            QDesktopServices.openUrl(QUrl.fromLocalFile(marker["log"]))

    box.buttonClicked.connect(_on_clicked)
    box.setModal(False)
    box.show()
    return box


def _agents_current_first(main_window) -> list:
    agents = list(available_backends())
    current = current_agent_backend(main_window)
    return sorted(agents, key=lambda name: name != current)


def _agent_menu(box, agents: list, main_window):
    """A button with a menu opens the menu instead of clicking, so the box
    stays up until an agent is picked."""
    from PySide6.QtWidgets import QMenu

    menu = QMenu(box)
    for name in agents:
        action = menu.addAction(name)
        action.triggered.connect(lambda _checked=False, name=name: _investigate_with(box, main_window, name))
    return menu


def _investigate_with(box, main_window, agent: str) -> None:
    box.close()
    draft_agent_conversation(main_window, investigation_prompt(), agent)
