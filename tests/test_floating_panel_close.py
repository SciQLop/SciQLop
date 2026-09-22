"""Closing a floating plot panel must not crash (SciQLop 0.13.0 segfault on macOS).

Qt's QRhiWidget keeps a pointer to its old window's QRhi when it is moved out of that
window (WindowAboutToChangeInternal drops the cleanup callback but keeps d->rhi). Closing
a floating panel moved the plots out of the floating window, QtAds then destroyed that
window and its QRhi, and ~QRhiWidget later called removeCleanupCallback on the freed QRhi.
Standalone Qt reproducer: docs/qt-bugs/qrhiwidget_reparent_uaf.py.

glibc usually hides the bad read, so the child runs with MALLOC_PERTURB_ to poison freed
memory; macOS pointer authentication catches it without that.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

_CHILD = Path(__file__).with_name("_float_close_child.py")


@pytest.mark.parametrize("close_mode", ["tab", "window", "forced"])
def test_closing_a_floating_plot_panel_does_not_crash(close_mode):
    env = {**os.environ, "MALLOC_PERTURB_": "165"}
    result = subprocess.run([sys.executable, str(_CHILD), close_mode], env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, (
        f"child exited with {result.returncode}\n--- stdout ---\n{result.stdout[-2000:]}"
        f"\n--- stderr ---\n{result.stderr[-4000:]}")
    assert "closed floating panel without crashing" in result.stdout
