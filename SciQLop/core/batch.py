"""Batch mode: `sciqlop --batch script.py [args...]` runs a script inside a
windowless SciQLop and exits with the script's exit code.

The launcher passes the request to the app process in an environment variable.
Stdlib only: the launcher imports this from a thin install.
"""
from __future__ import annotations

import json
import os
import runpy
import sys
import traceback
from dataclasses import asdict, dataclass, field
from typing import Mapping, Optional

BATCH_ENV = "SCIQLOP_BATCH"


@dataclass(frozen=True)
class BatchRequest:
    script: str
    args: list[str] = field(default_factory=list)
    cwd: str = "."

    @classmethod
    def from_command_line(cls, batch_argv: list[str]) -> "BatchRequest":
        script, *args = batch_argv
        return cls(script=os.path.abspath(script), args=args, cwd=os.getcwd())

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Optional["BatchRequest"]:
        raw = env.get(BATCH_ENV)
        return cls(**json.loads(raw)) if raw else None

    def to_env(self) -> str:
        return json.dumps(asdict(self))


def run_batch_script(request: BatchRequest) -> int:
    """Run the script as ``__main__`` from the caller's directory.

    Workspace activation chdirs into the workspace; going back makes relative
    output paths land where the user ran the command."""
    os.chdir(request.cwd)
    sys.argv = [request.script, *request.args]
    try:
        runpy.run_path(request.script, run_name="__main__")
    except SystemExit as e:
        return _exit_code(e.code)
    except BaseException:
        traceback.print_exc()
        return 1
    return 0


def _exit_code(code) -> int:
    if code is None or isinstance(code, int):
        return code or 0
    print(code, file=sys.stderr)
    return 1
