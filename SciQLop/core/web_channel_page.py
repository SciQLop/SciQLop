"""Reusable QWebEngineView + QWebChannel + Jinja2 base widget."""
from __future__ import annotations

import os

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from jinja2 import Environment, FileSystemLoader

from SciQLop.components.theming.palette import SCIQLOP_PALETTE


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

        self._view = QWebEngineView(self)
        self._view.page().setWebChannel(self._channel)
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        html = self._render_template()
        # Strip .j2 suffix so the base URL matches the original non-template filename
        base_name = self.template_name.removesuffix(".j2")
        base_url = QUrl.fromLocalFile(os.path.join(self.resources_dir, base_name))
        self._view.setHtml(html, base_url)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

    def _create_backend(self) -> QObject:
        raise NotImplementedError

    def _render_template(self) -> str:
        env = Environment(loader=FileSystemLoader(self.resources_dir))
        template = env.get_template(self.template_name)
        return template.render(palette=SCIQLOP_PALETTE)

    @property
    def backend(self):
        return self._backend
