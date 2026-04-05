"""Tests for the new jupyqt-based KernelManager."""


def test_kernel_manager_has_shell(qapp):
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    assert km.shell is not None


def test_kernel_manager_push_before_start(qapp):
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km.push_variables({"test_var": 42})
    assert km.shell.user_ns["test_var"] == 42


def test_kernel_manager_wrap_qt(qapp):
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    from PySide6.QtWidgets import QLabel
    km = KernelManager()
    label = QLabel("test")
    proxy = km.wrap_qt(label)
    assert proxy is not None


def test_kernel_manager_shutdown(qapp):
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km.start()
    km.shutdown()
    # Should not raise — clean shutdown
