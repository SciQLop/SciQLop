from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import indent
from typing import Any


@dataclass
class Step:
    action_name: str
    args: dict[str, str]
    narrate_template: str
    result: Any = None
    error: Exception | None = None

    @property
    def narrative(self) -> str:
        fmt_kwargs = {**self.args}
        if self.result is not None:
            fmt_kwargs["result"] = self.result
        return self.narrate_template.format(**fmt_kwargs)

    def as_code(self) -> str:
        args_str = ", ".join(f"{k}={v!r}" for k, v in self.args.items())
        return f"actions.{self.action_name}({args_str})"


class Story:
    def __init__(self):
        self.steps: list[Step] = []

    def record(self, step: Step):
        self.steps.append(step)

    def narrative(self) -> str:
        return "\n".join(
            f"{i + 1}. {step.narrative}" for i, step in enumerate(self.steps)
        )

    def reproducer(self) -> str:
        lines = [step.as_code() for step in self.steps]
        body = indent("\n".join(lines), "    ") if lines else "    pass"
        return f"def test_reproducer(main_window, qtbot):\n{body}"
