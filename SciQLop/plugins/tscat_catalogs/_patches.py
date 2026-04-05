"""Monkey-patches for tscat / tscat_gui datetime handling.

Fixes two issues until addressed upstream:

1. Naive-vs-aware mismatch: QDateTimeEdit.toPython() strips tzinfo,
   while other code paths may produce aware datetimes.  We strip
   tzinfo in SetAttributeAction so all values match tscat's naive
   ORM columns.

2. Start/stop ordering validation: tscat's _Event.__setattr__ and
   __init__ reject intermediate states where start > stop, which
   happens naturally when moving an event interactively (start and
   stop are written separately through an async queue).  We remove
   this validation — the UI already ensures final consistency.
"""

from datetime import datetime

from tscat.base import _BackendBasedEntity, _Event


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


def apply_tscat_gui_patches():
    from tscat_gui.tscat_driver.actions import SetAttributeAction

    _original_action = SetAttributeAction.action

    def _action_strip_tz(self):
        self.values = [_strip_tz(v) for v in self.values]
        _original_action(self)

    SetAttributeAction.action = _action_strip_tz
    _Event.__setattr__ = _event_setattr_no_order_check
