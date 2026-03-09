import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from PySide6.QtCore import QTimer

from SciQLop.components.jupyter.kernel import (
    POLL_FAST_MS,
    POLL_SLOW_MS,
    _KernelPoller,
)


def _make_kernel(do_one_iteration=True, raises=False):
    kernel = MagicMock()
    if do_one_iteration:
        mock = AsyncMock()
        if raises:
            mock.side_effect = RuntimeError("boom")
        kernel.do_one_iteration = mock
    else:
        del kernel.do_one_iteration
    return kernel


class TestKernelPollerInit:
    def test_starts_with_fast_interval(self, qtbot):
        poller = _KernelPoller(_make_kernel())
        poller.start()
        assert poller._timer.interval() == POLL_FAST_MS
        assert poller._timer.isActive()
        poller.stop()

    def test_no_is_iterating_attribute(self, qtbot):
        poller = _KernelPoller(_make_kernel())
        assert not hasattr(poller, "_is_iterating")

    def test_stop_stops_timer(self, qtbot):
        poller = _KernelPoller(_make_kernel())
        poller.start()
        assert poller._timer.isActive()
        poller.stop()
        assert not poller._timer.isActive()


class TestKernelPollerAdaptive:
    def test_stays_fast_on_success(self, qtbot):
        kernel = _make_kernel()
        poller = _KernelPoller(kernel)
        poller.start()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(poller._poll_kernel_do_one_iteration())
        assert poller._timer.interval() == POLL_FAST_MS
        poller.stop()

    def test_slows_down_on_error(self, qtbot):
        kernel = _make_kernel(raises=True)
        poller = _KernelPoller(kernel)
        poller.start()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(poller._poll_kernel_do_one_iteration())
        assert poller._timer.interval() == POLL_SLOW_MS
        poller.stop()
