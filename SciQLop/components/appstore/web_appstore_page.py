from __future__ import annotations

import json
import os

from PySide6.QtWidgets import QWidget

from SciQLop.core.web_channel_page import WebChannelPage
from .backend import AppStoreBackend


class AppStorePage(WebChannelPage):
    """AppStore page rendered as HTML via QWebEngineView."""

    resources_dir = os.path.join(os.path.dirname(__file__), "resources")
    template_name = "appstore.html.j2"

    def __init__(self, parent: QWidget | None = None):
        self._pending_package: str | None = None
        super().__init__("Plugin Store", parent)
        self._view.loadFinished.connect(self._flush_pending_package)

    def _create_backend(self):
        return AppStoreBackend(self)

    def show_package(self, name: str) -> None:
        """Open the store with a package's detail page selected.

        Safe to call before the page finished loading: the request is
        re-issued from loadFinished, and the JS side holds its own pending
        selection until the package list arrives.
        """
        if not name:
            return
        self._pending_package = name
        self._view.page().runJavaScript(
            f"showPackageDetailsByName({json.dumps(name)})")

    def _flush_pending_package(self, ok: bool) -> None:
        name, self._pending_package = self._pending_package, None
        if ok and name:
            self._view.page().runJavaScript(
                f"showPackageDetailsByName({json.dumps(name)})")
