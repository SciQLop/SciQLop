# taken here https://github.com/ipython/ipykernel/blob/main/examples/embedding/internal_ipkernel.py
import sys
from typing import List, Mapping, Optional
from contextlib import closing
import socket
import secrets

import jupyter_client
from PySide6.QtCore import QProcess, QProcessEnvironment, QObject, Signal

from ipykernel.kernelapp import IPKernelApp

from enum import Enum
from SciQLop.backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


def mpl_kernel(gui="qt"):
    """Launch and return an IPython kernel with matplotlib support for the desired gui"""
    kernel = IPKernelApp.instance(kernel_name="SciQlop", log=sciqlop_logging.getLogger("SciQlop"))
    kernel.capture_fd_output = False
    kernel.initialize(
        [
            "python",
            f"--matplotlib={gui}",
            # '--log-level=10'
        ]
    )
    sciqlop_logging.replace_stdios()
    return kernel


def find_available_port(start_port: int = 8000, end_port: int = 9000) -> Optional[int]:
    for port in range(start_port, end_port):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            res = sock.connect_ex(('localhost', port))
            if res != 0:
                return port
    return None


class ClientType(Enum):
    QTCONSOLE = "qtconsole"
    JUPYTERLAB = "jupyterlab"


class SciQLopJupyterClient:
    def __init__(self, client_type: ClientType):
        self.process = QProcess()
        self.client_type = client_type

    def _start_process(self, cmd: str, args: List[str], connection_file: str,
                       extra_env: Optional[Mapping[str, str]] = None):
        env = QProcessEnvironment.systemEnvironment()
        env.insert("SCIQLOP_IPYTHON_CONNECTION_FILE", connection_file)
        if extra_env:
            for key, value in extra_env.items():
                env.insert(key, value)
        self.process.setProcessEnvironment(env)
        self.process.start(cmd, args)

    def state(self) -> QProcess.ProcessState:
        return self.process.state()

    def kill(self):
        self.process.kill()

    def waitForFinished(self):
        self.process.waitForFinished()


class QtConsoleClient(SciQLopJupyterClient):
    def __init__(self, connection_file: str):
        super().__init__(ClientType.QTCONSOLE)
        args = ["-c", "from qtconsole import qtconsoleapp;qtconsoleapp.main()", "--existing", connection_file]
        self._start_process(cmd=sys.executable, args=args, connection_file=connection_file)


class JupyterLabClient(SciQLopJupyterClient):
    def __init__(self, connection_file: str):
        super().__init__(ClientType.JUPYTERLAB)
        self.port = find_available_port()
        self.token = secrets.token_hex(16)
        self.url = f"http://localhost:{self.port}/?token={self.token}"
        args = ["lab",
                "--debug",
                "--log-level=DEBUG",
                "--ServerApp.kernel_manager_class=SciQLop.Jupyter.lab_kernel_manager.ExternalMappingKernelManager",
                "--KernelProvisionerFactory.default_provisioner_name=sciqlop-kernel-provisioner",
                f"--port={self.port}",
                "--no-browser",
                f"--NotebookApp.token={self.token}",
                ]
        self._start_process(cmd="jupyter", args=args, connection_file=connection_file)
        log.info(f"JupyterLab started at {self.url}")


class InternalIPKernel(QObject):
    """Internal ipykernel manager."""
    jupyterlab_started = Signal(str)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.ipkernel = None
        self._jupyter_processes: List[SciQLopJupyterClient] = []

    def init_ipkernel(self, backend):
        self.ipkernel = mpl_kernel(backend)

    def pushVariables(self, variable_dict):
        """ Given a dictionary containing name / value pairs, push those
        variables to the IPython console widget.

        :param variable_dict: Dictionary of variables to be pushed to the
            console's interactive namespace (```{variable_name: object, …}```)
        """
        self.ipkernel.shell.push(variable_dict)

    def _connection_file(self) -> str:
        return jupyter_client.find_connection_file(self.ipkernel.abs_connection_file)

    def new_qt_console(self, evt=None):
        """start a new qtconsole connected to our kernel"""
        self._jupyter_processes.append(QtConsoleClient(connection_file=self._connection_file()))

    def start_jupyterlab(self, evt=None):
        """start a new jupyterlab connected to our kernel"""
        self._jupyter_processes.append(JupyterLabClient(connection_file=self._connection_file()))
        self.jupyterlab_started.emit(self._jupyter_processes[-1].url)

    def cleanup_consoles(self, evt=None):
        """Clean up the consoles."""
        for c in self._jupyter_processes:
            if c.state() is QProcess.ProcessState.Running:
                c.kill()
                c.waitForFinished()

    def start(self):
        self.ipkernel.start()