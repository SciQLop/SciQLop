from datetime import datetime as datetime, timezone as timezone
from SciQLopPlots import SciQLopPlotRange as TimeRange
from speasy.core import make_utc_datetime as make_utc_datetime, AnyDateTimeType as AnyDateTimeType


def listify(a):
    if type(a) in (list, tuple):
        return a
    return [a]


def filter_none(a):
    return list(filter(None.__ne__, a))
