# taken here https://github.com/ipython/ipykernel/blob/main/examples/embedding/internal_ipkernel.py
import os.path
import sys
from typing import List, Mapping, Optional
from contextlib import closing
import socket
import secrets
from pathlib import Path


import jupyter_client
from PySide6.QtCore import QProcess, QProcessEnvironment, QObject, Signal

from ipykernel.kernelapp import IPKernelApp

from enum import Enum
from SciQLop.backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


def is_pyinstaller_exe() -> bool:
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def pyinstaller_exe_path() -> str:
    assert is_pyinstaller_exe()
    return sys._MEIPASS


def get_python() -> str:
    if "APPIMAGE" in os.environ:
        return os.path.join(os.environ["APPDIR"], "usr/bin/python3")
    python_exe = 'python.exe' if os.name == 'nt' else 'python'
    if python_exe not in os.path.basename(sys.executable):
        def _find_python() -> str:
            return next(filter(lambda p: os.path.exists(p),
                               map(lambda p: os.path.join(p, python_exe),
                                   [sys.prefix, os.path.join(sys.prefix, 'bin'), sys.base_prefix, sys.base_exec_prefix,
                                    os.path.join(sys.base_prefix, 'bin')])))

        if (python_path := _find_python()) in (None, "") or not os.path.exists(python_path):
            raise RuntimeError("Could not find python executable")
        else:
            return python_path
    return sys.executable


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

        if os.name == 'nt':
            sep = ';'
        else:
            sep = ':'
        PYTHONPATH = sep.join(sys.path)
        if is_pyinstaller_exe():
            PYTHONPATH += sep.join([f"{pyinstaller_exe_path()}", f"{pyinstaller_exe_path()}/base_library.zip"])
        env.insert("PYTHONPATH", PYTHONPATH)
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self._forward_stdout)
        self.process.readyReadStandardError.connect(self._forward_stderr)
        self.process.stateChanged.connect(self._process_state_changed)
        self.process.start(cmd, args)
        print(f"\n{self.process.program()}  {' '.join(self.process.arguments())}\n")

    def state(self) -> QProcess.ProcessState:
        return self.process.state()

    def _process_state_changed(self, state: QProcess.ProcessState):
        print(state)

    def _forward_stdout(self):
        print(str(self.process.readAllStandardOutput(), encoding="utf-8"))

    def _forward_stderr(self):
        print(str(self.process.readAllStandardError(), encoding="utf-8"))

    def kill(self):
        self.process.kill()

    def waitForFinished(self):
        self.process.waitForFinished()


class QtConsoleClient(SciQLopJupyterClient):
    def __init__(self, connection_file: str):
        super().__init__(ClientType.QTCONSOLE)
        args = ["-S", "-c", "from qtconsole import qtconsoleapp;qtconsoleapp.main()", "--existing", connection_file]
        self._start_process(cmd=get_python(), args=args, connection_file=connection_file)


class JupyterLabClient(SciQLopJupyterClient):
    def __init__(self, connection_file: str, workdir: Optional[str] = None):
        super().__init__(ClientType.JUPYTERLAB)
        if workdir is None:
            workdir = Path.home()
        self.port = find_available_port()
        self.token = secrets.token_hex(16)
        self.url = f"http://localhost:{self.port}/?token={self.token}"
        # JUPYTER_CONFIG_PATH=/tmp/_MEI4oIyQF/etc/jupyter/ JUPYTER_CONFIG_DIR=/tmp/_MEI4oIyQF/etc/jupyter/ JUPYTERLAB_DIR=/tmp/_MEI4oIyQF/share/jupyter/lab
        if is_pyinstaller_exe():
            path = pyinstaller_exe_path()
            extra_env = {
                "JUPYTER_CONFIG_PATH": f"{path}/etc/jupyter/",
                "JUPYTER_CONFIG_DIR": f"{path}/etc/jupyter/",
                "JUPYTERLAB_DIR": f"{path}/share/jupyter/lab",
            }
        else:
            extra_env = None
        args = [
            "-S",
            "-m",
            "jupyterlab",
            "--debug",
            "--log-level=DEBUG",
            "--ServerApp.kernel_manager_class=SciQLop.Jupyter.lab_kernel_manager.ExternalMappingKernelManager",
            "--KernelProvisionerFactory.default_provisioner_name=sciqlop-kernel-provisioner",
            f"--port={self.port}",
            "--no-browser",
            f"--NotebookApp.token={self.token}",
            f"--NotebookApp.notebook_dir={workdir}",
        ]
        self._start_process(cmd=get_python(), args=args, connection_file=connection_file, extra_env=extra_env)
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
