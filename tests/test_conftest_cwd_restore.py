"""conftest.py's _restore_cwd autouse fixture (2026-09-06 final review):
Workspace.activate() deliberately os.chdir()s into the workspace directory
whenever a real SciQLopMainWindow is constructed. Several test files do
that directly, and the session-scoped `main_window` fixture does too --- so
this isn't specific to any one test file, and the fix belongs centrally in
conftest.py rather than as a per-file fixture that only knows about its own
tests.

Order matters here: test_a must run before test_b for this to prove
anything. Both are in the same module, so pytest's default (file, then
definition order) keeps them adjacent regardless of test-selection order
elsewhere in a full run.
"""
import os

_BASELINE = os.getcwd()


def test_a_changes_cwd_without_restoring_it_itself():
    os.chdir(os.path.dirname(_BASELINE) or "/")
    assert os.getcwd() != _BASELINE


def test_b_sees_the_restored_baseline_cwd():
    assert os.getcwd() == _BASELINE
