from typing import Optional

import secrets
from pathlib import Path

from .jupyter_client import SciQLopJupyterClient, ClientType, is_pyinstaller_exe, pyinstaller_exe_path
from ..common import find_available_port, get_python
from SciQLop.backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


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
