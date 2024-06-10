from datetime import datetime
from SciQLopPlots import QCPRange
from .icons import icons, register_icon  # noqa: F401
from .products_model.product_node import ProductNode as Product  # noqa: F401
from speasy.core import make_utc_datetime, AnyDateTimeType


def listify(a):
    if type(a) in (list, tuple):
        return a
    return [a]


def filter_none(a):
    return list(filter(None.__ne__, a))


class TimeRange:
    """A class representing a time range. It is a simple wrapper around a start and stop time in seconds since the epoch.

    Methods:
    - from_qcprange: Create a TimeRange from a QCPRange.
    - to_qcprange: Convert the TimeRange to a QCPRange.
    - overlaps: Check if this TimeRange overlaps with another TimeRange.
    - contains: Check if this TimeRange contains another TimeRange.
    - __mul__: Multiply the TimeRange by a constant factor.
    - __rmul__: Multiply the TimeRange by a constant factor.
    - __truediv__: Divide the TimeRange by a constant factor.
    - __repr__: Return a string representation of the TimeRange.

    Attributes:
    - start: The start time in seconds since the epoch.
    - datetime_start: The start time as a Python datetime object.
    - stop: The stop time in seconds since the epoch.
    - datetime_stop: The stop time as a Python datetime object.

    """
    __slots__ = ["_start", "_stop"]

    def __init__(self, start: AnyDateTimeType, stop: AnyDateTimeType):
        """Create a TimeRange object. The start and stop times can be provided as Python datetime objects, timestamps, or strings."""
        if type(start) not in (float, int):
            start = make_utc_datetime(start).timestamp()
        if type(stop) not in (float, int):
            stop = make_utc_datetime(stop).timestamp()
        self._start = min(start, stop)
        self._stop = max(stop, start)

    @staticmethod
    def from_qcprange(qcprange: QCPRange):
        """Create a TimeRange from a QCPRange.
        Args:
            qcprange (QCPRange): The QCPRange to convert.
        Returns:
            TimeRange: The TimeRange object.

        Note:
            This method is mainly used internally by the SciQLop backend.

        See Also:
            to_qcprange
        """
        return TimeRange(qcprange.lower, qcprange.upper)

    def to_qcprange(self):
        """Convert the TimeRange to a QCPRange.
        Returns:
            QCPRange: The QCPRange object.

        Note:
            This method is mainly used internally by the SciQLop backend.

        See Also:
            from_qcprange
        """
        return QCPRange(self._start, self._stop)

    @property
    def start(self):
        """The start time in seconds since the epoch."""
        return self._start

    @start.setter
    def start(self, value: float):
        """Set the start time in seconds since the epoch."""
        assert value <= self._stop and type(value) is float
        self._start = value

    @property
    def datetime_start(self):
        """The start time as a Python datetime object."""
        return datetime.utcfromtimestamp(self._start)

    @property
    def stop(self):
        """The stop time in seconds since the epoch."""
        return self._stop

    @stop.setter
    def stop(self, value: float):
        """Set the stop time in seconds since the epoch."""
        assert value >= self._start and type(value) is float
        self._stop = value

    @property
    def datetime_stop(self):
        """The stop time as a Python datetime object."""
        return datetime.utcfromtimestamp(self._stop)

    def __mul__(self, other):
        if type(other) is float:
            new_dt = (self._stop - self._start) * other / 2.
            center = (self._start + self._stop) / 2.
            return TimeRange(center - new_dt, center + new_dt)
        elif type(other) is int:
            return self.__mul__(float(other))
        else:
            return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if type(other) is float:
            new_dt = (self._stop - self._start) / other / 2.
            center = (self._start + self._stop) / 2.
            return TimeRange(center - new_dt, center + new_dt)
        elif type(other) is int:
            return self.__truediv__(float(other))
        else:
            return NotImplemented

    def overlaps(self, other: "TimeRange"):
        """Check if this TimeRange overlaps with another TimeRange. Two TimeRanges overlap if their intersection is not empty.

        Args:
            other (TimeRange): The other TimeRange to check.
        Returns:
            bool: True if the TimeRanges overlap, False otherwise.
        """
        return max(self._start, other._start) <= min(self._stop, other._stop)

    def contains(self, other: "TimeRange"):
        """Check if this TimeRange contains another TimeRange. One TimeRange contains another if the other TimeRange is completely inside it.

        Args:
            other (TimeRange): The other TimeRange to check.
        Returns:
            bool: True if this TimeRange contains the other TimeRange, False otherwise.
        """
        return self._start <= other._start and self._stop >= other._stop

    def __repr__(self):
        return f"""TimeRange: {self._start}, {self._stop}
\t{self.datetime_start}, {self.datetime_stop}
        """
