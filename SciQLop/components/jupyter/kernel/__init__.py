# taken here https://github.com/ipython/ipykernel/blob/main/examples/embedding/internal_ipkernel.py
from qasync import asyncSlot
import jupyter_client
from PySide6.QtCore import QObject, QTimer
from ipykernel.kernelapp import IPKernelApp
from ipykernel.ipkernel import IPythonKernel

from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


class SciQLopKernel(IPythonKernel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


POLL_FAST_MS = 5
POLL_SLOW_MS = 50


class _KernelPoller(QObject):
    def __init__(self, kernel: IPythonKernel):
        super().__init__()
        assert kernel is not None
        self.kernel = kernel
        self._timer = QTimer()
        if hasattr(self.kernel, "do_one_iteration"):
            self._timer.timeout.connect(self._poll_kernel_do_one_iteration)
        else:
            self._timer.timeout.connect(self._poll_kernel_flush)

    def start(self):
        self._timer.start(POLL_FAST_MS)

    def stop(self):
        self._timer.stop()

    def _set_interval(self, ms: int):
        if self._timer.isActive():
            self._timer.setInterval(ms)

    @asyncSlot()
    async def _poll_kernel_do_one_iteration(self):
        try:
            await self.kernel.do_one_iteration()
            self._set_interval(POLL_FAST_MS)
        except Exception as e:
            log.error(f"Error while polling IPython kernel: {e}")
            self._set_interval(POLL_SLOW_MS)

    @asyncSlot()
    async def _poll_kernel_flush(self):
        from ipykernel.eventloops import get_shell_stream
        get_shell_stream(self.kernel).flush(limit=1)


class SciQLopKernelApp(IPKernelApp):

    def start(self):
        if self.subapp is not None:
            return self.subapp.start()
        if self.poller is not None:
            self.poller.start()


class InternalIPKernel(QObject):
    """Internal ipykernel manager."""

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.ipykernel = None

    def init_ipkernel(self):
        self.ipykernel = SciQLopKernelApp.instance(kernel_name="SciQLop",
                                                   kernel_class=SciQLopKernel)
        self.ipykernel.capture_fd_output = False
        self.ipykernel.initialize()
        self._register_magics()

    def _register_magics(self):
        from SciQLop.user_api.magics import register_all_magics
        register_all_magics(self.ipykernel.shell)

    def push_variables(self, variable_dict):
        self.ipykernel.shell.push(variable_dict)

    @property
    def connection_file(self) -> str:
        return jupyter_client.find_connection_file(self.ipykernel.abs_connection_file)


from .manager import KernelManager
