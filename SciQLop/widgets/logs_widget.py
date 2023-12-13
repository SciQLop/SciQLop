from typing import List

import PySide6QtAds as QtAds
from PySide6.QtCore import Signal, QMimeData, Qt, QObject, QThread, QSize, QStringListModel
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QListView, QWidget, QVBoxLayout
from datetime import datetime
from ..backend.sciqlop_logging import _stdout
import sys


class LogsWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Logs")
        self._model = QStringListModel()
        self._list_view = QListView(self)
        _stdout.new_line.connect(self._new_line)

        self._list_view.setModel(self._model)
        self._list_view.setEditTriggers(QListView.NoEditTriggers)
        self._list_view.setUniformItemSizes(True)
        self._list_view.setAlternatingRowColors(True)
        self._list_view.setResizeMode(QListView.Adjust)
        self._list_view.setFlow(QListView.TopToBottom)
        self._list_view.setMovement(QListView.Static)
        self._list_view.setSpacing(0)
        self._list_view.setFrameShape(QListView.NoFrame)
        self._list_view.setFrameShadow(QListView.Plain)
        self._list_view.setLineWidth(0)
        self._list_view.setMidLineWidth(0)
        self._list_view.setBatchSize(100)
        self._list_view.setUniformItemSizes(True)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self._list_view)

    def _new_line(self, msg):
        self._model.insertRow(0)
        self._model.setData(self._model.index(0), msg)
        self._list_view.scrollToTop()
