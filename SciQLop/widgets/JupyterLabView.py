from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QTimer


class JupyterLabView(QWebEngineView):
    def __init__(self, parent=None, url=None):
        super().__init__()
        self.setWindowTitle("SciQLop JupyterLab")
        QTimer.singleShot(2000, lambda : self.setUrl(url))
