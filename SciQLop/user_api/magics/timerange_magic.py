"""Implementation of %timerange line magic and its tab completer."""
import shlex
from datetime import datetime, timezone

from IPython.core.error import UsageError

from SciQLop.user_api.magics.completions import _parse_time


def _panel_names():
    from SciQLop.user_api.gui import get_main_window
    mw = get_main_window()
    return mw.plot_panels() if mw else []


def _print_all_time_ranges():
    for name in _panel_names():
        _print_time_range(name)


def _print_time_range(panel_name: str):
    from SciQLop.user_api.plot import plot_panel as _get_panel
    panel = _get_panel(panel_name)
    if panel is None:
        raise UsageError(f"Panel '{panel_name}' not found")
    tr = panel.time_range
    start = datetime.fromtimestamp(tr.start(), tz=timezone.utc).isoformat()
    stop = datetime.fromtimestamp(tr.stop(), tz=timezone.utc).isoformat()
    print(f"{panel_name}: {start} \u2192 {stop}")


def _set_time_range(start: float, stop: float, panel_name: str):
    from SciQLop.core import TimeRange
    from SciQLop.user_api.plot import plot_panel as _get_panel
    panel = _get_panel(panel_name)
    if panel is None:
        raise UsageError(f"Panel '{panel_name}' not found")
    panel.time_range = TimeRange(start, stop)


def timerange_magic(line: str):
    """Line magic: %timerange [panel] or %timerange <start> <stop> <panel>

    Print or set panel time ranges.
    """
    args = shlex.split(line)
    if len(args) == 0:
        _print_all_time_ranges()
    elif len(args) == 1:
        _print_time_range(args[0])
    elif len(args) == 3:
        _set_time_range(_parse_time(args[0]), _parse_time(args[1]), panel_name=args[2])
    else:
        raise UsageError("Usage: %timerange [panel] or %timerange <start> <stop> <panel>")


