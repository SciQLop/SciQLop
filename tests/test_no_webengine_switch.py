"""SCIQLOP_TEST_NO_WEBENGINE=1 must keep Chromium out of WebChannelPage.

Most GUI tests need the main window's dock manager, not a browser. Spawning
QWebEngineView renderer processes per test session wastes memory and is the
recurring SIGSEGV frame (libQt6WebEngineCore) in container runs.
"""

import os

import pytest


@pytest.fixture()
def no_webengine(monkeypatch):
    monkeypatch.setenv("SCIQLOP_TEST_NO_WEBENGINE", "1")


def test_welcome_page_creates_no_webengine_view(qapp, no_webengine):
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from SciQLop.components.welcome import WelcomePage

    page = WelcomePage()
    assert page.findChild(QWebEngineView) is None
    assert page.backend is not None
    page.deleteLater()


def test_appstore_page_creates_no_webengine_view(qapp, no_webengine):
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from SciQLop.components.appstore import AppStorePage

    page = AppStorePage()
    assert page.findChild(QWebEngineView) is None
    assert page.backend is not None
    page.deleteLater()


def test_conftest_disables_webengine_suite_wide():
    assert os.environ.get("SCIQLOP_TEST_NO_WEBENGINE") == "1"
