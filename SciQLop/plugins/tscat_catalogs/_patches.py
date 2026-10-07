"""Monkey-patches for tscat / tscat_gui.

Fixes three issues until addressed upstream:

1. Naive-vs-aware mismatch: QDateTimeEdit.toPython() strips tzinfo,
   while other code paths may produce aware datetimes.  We strip
   tzinfo in SetAttributeAction so all values match tscat's naive
   ORM columns.

2. Start/stop ordering validation: tscat's _Event.__setattr__ and
   __init__ reject intermediate states where start > stop, which
   happens naturally when moving an event interactively (start and
   stop are written separately through an async queue).  We remove
   this validation — the UI already ensures final consistency.

3. Quitting while the driver's worker runs an action aborts the process:
   TscatDriver.stop() never waits for the worker after quit().

4. An action raising on the driver's worker thread is never completed, so
   whoever waits on it hangs. ``driver_action_failures()`` reports it instead.
"""

import atexit
import logging
from datetime import datetime

from PySide6.QtCore import QObject, Signal
from tscat.base import _BackendBasedEntity, _Event

log = logging.getLogger(__name__)


def _strip_tz(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _event_setattr_no_order_check(self, key, value):
    """_Event.__setattr__ without start/stop ordering validation."""
    from uuid import UUID
    if key == 'uuid':
        UUID(value, version=4)
    elif key in ['tags', 'products']:
        if any(not isinstance(v, str) for v in value):
            raise ValueError("a tag has to be a string")
        if any(',' in v for v in value):
            raise ValueError("a string-list value shall not contain a comma")
    elif key == 'rating':
        if value is not None:
            if not isinstance(value, int):
                raise ValueError("rating has to be an integer value")
            if value < 1 or value > 10:
                raise ValueError("rating has to be between 1 and 10")
    _BackendBasedEntity.__setattr__(self, key, value)


def _stop_after_running_action(self):
    """TscatDriver.stop() that lets the running action finish.

    The original waits for a worker that only stops after quit(), then calls
    quit() without waiting: a worker busy at exit is destroyed while running
    and Qt aborts the process. No timeout: an action is a database call that
    ends, and cutting a catalog write short is worse than a slower exit."""
    self._worker.quit()
    self._worker.wait()


class _DriverActionFailures(QObject):
    failed = Signal(object, str)


def _do_action_reporting_failure(self, action):
    """_TscatDriverWorker.do_action that survives a failing action.

    action_done is still not emitted for a failed action: tscat_gui's own
    handler reads the action's result (e.g. asserts on a created entity)."""
    try:
        action.action()
    except Exception as error:
        log.error("tscat action %s failed", type(action).__name__, exc_info=True)
        driver_action_failures().failed.emit(action, f"{type(error).__name__}: {error}")
        return
    action.completed = True
    self.action_done.emit(action)


def driver_action_failures() -> _DriverActionFailures:
    """Signal source for actions that raised on the driver thread; installs
    the worker patch on first use. Stored on tscat_gui's driver so both module
    identities of this plugin (see orphans.py) share one instance."""
    from tscat_gui.tscat_driver.driver import _TscatDriverWorker, tscat_driver
    failures = getattr(tscat_driver, "_sciqlop_action_failures", None)
    if failures is None:
        failures = _DriverActionFailures()
        tscat_driver._sciqlop_action_failures = failures
        _TscatDriverWorker.do_action = _do_action_reporting_failure
    return failures


def apply_tscat_gui_patches():
    from tscat_gui.tscat_driver.actions import SetAttributeAction
    from tscat_gui.tscat_driver.driver import TscatDriver, tscat_driver

    TscatDriver.stop = _stop_after_running_action
    # tscat_gui registered the original bound stop() at import; atexit runs
    # last-registered first, so this one finishes the worker before it.
    atexit.register(tscat_driver.stop)

    _original_action = SetAttributeAction.action

    def _action_strip_tz(self):
        self.values = [_strip_tz(v) for v in self.values]
        _original_action(self)

    SetAttributeAction.action = _action_strip_tz
    _Event.__setattr__ = _event_setattr_no_order_check
