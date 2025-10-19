from PySide6.QtCore import QProcess, QProcessEnvironment, QObject, Signal
from typing import List
from .jupyter_client_process import SciQLopJupyterClient, ClientType
from .qt_console import QtConsoleClient
from .jupyterlab_launcher import JupyterLabClient


class ClientsManager(QObject):
    """Internal ipykernel manager."""
    jupyterlab_started = Signal(str)

    def __init__(self, connection_file, parent=None):
        super().__init__(parent)
        self._connection_file = connection_file
        self._jupyter_processes: List[SciQLopJupyterClient] = []
        self._running_jupyterlab = False

    def new_qt_console(self, cwd=None):
        """start a new qtconsole connected to our kernel"""
        self._jupyter_processes.append(QtConsoleClient(connection_file=self._connection_file, cwd=cwd))

    def start_jupyterlab(self, cwd=None):
        """start a new jupyterlab connected to our kernel"""
        client = JupyterLabClient(connection_file=self._connection_file, cwd=cwd, parent=self)
        self._jupyter_processes.append(client)
        client.jupyterlab_ready.connect(self.jupyterlab_started)
        self._running_jupyterlab = True

    @property
    def has_running_jupyterlab(self):
        return self._running_jupyterlab

    def cleanup(self):
        """Clean up the consoles."""
        for c in self._jupyter_processes:
            if c.state() is QProcess.ProcessState.Running:
                c.kill()
                c.waitForFinished()
