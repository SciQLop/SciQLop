from __future__ import annotations

import os

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from jinja2 import Environment, FileSystemLoader

from SciQLop.components.theming.palette import SCIQLOP_PALETTE
from .backend import AppStoreBackend

_RESOURCES = os.path.join(os.path.dirname(__file__), "resources")


def _render_template() -> str:
    env = Environment(loader=FileSystemLoader(_RESOURCES))
    template = env.get_template("appstore.html.j2")
    return template.render(palette=SCIQLOP_PALETTE)


class AppStorePage(QWidget):
    """AppStore page rendered as HTML via QWebEngineView."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Store")

        self._backend = AppStoreBackend(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("backend", self._backend)

        self._view = QWebEngineView(self)
        self._view.page().setWebChannel(self._channel)
        self._view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        html = _render_template()
        self._view.setHtml(html, QUrl.fromLocalFile(os.path.join(_RESOURCES, "appstore.html")))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
