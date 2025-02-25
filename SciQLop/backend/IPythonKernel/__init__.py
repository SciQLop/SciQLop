# taken here https://github.com/ipython/ipykernel/blob/main/examples/embedding/internal_ipkernel.py
from qasync import asyncSlot
import jupyter_client
from PySide6.QtCore import QObject, QTimer

from ipykernel.kernelapp import IPKernelApp
from ipykernel.ipkernel import IPythonKernel

from SciQLop.backend import sciqlop_logging, sciqlop_application

log = sciqlop_logging.getLogger(__name__)

class SciQLopKernel(IPythonKernel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class SciQLopKernelApp(IPKernelApp):
    def start(self):
        """Start the application."""
        if self.subapp is not None:
            return self.subapp.start()
        if self.poller is not None:
            self.poller.start()
        self.kernel.start()
        self.timer = QTimer()
        self.timer.timeout.connect(self.do_one_iteration)
        self.timer.start(int(1000 * self.kernel._poll_interval))
        sciqlop_application.sciqlop_event_loop().exec()

    @asyncSlot()
    async def do_one_iteration(self):
        await self.kernel.do_one_iteration()


class InternalIPKernel(QObject):
    """Internal ipykernel manager."""

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.ipykernel = None

    def init_ipkernel(self, mpl_backend=None):
        self.ipykernel = SciQLopKernelApp.instance(kernel_name="SciQLop",
                                                   kernel_class=SciQLopKernel)
        self.ipykernel.capture_fd_output = False
        self.ipykernel.initialize()

    def push_variables(self, variable_dict):
        """ Given a dictionary containing name / value pairs, push those
        variables to the IPython console widget.

        :param variable_dict: Dictionary of variables to be pushed to the
            console's interactive namespace (```{variable_name: object, …}```)
        """
        self.ipykernel.shell.push(variable_dict)

    # def do_one_iteration(self):
    #    self.ipykernel.kernel.process_one(wait=True)

    def start(self):
        self.ipykernel.start()
        log.info("IPython kernel started")

    @property
    def connection_file(self) -> str:
        return jupyter_client.find_connection_file(self.ipykernel.abs_connection_file)
