from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog
from pathlib import Path


class JupyterLabView(QWebEngineView):
    def __init__(self, parent=None, url=None):
        super().__init__()
        self.setWindowTitle("SciQLop JupyterLab")
        QTimer.singleShot(100, lambda: self.setUrl(url))
        self.page().profile().downloadRequested.connect(self.download)

    def download(self, download_item: QWebEngineDownloadRequest):
        print("Downloading", download_item)
        path, _ = QFileDialog.getSaveFileName(self, "Save File",
                                              f"{download_item.downloadDirectory()}/{download_item.downloadFileName()}")
        path = Path(path).as_posix()
        if path:
            download_item.setDownloadDirectory(Path(path).parent.as_posix())
            download_item.setDownloadFileName(Path(path).name)
            download_item.accept()
