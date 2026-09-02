"""Importing sciqlop_app must leave the Qt platform choice to Qt (and to the
user's own QT_QPA_PLATFORM), never force one."""
import os
import subprocess
import sys


def _qpa_after_import(env_value: str | None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    if env_value is not None:
        env["QT_QPA_PLATFORM"] = env_value
    code = "import os, SciQLop.sciqlop_app; print(repr(os.environ.get('QT_QPA_PLATFORM')))"
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True)
    return out.stdout.strip().splitlines()[-1]


def test_import_does_not_force_a_platform():
    assert _qpa_after_import(None) == "None"


def test_import_keeps_the_user_platform():
    assert _qpa_after_import("wayland") == "'wayland'"
