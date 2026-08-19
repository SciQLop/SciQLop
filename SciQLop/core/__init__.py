from datetime import datetime as datetime, timezone as timezone

# TimeRange and speasy's date helpers are resolved on first access: they need
# SciQLopPlots and speasy, which a thin (launcher-only) install does not have,
# and the launcher imports SciQLop.core.common.python through this package.
# See tests/test_launcher_thin_imports.py.
_LAZY = ("TimeRange", "as_time_range", "make_utc_datetime", "AnyDateTimeType")


def __getattr__(name):
    if name in _LAZY:
        from . import time_range
        return getattr(time_range, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted([*globals(), *_LAZY])


def listify(a):
    if type(a) in (list, tuple):
        return a
    return [a]


def filter_none(a):
    return list(filter(None.__ne__, a))
