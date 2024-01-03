from PySide6.QtCore import QProcess, QProcessEnvironment, QObject, Signal
from typing import List
from .jupyter_client import SciQLopJupyterClient, ClientType
from .qt_console import QtConsoleClient
from .jupyterlab import JupyterLabClient


class ClientsManager(QObject):
    """Internal ipykernel manager."""
    jupyterlab_started = Signal(str)

    def __init__(self, connection_file, parent=None):
        QObject.__init__(self, parent)
        self._connection_file = connection_file
        self._jupyter_processes: List[SciQLopJupyterClient] = []

    def new_qt_console(self):
        """start a new qtconsole connected to our kernel"""
        self._jupyter_processes.append(QtConsoleClient(connection_file=self._connection_file))

    def start_jupyterlab(self):
        """start a new jupyterlab connected to our kernel"""
        self._jupyter_processes.append(JupyterLabClient(connection_file=self._connection_file))
        self.jupyterlab_started.emit(self._jupyter_processes[-1].url)

    def cleanup(self):
        """Clean up the consoles."""
        for c in self._jupyter_processes:
            if c.state() is QProcess.ProcessState.Running:
                c.kill()
                c.waitForFinished()
