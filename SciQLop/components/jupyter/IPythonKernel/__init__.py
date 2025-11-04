# taken here https://github.com/ipython/ipykernel/blob/main/examples/embedding/internal_ipkernel.py
from qasync import asyncSlot
import jupyter_client
from PySide6.QtCore import QObject, QTimer
from typing import Optional

from ipykernel.kernelapp import IPKernelApp
from ipykernel.ipkernel import IPythonKernel

from SciQLop.core import sciqlop_application
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


class SciQLopKernel(IPythonKernel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class _KernelPoller(QObject):
    def __init__(self, kernel: IPythonKernel, poll_interval: float = 0.1):
        super().__init__()
        assert kernel is not None
        self.kernel = kernel
        self._poll_interval = poll_interval
        self.timer = QTimer()
        if hasattr(self.kernel, "do_one_iteration"):
            self.timer.timeout.connect(self._poll_kernel_do_one_iteration)
        else:
            self.timer.timeout.connect(self._poll_kernel_flush)

    def start(self):
        self.timer.start(int(1000 * self._poll_interval))

    @asyncSlot()
    async def _poll_kernel_do_one_iteration(self):
        await self.kernel.do_one_iteration()

    @asyncSlot()
    async def _poll_kernel_flush(self):
        from ipykernel.eventloops import get_shell_stream
        get_shell_stream(self.kernel).flush(limit=1)


class SciQLopKernelApp(IPKernelApp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kernel_poller: Optional[_KernelPoller] = None

    def start(self):
        """Start the application."""
        if self.subapp is not None:
            return self.subapp.start()
        if self.poller is not None:
            self.poller.start()
        self.kernel.start()
        self._kernel_poller = _KernelPoller(kernel=self.kernel, poll_interval=0.01)
        self._kernel_poller.start()
        sciqlop_application.sciqlop_event_loop().exec()


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
