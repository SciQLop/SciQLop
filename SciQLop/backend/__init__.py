from datetime import datetime, timezone
from SciQLopPlots import SciQLopPlotRange as TimeRange
from .icons import register_icon  # noqa: F401
from speasy.core import make_utc_datetime, AnyDateTimeType


def listify(a):
    if type(a) in (list, tuple):
        return a
    return [a]


def filter_none(a):
    return list(filter(None.__ne__, a))
