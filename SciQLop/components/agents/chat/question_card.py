"""Inline card that renders the agent's AskUserQuestion and collects answers.

The model's built-in AskUserQuestion tool sends a list of questions, each with
options; the SDK expects the answers mapped back as {question_text: label(s)}.
This widget renders single-select questions as exclusive radio groups and
multi-select ones as checkboxes, then emits the collected answers on submit.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class QuestionCard(QFrame):
    """Renders AskUserQuestion ``questions`` and emits ``answered(dict)`` on submit.

    The emitted dict maps each question's text to the chosen option label
    (single-select) or to a list of chosen labels (multi-select).
    """

    answered = Signal(dict)

    def __init__(self, questions: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("agentQuestionCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        # (question_text, multiSelect, [(label, button)])
        self._groups: List[tuple] = []

        for q in questions:
            self._add_question(layout, q)

        send = QPushButton("Send answers")
        send.setObjectName("agentQuestionSend")
        send.clicked.connect(self._on_send)
        layout.addWidget(send)

    def _add_question(self, layout: QVBoxLayout, q: Dict[str, Any]) -> None:
        header = q.get("header", "")
        if header:
            layout.addWidget(QLabel(f"<b>{header}</b>"))
        question_text = q.get("question", "")
        prompt = QLabel(question_text)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        multi = bool(q.get("multiSelect", False))
        group = None if multi else QButtonGroup(self)
        buttons: List[tuple] = []
        for i, opt in enumerate(q.get("options", []) or []):
            label = opt.get("label", "")
            btn = QCheckBox(label) if multi else QRadioButton(label)
            if group is not None:
                group.addButton(btn)
                if i == 0:
                    btn.setChecked(True)  # sensible default for single-select
            layout.addWidget(btn)
            self._add_description(layout, opt.get("description", ""))
            buttons.append((label, btn))
        self._groups.append((question_text, multi, buttons))

    def _add_description(self, layout: QVBoxLayout, description: str) -> None:
        """Descriptions get a label of their own: Qt buttons never wrap their
        text, so a long one is cropped at the dock's width instead."""
        if not description:
            return
        text = QLabel(description)
        text.setWordWrap(True)
        text.setIndent(self.fontMetrics().horizontalAdvance("MM"))
        text.setStyleSheet("color: gray;")
        layout.addWidget(text)

    def _on_send(self) -> None:
        answers: Dict[str, Any] = {}
        for question_text, multi, buttons in self._groups:
            if multi:
                answers[question_text] = [lbl for lbl, b in buttons if b.isChecked()]
            else:
                answers[question_text] = next(
                    (lbl for lbl, b in buttons if b.isChecked()), "")
        self.answered.emit(answers)
