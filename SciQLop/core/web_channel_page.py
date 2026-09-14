"""Reusable QWebEngineView + QWebChannel + Jinja2 base widget."""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from jinja2 import Environment, FileSystemLoader

class WebChannelPage(QWidget):
    """Base widget: renders a Jinja2 template in QWebEngineView with a QWebChannel backend.

    Subclasses provide:
      - resources_dir: path to the directory containing the template and assets
      - template_name: Jinja2 template filename
      - _create_backend(): factory returning a QObject exposed as "backend" to JS
    """

    resources_dir: str  # set by subclass
    template_name: str  # set by subclass

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self._backend = self._create_backend()
        self._channel = QWebChannel(self)
        self._channel.registerObject("backend", self._backend)

        # Test hook: SCIQLOP_TEST_NO_WEBENGINE=1 (set by tests/conftest.py)
        # skips the QWebEngineView so browser-free tests don't pay for
        # Chromium renderer processes. Backend and channel still exist, so
        # backend-logic tests keep working; view-touching code no-ops.
        self._view: QWebEngineView | None = None
        if os.environ.get("SCIQLOP_TEST_NO_WEBENGINE") == "1":
            page_widget: QWidget = QWidget(self)
        else:
            view = QWebEngineView(self)
            view.page().setWebChannel(self._channel)
            settings = view.settings()
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
            # The page is loaded with a file:// base URL (setHtml below), so its
            # origin is local; without this, remote plugin card/screenshot images
            # are blocked and every card falls back to the emoji placeholder.
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            page_widget = self._view = view

        self._load_html()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page_widget)

        from SciQLop.core.sciqlop_application import sciqlop_app
        sciqlop_app().theme_changed.connect(self._on_theme_changed)

    def _create_backend(self) -> QObject:
        raise NotImplementedError

    def _on_theme_changed(self, _palette_name: str) -> None:
        self._load_html()

    def _load_html(self):
        if self._view is None:
            return
        html = self._render_template()
        base_name = self.template_name.removesuffix(".j2")
        base_url = QUrl.fromLocalFile(os.path.join(self.resources_dir, base_name))
        self._view.setHtml(html, base_url)

    def _render_template(self) -> str:
        from SciQLop.components.theming.palette import SCIQLOP_PALETTE
        env = Environment(loader=FileSystemLoader(self.resources_dir))
        template = env.get_template(self.template_name)
        return template.render(palette=SCIQLOP_PALETTE)

    @property
    def backend(self):
        return self._backend
