"""TimeRange and its UTC parsing.

Split out of ``SciQLop.core`` so that importing the package does not drag in
SciQLopPlots and speasy: the launcher imports ``SciQLop.core.common.python`` to
locate an interpreter, and a thin install has neither. ``SciQLop.core.TimeRange``
still resolves, through the lazy re-export in ``__init__``.
"""

from datetime import datetime

from SciQLopPlots import SciQLopPlotRange as _SciQLopPlotRange
from speasy.core import make_utc_datetime as make_utc_datetime, AnyDateTimeType as AnyDateTimeType


def _to_utc_epoch(value):
    if isinstance(value, (str, datetime)):
        return make_utc_datetime(value).timestamp()
    return value


class TimeRange(_SciQLopPlotRange):
    """SciQLopPlotRange with date inputs parsed on the Python side: the C++
    (str, str) overload silently turns unparseable strings into a NaN range,
    and the datetime overload shifts by the host timezone instead of using
    UTC. Strings and datetimes go through speasy's UTC parser, which raises
    ``ValueError`` on garbage."""

    def __init__(self, *args):
        super().__init__(*(_to_utc_epoch(a) for a in args))
