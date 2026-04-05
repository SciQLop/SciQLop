import os

import pytest
from tests.fixtures import *  # noqa: F401,F403 — re-export main_window, qapp_cls, etc.
from tests.fuzzing.actions import StoryRunner


@pytest.fixture(scope="session", autouse=True)
def fuzzing_reports_dir():
    """Ensure test-reports directory exists for story dumps."""
    reports_dir = os.environ.get("SCIQLOP_TEST_REPORTS", "test-reports")
    os.makedirs(reports_dir, exist_ok=True)


@pytest.fixture
def story_runner(main_window):
    """A StoryRunner wired to the live main_window, with automatic cleanup."""
    runner = StoryRunner(main_window)
    yield runner
    runner.cleanup()
