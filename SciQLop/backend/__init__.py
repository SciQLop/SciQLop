from datetime import datetime
from SciQLopPlots import SciQLopPlotRange
from .icons import icons, register_icon  # noqa: F401
from .products_model.product_node import ProductNode as Product  # noqa: F401
from speasy.core import make_utc_datetime, AnyDateTimeType


def listify(a):
    if type(a) in (list, tuple):
        return a
    return [a]


def filter_none(a):
    return list(filter(None.__ne__, a))


class TimeRange(SciQLopPlotRange):

    def __init__(self, start: AnyDateTimeType, stop: AnyDateTimeType):
        """Create a TimeRange object. The start and stop times can be provided as Python datetime objects, timestamps, or strings."""
        super().__init__(0, 0)
        if type(start) not in (float, int):
            start = make_utc_datetime(start).timestamp()
        if type(stop) not in (float, int):
            stop = make_utc_datetime(stop).timestamp()
        self.start = min(start, stop)
        self.stop = max(stop, start)

    @property
    def start(self):
        """The start time in seconds since the epoch."""
        return super().start()

    @start.setter
    def start(self, value: float):
        """Set the start time in seconds since the epoch."""
        assert value <= self.stop and type(value) is float
        self[0] = value

    @property
    def datetime_start(self):
        """The start time as a Python datetime object."""
        return datetime.utcfromtimestamp(self.start)

    @property
    def stop(self):
        """The stop time in seconds since the epoch."""
        return super().stop()

    @stop.setter
    def stop(self, value: float):
        """Set the stop time in seconds since the epoch."""
        assert value >= self.start and type(value) is float
        self[1] = value

    @property
    def datetime_stop(self):
        """The stop time as a Python datetime object."""
        return datetime.utcfromtimestamp(self.stop)

    def __repr__(self):
        return f"""TimeRange: {self._start}, {self._stop}
\t{self.datetime_start}, {self.datetime_stop}
        """
