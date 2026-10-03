"""Interval timelines: coloured bars on named lanes (observation plans, instrument modes)."""
from datetime import datetime
from typing import Callable, Dict, Hashable, List, NamedTuple, Optional, Sequence, Union

import numpy as np
from PySide6.QtGui import QColor
from speasy.core import make_utc_datetime

from ._graphs import _wire_destroyed
from ._thread_safety import on_main_thread, GuardedImpl


class Interval(NamedTuple):
    """One interval as last given to :meth:`Timeline.set_intervals`. Times are epoch seconds."""
    id: Hashable
    lane: str
    category: str
    label: str
    start: float
    stop: float

    @property
    def duration(self) -> float:
        return self.stop - self.start


class IntervalEdit(NamedTuple):
    """Where the user dragged an interval to. Times are epoch seconds."""
    id: Hashable
    start: float
    stop: float
    lane: str


def _epoch_seconds_of(value) -> float:
    if isinstance(value, str):
        # str() because numpy hands back np.str_, which speasy's parser rejects.
        return make_utc_datetime(str(value)).timestamp()
    if isinstance(value, datetime):
        return make_utc_datetime(value).timestamp()
    return float(value)


def _epoch_seconds(values) -> np.ndarray:
    a = np.asarray(values)
    if np.issubdtype(a.dtype, np.datetime64):
        return a.astype("datetime64[ns]").astype(np.int64) / 1e9
    if a.dtype == object or a.dtype.kind in "US":
        return np.array([_epoch_seconds_of(v) for v in a.ravel()], dtype=np.float64)
    return a.astype(np.float64)


def _column(values, n: int) -> List[str]:
    return [""] * n if values is None else [str(v) for v in values]


def _unique_ids(ids, n: int) -> list:
    ids = list(range(n)) if ids is None else list(ids)
    if len(set(ids)) != len(ids):
        raise ValueError("timeline ids must be unique")
    return ids


