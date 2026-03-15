import os
import sys

# Ensure tests/ is importable so we can reuse fixtures and conftest hooks.
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Pull in pytest_configure (env vars, Xvfb, Qt attrs) and shared fixtures.
pytest_plugins = ["tests.conftest", "tests.fixtures"]

import pytest  # noqa: E402
from tests.fuzzing.actions import StoryRunner  # noqa: E402


@pytest.fixture
def screenshot_runner(main_window):
    runner = StoryRunner(main_window)
    yield runner
    runner.cleanup()
