"""Run a reproducer in a child pytest, so a SIGSEGV is a return code and not the end of the test session."""
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def run_inner_pytest(test_file) -> subprocess.CompletedProcess:
    """`-p tests.conftest`: a file outside tests/ does not load it, and the child then inherits the parent's
    data directories. Sharing the catalog database made the child fail with "database is locked"."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "--no-xvfb", "-x", "-q", "-s", "--rootdir", REPO_ROOT,
         "-p", "no:cacheprovider", "-p", "tests.conftest"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=240)


def _output_of(result) -> str:
    return (f"returncode={result.returncode}\n--- stdout ---\n{result.stdout[-4000:]}\n"
            f"--- stderr ---\n{result.stderr[-4000:]}")


def assert_passed_without_segfault(result, crash: str) -> None:
    """A SIGSEGV is the reported crash. Other noise at interpreter shutdown, after the test body, is tolerated."""
    assert result.returncode not in (-11, 139), f"{crash} SIGSEGV reproduced: {_output_of(result)}"
    assert "passed" in result.stdout, f"inner test did not report a pass: {_output_of(result)}"
