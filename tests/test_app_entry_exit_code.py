"""``python -m SciQLop.app`` must propagate the launcher's exit code.

Restart (64), switch-workspace (65) and failure (1) all need to reach the OS
unchanged, since the native launcher / AppRun fallback / macOS wrapper /
Windows launcher.c all key their behaviour off this process's exit code. A
real subprocess round-trip is required because the bug is specifically about
what the OS sees when the module is run as ``__main__``.
"""

import subprocess
import sys

import pytest

_CODE = (
    "import runpy, SciQLop.sciqlop_launcher as l; "
    "l.main = lambda argv=None: {value}; "
    "runpy.run_module('SciQLop.app', run_name='__main__')"
)


@pytest.mark.parametrize("value", [0, 1, 64, 65])
def test_app_entry_propagates_launcher_exit_code(value):
    result = subprocess.run([sys.executable, "-c", _CODE.format(value=value)])
    assert result.returncode == value
