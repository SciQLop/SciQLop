# taken here https://github.com/ipython/ipykernel/blob/main/examples/embedding/internal_ipkernel.py

import jupyter_client
from PySide6.QtCore import QObject

from ipykernel.kernelapp import IPKernelApp

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


class InternalIPKernel(QObject):
    """Internal ipykernel manager."""

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.ipkernel = None

    def init_ipkernel(self, backend):
        self.ipkernel = mpl_kernel(backend)

    def pushVariables(self, variable_dict):
        """ Given a dictionary containing name / value pairs, push those
        variables to the IPython console widget.

        :param variable_dict: Dictionary of variables to be pushed to the
            console's interactive namespace (```{variable_name: object, …}```)
        """
        self.ipkernel.shell.push(variable_dict)

    @property
    def connection_file(self) -> str:
        return jupyter_client.find_connection_file(self.ipkernel.abs_connection_file)

    def start(self):
        self.ipkernel.start()
