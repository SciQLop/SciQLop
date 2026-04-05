from __future__ import annotations

import os

from PySide6.QtWidgets import QWidget

from SciQLop.core.web_channel_page import WebChannelPage
from .backend import WelcomeBackend


class WebWelcomePage(WebChannelPage):
    """Welcome page rendered as HTML via QWebEngineView."""

    resources_dir = os.path.join(os.path.dirname(__file__), "resources")
    template_name = "welcome.html.j2"

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Welcome", parent)

    def _create_backend(self):
        return WelcomeBackend(self)