class Timeline(GuardedImpl):
    """Intervals drawn as coloured bars on named lanes, synced with the panel's time axis.

    Ids can be any hashable; every callback hands them back unchanged. User edits are
    proposals: the timeline keeps showing the data from the last :meth:`set_intervals`
    call until you call it again with the accepted changes.
    """

    def __init__(self, impl):
        self._impl = impl
        self._rows: List[Interval] = []
        self._row_of: Dict[Hashable, int] = {}
        _wire_destroyed(self, impl)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The timeline does not exist anymore.")
        return self._impl

    def _id(self, row) -> Hashable:
        return self._rows[int(row)].id

    @on_main_thread
    def set_intervals(self, start, stop=None, *, lane: Optional[Sequence[str]] = None,
                      category: Optional[Sequence[str]] = None, label: Optional[Sequence[str]] = None,
                      ids: Optional[Sequence[Hashable]] = None):
        """Replace every interval.

        Parameters
        ----------
        start, stop : array-like
            Epoch seconds, ``datetime64``, datetimes or date strings (UTC). A missing
            ``stop`` makes every interval an instant event.
        lane, category, label : sequence of str, optional
            One per interval. Lanes and categories keep their first-seen order;
            each category gets the same colour in every timeline.
        ids : sequence of hashables, optional
            Unique, one per interval. Defaults to the interval's position.
        """
        start = _epoch_seconds(start)
        stop = start.copy() if stop is None else _epoch_seconds(stop)
        n = len(start)
        ids = _unique_ids(ids, n)
        # The C++ side only takes float ids; rows stand in for them, mapped back in callbacks.
        self._get_impl_or_raise().set_intervals(start, stop, lane=lane, category=category, label=label,
                                                ids=np.arange(len(ids), dtype=np.float64))
        self._rows = [Interval(*row) for row in zip(ids, _column(lane, n), _column(category, n),
                                                    _column(label, n), start.tolist(), stop.tolist())]
        self._row_of = {interval.id: row for row, interval in enumerate(self._rows)}

    def interval(self, interval_id: Hashable) -> Interval:
        """The interval with this id, as last given to :meth:`set_intervals`."""
        return self._rows[self._row_of[interval_id]]

    def __len__(self) -> int:
        return len(self._rows)

    @property
    @on_main_thread
    def lanes(self) -> List[str]:
        """Displayed lanes, top to bottom. Assign a list to reorder them or hide the others."""
        return list(self._get_impl_or_raise().lanes)

    @lanes.setter
    @on_main_thread
    def lanes(self, names: Sequence[str]):
        self._get_impl_or_raise().lanes = list(names)

    @on_main_thread
    def rename_lane(self, old: str, new: str):
        self._get_impl_or_raise().rename_lane(old, new)
        self._rows = [r._replace(lane=new) if r.lane == old else r for r in self._rows]

    @property
    @on_main_thread
    def style(self) -> str:
        """``"wave"`` (bus-shaped bars and an idle line per lane, like a logic analyzer;
        the default) or ``"bars"`` (plain bars)."""
        return self._get_impl_or_raise().style

    @style.setter
    @on_main_thread
    def style(self, name: str):
        self._get_impl_or_raise().style = name

    @property
    @on_main_thread
    def lane_height(self) -> int:
        """Height of one lane in pixels."""
        return self._get_impl_or_raise().lane_height()

    @lane_height.setter
    @on_main_thread
    def lane_height(self, pixels: int):
        self._get_impl_or_raise().set_lane_height(int(pixels))

    @on_main_thread
    def set_category_colors(self, colors: Dict[str, Union[str, QColor]]):
        """Colour per category, as ``QColor`` or any Qt colour string (``"#f59e0b"``, ``"red"``)."""
        self._get_impl_or_raise().set_category_colors({name: QColor(c) for name, c in colors.items()})

    @on_main_thread
    def category_color(self, category: str) -> str:
        return self._get_impl_or_raise().category_color(category).name()

    @property
    @on_main_thread
    def selected_ids(self) -> list:
        return [self._id(row) for row in self._get_impl_or_raise().selected_ids()]

    @on_main_thread
    def select_ids(self, ids: Sequence[Hashable]):
        self._get_impl_or_raise().select_ids([self._row_of[i] for i in ids])

    @property
    @on_main_thread
    def editable(self) -> bool:
        """Let the user edit intervals with the mouse and keyboard (see ``edit_modes``)."""
        return self._get_impl_or_raise().editable

    @editable.setter
    @on_main_thread
    def editable(self, value: bool):
        self._get_impl_or_raise().editable = bool(value)

    @property
    @on_main_thread
    def edit_modes(self) -> set:
        """Allowed gestures among ``{"move", "resize", "change_lane", "create", "delete"}``."""
        return self._get_impl_or_raise().edit_modes

    @edit_modes.setter
    @on_main_thread
    def edit_modes(self, modes):
        self._get_impl_or_raise().edit_modes = set(modes)

    @property
    @on_main_thread
    def snap_to(self):
        """``"edges"``, a step in seconds, or ``None``."""
        return self._get_impl_or_raise().snap_to

    @snap_to.setter
    @on_main_thread
    def snap_to(self, value):
        self._get_impl_or_raise().snap_to = value

    @on_main_thread
    def on_edit(self, callback: Callable[[List[IntervalEdit]], None]):
        """Call ``callback(edits)`` once per gesture (all dragged intervals together),
        on mouse release or arrow-key nudge. Accept by calling :meth:`set_intervals`."""
        self._get_impl_or_raise().intervals_changed.connect(
            lambda payload: callback([IntervalEdit(self._id(row), start, stop, lane)
                                      for row, start, stop, lane in payload]))

    @on_main_thread
    def on_create(self, callback: Callable[[float, float, str], None]):
        """Call ``callback(start, stop, lane)`` when the user draws an interval ("create" mode)."""
        self._get_impl_or_raise().interval_created.connect(callback)

    @on_main_thread
    def on_delete(self, callback: Callable[[list], None]):
        """Call ``callback(ids)`` when the user presses Delete on a selection ("delete" mode)."""
        self._get_impl_or_raise().delete_requested.connect(
            lambda rows: callback([self._id(row) for row in rows]))

    @on_main_thread
    def on_hover(self, callback: Callable[[Optional[Interval]], None]):
        """Call ``callback(interval)`` when the mouse enters an interval, ``callback(None)`` when it leaves."""
        self._get_impl_or_raise().hovered.connect(
            lambda row: callback(self._rows[row] if 0 <= row < len(self._rows) else None))

    @on_main_thread
    def on_selection(self, callback: Callable[[list], None]):
        """Call ``callback(ids)`` whenever the selection changes."""
        self._get_impl_or_raise().selected_intervals_changed.connect(
            lambda rows: callback([self._id(row) for row in rows]))
