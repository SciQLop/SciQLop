import pytest
from unittest.mock import MagicMock, patch


def test_kernel_manager_defers_variables_before_init():
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km.push_variables({"x": 42})
    assert km._deferred_variables == {"x": 42}


def test_kernel_manager_shutdown_stops_poller():
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km._poller = MagicMock()
    km._kernel_app = MagicMock()
    km._clients = MagicMock()
    km._initialized = True

    km.shutdown()

    km._clients.cleanup.assert_called_once()
    km._poller.stop.assert_called_once()
    km._kernel_app.kernel.do_shutdown.assert_called_once()


def test_kernel_manager_shutdown_noop_when_not_initialized():
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km.shutdown()  # Should not raise


def test_kernel_manager_init_is_idempotent():
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km._initialized = True
    km.init()  # Should be a no-op, not create new kernel
    assert km._kernel is None  # Was never actually created
