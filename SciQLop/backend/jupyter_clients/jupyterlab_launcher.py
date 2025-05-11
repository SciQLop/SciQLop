import os.path
import sys
from typing import Optional

from PySide6.QtCore import Signal
import secrets
from pathlib import Path

from .jupyter_client_process import SciQLopJupyterClient, ClientType, is_pyinstaller_exe, pyinstaller_exe_path
from ..common import find_available_port
from ..common.python import get_python
from SciQLop.backend import sciqlop_logging
import re
from platformdirs import *

_server_ready_regex = re.compile(r".*Jupyter Server [\.\d]+ is running at:.*")

log = sciqlop_logging.getLogger(__name__)

SCIQLOP_JUPYTERLAB_DIR = os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True),
                                      'jupyterlab')

__here__ = Path(__file__).parent


class JupyterLabClient(SciQLopJupyterClient):
    jupyterlab_ready = Signal(str)

    def __init__(self, connection_file: str, cwd: Optional[str] = None, parent=None):
        super().__init__(ClientType.JUPYTERLAB, stdout_parser=self._parse_stdout, stderr_parser=self._parse_stdout, parent=parent)
        if cwd is None:
            cwd = Path.home()
        self.port = find_available_port()
        self.token = secrets.token_hex(16)
        self.url = f"http://localhost:{self.port}/?token={self.token}"
        # JUPYTER_CONFIG_PATH=/tmp/_MEI4oIyQF/etc/jupyter/ JUPYTER_CONFIG_DIR=/tmp/_MEI4oIyQF/etc/jupyter/ JUPYTERLAB_DIR=/tmp/_MEI4oIyQF/share/jupyter/lab
        if 'win' not in sys.platform:  # On Windows it is not easy to build JupyterLab artifacts
            extra_env = {
                "JUPYTERLAB_DIR": SCIQLOP_JUPYTERLAB_DIR
            }
        else:
            extra_env = None

        args = [
            f"{__here__}/jupyterlab_auto_build.py",
            "-m",
            "jupyterlab",
            "--ServerApp.kernel_manager_class=SciQLop.Jupyter.lab_kernel_manager.ExternalMappingKernelManager",
            "--KernelProvisionerFactory.default_provisioner_name=sciqlop-kernel-provisioner",
            f"--port={self.port}",
            "--no-browser",
            f"--NotebookApp.token={self.token}",
            f"--NotebookApp.notebook_dir={cwd}",
            "--NotebookApp.terminals_enabled=False"
        ]
        if 'SCIQLOP_BUNDLED' in os.environ:
            args.insert(0, '-I')
        if 'SCIQLOP_DEBUG' in os.environ:
            args += ["--debug", "--log-level=DEBUG"]
        self._start_process(cmd=get_python(), args=args, connection_file=connection_file, extra_env=extra_env,
                            cwd=str(Path.home()))
        log.info(f"JupyterLab started at {self.url}")

    def _parse_stdout(self, txt: str) -> str:
        if next(_server_ready_regex.finditer(txt), None):
            self.jupyterlab_ready.emit(self.url)
        return txt
