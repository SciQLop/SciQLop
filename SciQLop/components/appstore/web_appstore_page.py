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
        self._pending_js: list[str] = []
        super().__init__("Plugin Store", parent)
        if self._view is not None:
            self._view.loadFinished.connect(self._flush_pending_js)

    def _create_backend(self):
        return AppStoreBackend(self)

    def show_package(self, name: str) -> None:
        """Open the store with a package's detail page selected.

        Safe to call before the page finished loading: the request is
        re-issued from loadFinished, and the JS side holds its own pending
        selection until the package list arrives.
        """
        if name:
            self._run_js(f"showPackageDetailsByName({json.dumps(name)})")

    def show_page(self, page: str) -> None:
        """Switch the store to one of its pages: explore, installed or updates."""
        self._run_js(f"showPage({json.dumps(page)})")

    def _run_js(self, js: str) -> None:
        self._pending_js.append(js)
        if self._view is not None:
            self._view.page().runJavaScript(js)

    def _flush_pending_js(self, ok: bool) -> None:
        pending, self._pending_js = self._pending_js, []
        if ok and self._view is not None:
            for js in pending:
                self._view.page().runJavaScript(js)
