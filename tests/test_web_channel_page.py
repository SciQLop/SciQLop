"""Local-origin web pages must be allowed to load remote images.

The appstore and welcome pages are rendered with ``setHtml(html, base_url)``
where ``base_url`` is a ``file://`` URL, so their document origin is local.
Plugin card thumbnails and screenshots are remote ``https://`` URLs. QtWebEngine
blocks a local-origin document from loading remote URLs unless
``LocalContentCanAccessRemoteUrls`` is enabled — without it every card falls
back to the emoji placeholder and the screenshot carousel stays empty.
"""
import gc
import os
import weakref

import pytest

from PySide6.QtWebEngineCore import QWebEngineSettings
from SciQLop.components.appstore.web_appstore_page import AppStorePage


@pytest.mark.skipif(
    os.environ.get("SCIQLOP_TEST_NO_WEBENGINE") == "1",
    reason="needs a real QWebEngineView; tests/conftest.py disables it by default "
           "because Chromium segfaults under the headless Xvfb without CI's flags")
def test_local_page_can_load_remote_images(qapp):
    page = AppStorePage()
    settings = page._view.settings()
    assert settings.testAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls), \
        "remote plugin images won't load from the file:// origin without this"
    page.deleteLater()
    qapp.processEvents()


def test_page_is_collectible_after_delete(qapp, qtbot):
    """A WebChannelPage must not be kept alive forever by its theme_changed
    connection -- every constructed page (and its QWebEngineView's Chromium
    renderer process) otherwise survives for the whole process lifetime,
    since sciqlop_app() is a singleton that outlives any individual page."""
    page = AppStorePage()
    ref = weakref.ref(page)
    page.deleteLater()
    qtbot.wait(10)
    del page
    gc.collect()
    assert ref() is None
