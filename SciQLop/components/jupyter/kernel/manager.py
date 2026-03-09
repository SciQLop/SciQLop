from typing import Optional
from PySide6.QtCore import QObject, Signal

from SciQLop.components.jupyter.kernel import InternalIPKernel, _KernelPoller, SciQLopKernelApp
from SciQLop.components.jupyter.jupyter_clients.clients_manager import ClientsManager
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.sciqlop_application import sciqlop_event_loop

log = getLogger(__name__)


class KernelManager(QObject):
    """Owns the full IPython kernel lifecycle: init, start, push_variables, shutdown."""
    jupyterlab_started = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._kernel: Optional[InternalIPKernel] = None
        self._kernel_app: Optional[SciQLopKernelApp] = None
        self._poller: Optional[_KernelPoller] = None
        self._clients: Optional[ClientsManager] = None
        self._deferred_variables: dict = {}
        self._initialized = False

    def init(self):
        if self._initialized:
            return
        self._kernel = InternalIPKernel()
        self._kernel.init_ipkernel()
        self._kernel_app = self._kernel.ipykernel
        self._clients = ClientsManager(self._kernel.connection_file, parent=self)
        self._clients.jupyterlab_started.connect(self.jupyterlab_started)
        self._flush_deferred_variables()
        self._initialized = True

    def _flush_deferred_variables(self):
        if self._deferred_variables:
            self._kernel.push_variables(self._deferred_variables)
            self._deferred_variables.clear()

    def start(self):
        if not self._initialized:
            self.init()
        self._kernel_app.kernel.start()
        self._poller = _KernelPoller(kernel=self._kernel_app.kernel)
        self._poller.start()
        sciqlop_event_loop().exec()

    def push_variables(self, variable_dict: dict):
        if not self._initialized:
            self._deferred_variables.update(variable_dict)
        else:
            self._kernel.push_variables(variable_dict)

    def shutdown(self):
        if not self._initialized:
            return
        if self._clients:
            self._clients.cleanup()
        if self._poller:
            self._poller.stop()
        if self._kernel_app and self._kernel_app.kernel:
            self._kernel_app.kernel.do_shutdown(restart=False)

    @property
    def connection_file(self) -> Optional[str]:
        if self._kernel:
            return self._kernel.connection_file
        return None

    @property
    def clients(self) -> Optional[ClientsManager]:
        return self._clients

    @property
    def is_initialized(self) -> bool:
        return self._initialized
