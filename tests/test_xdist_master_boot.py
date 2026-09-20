"""Regression guard for the pytest-xdist master boot path.

pytest-xvfb deliberately skips starting Xvfb for the xdist *master* process
(it never runs a test itself, only dispatches to workers) -- see
`is_xdist_master` in pytest_xvfb.py. Before this test existed, tests/conftest.py's
`pytest_configure` built a real `SciQLopApp` unconditionally, with no display
available on the master, aborting the whole run (SIGABRT in
`QGuiApplicationPrivate::createPlatformIntegration`) before a single test ran.
"""
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_xdist_master_does_not_abort_on_boot():
    # A real terminal (or an outer pytest-xvfb instance) leaves $DISPLAY set,
    # which the child would inherit and silently mask the bug this guards
    # against: the master never needs a display, but nothing stopped it from
    # trying to build one. Drop it so this test exercises the actual
    # no-display case CI runs in.
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_signal_rate_limiter.py",
         "-n", "2", "-q", "-p", "no:cacheprovider"],
        cwd=_REPO_ROOT, capture_output=True, text=True, timeout=90, env=env,
    )
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-4000:]
