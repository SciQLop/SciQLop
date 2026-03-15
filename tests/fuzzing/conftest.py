import os

import pytest
from tests.fixtures import *  # noqa: F401,F403 — re-export main_window, qapp_cls, etc.


@pytest.fixture(scope="session", autouse=True)
def fuzzing_reports_dir():
    """Ensure test-reports directory exists for story dumps."""
    reports_dir = os.environ.get("SCIQLOP_TEST_REPORTS", "test-reports")
    os.makedirs(reports_dir, exist_ok=True)
