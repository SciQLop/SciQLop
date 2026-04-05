from __future__ import annotations

import os

from PySide6.QtWidgets import QWidget

from SciQLop.core.web_channel_page import WebChannelPage
from .backend import AppStoreBackend


class AppStorePage(WebChannelPage):
    """AppStore page rendered as HTML via QWebEngineView."""

    resources_dir = os.path.join(os.path.dirname(__file__), "resources")
    template_name = "appstore.html.j2"

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Plugin Store", parent)

    def _create_backend(self):
        return AppStoreBackend(self)
