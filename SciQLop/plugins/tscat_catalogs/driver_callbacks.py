"""Callbacks for requests sent to the tscat database thread."""
import weakref
from typing import Callable


def while_alive(owner, callback: Callable) -> Callable:
    """A request callback calling `callback(owner, action)`, and nothing once `owner` is gone.

    Why not a bound method or a closure over `owner`: the database thread can be the last to drop a
    request, so a callback holding `owner` gets it destroyed there. Qt cannot stop a QObject's timers
    from another thread, and the timer later fires on freed memory (segfault).
    """
    owner_ref = weakref.ref(owner)

    def call(action):
        owner = owner_ref()
        if owner is not None:
            callback(owner, action)

    return call
