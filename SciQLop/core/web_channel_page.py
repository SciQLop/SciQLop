"""Reusable QWebEngineView + QWebChannel + Jinja2 base widget."""
from __future__ import annotations

import os
import time

from PySide6.QtCore import QObject, QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from jinja2 import Environment, FileSystemLoader

from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

_CRASH_WINDOW_S = 60.0
_MAX_RELOADS_PER_WINDOW = 3


def should_reload(status: QWebEnginePage.RenderProcessTerminationStatus,
                  earlier_crashes: list[float], now: float) -> bool:
    """A dead renderer leaves a blank page: reload it, unless it keeps dying."""
    if status == QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus:
        return False
    recent = sum(now - t < _CRASH_WINDOW_S for t in earlier_crashes)
    return recent < _MAX_RELOADS_PER_WINDOW


class WebChannelPage(QWidget):
    """Base widget: renders a Jinja2 template in QWebEngineView with a QWebChannel backend.

    Subclasses provide:
      - resources_dir: path to the directory containing the template and assets
      - template_name: Jinja2 template filename
      - _create_backend(): factory returning a QObject exposed as "backend" to JS
    """

    resources_dir: str  # set by subclass
    template_name: str  # set by subclass
    # The app store needs remote screenshots. A page that renders untrusted
    # text (agent output) must not: a markdown image would fetch any URL.
    allows_remote_content: bool = True

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(title)

        self._backend = self._create_backend()
        self._channel = QWebChannel(self)
        self._channel.registerObject("backend", self._backend)

        # SCIQLOP_NO_WEBENGINE=1 (`sciqlop --no-webengine`, `--batch`, the
        # tests) skips the QWebEngineView: no Chromium renderer processes,
        # which a container or a browser-free test does not want. Backend and
        # channel still exist, so backend logic keeps working; view-touching
        # code no-ops.
        self._view: QWebEngineView | None = None
        self._crash_times: list[float] = []
        if os.environ.get("SCIQLOP_NO_WEBENGINE") == "1":
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
                QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
                self.allows_remote_content)
            view.renderProcessTerminated.connect(self._on_render_process_terminated)
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

    def _on_render_process_terminated(self, status, exit_code: int) -> None:
        if status == QWebEnginePage.RenderProcessTerminationStatus.NormalTerminationStatus:
            return
        now = time.monotonic()
        if not should_reload(status, self._crash_times, now):
            log.error("%s: web renderer keeps crashing (%s, exit code %s); not reloading",
                      self.windowTitle(), status.name, exit_code)
            return
        self._crash_times.append(now)
        log.warning("%s: web renderer died (%s, exit code %s); reloading",
                    self.windowTitle(), status.name, exit_code)
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
