# taken here https://github.com/ipython/ipykernel/blob/main/examples/embedding/internal_ipkernel.py

import jupyter_client
from PySide6.QtCore import QObject, QTimer

from ipykernel.kernelapp import IPKernelApp
from ipykernel.ipkernel import IPythonKernel
from ipykernel.eventloops import register_integration, enable_gui

from SciQLop.backend import sciqlop_logging, sciqlop_application

log = sciqlop_logging.getLogger(__name__)


@register_integration('sciqlop')
def loop_sciqlop(kernel):
    """Start the SciQLop event loop."""
    timer = QTimer()
    timer.timeout.connect(kernel.do_one_iteration)
    timer.start(int(kernel._poll_interval))
    # sciqlop_application.sciqlop_event_loop().exec()


class SciQLopKernel(IPythonKernel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


def qt_kernel(mpl_backend=None):
    """Launch and return an IPython kernel with matplotlib support for the desired gui"""

    kernel = IPKernelApp.instance(kernel_name="SciQLop", log=sciqlop_logging.getLogger("SciQLop"),
                                  kernel_class=SciQLopKernel)
    kernel.capture_fd_output = False
    args = []  # ["--gui=sciqlop", "--colors=linux"]
    if mpl_backend is not None:
        args.append(f"--matplotlib={mpl_backend}")
    if len(args) > 0:
        kernel.initialize(["python", ] + args)
    else:
        kernel.initialize()
    enable_gui('sciqlop')
    sciqlop_logging.replace_stdios()
    return kernel


class InternalIPKernel(QObject):
    """Internal ipykernel manager."""

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.ipykernel = None

    def init_ipkernel(self, mpl_backend=None):
        self.ipykernel = qt_kernel(mpl_backend)

    def push_variables(self, variable_dict):
        """ Given a dictionary containing name / value pairs, push those
        variables to the IPython console widget.

        :param variable_dict: Dictionary of variables to be pushed to the
            console's interactive namespace (```{variable_name: object, …}```)
        """
        self.ipykernel.shell.push(variable_dict)

    def do_one_iteration(self):
        self.ipykernel.kernel.process_one(wait=True)

    def start(self):
        self.ipykernel.start()
        print("IPython kernel started")

    @property
    def connection_file(self) -> str:
        return jupyter_client.find_connection_file(self.ipykernel.abs_connection_file)
