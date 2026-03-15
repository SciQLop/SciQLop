from __future__ import annotations

from hypothesis import strategies as st

from tests.fuzzing.actions import ui_action, ActionRegistry
from tests.fuzzing.introspect import count_panels, panel_time_range

from SciQLop.user_api.plot import create_plot_panel


registry = ActionRegistry()


@registry.register
@ui_action(
    target="panels",
    narrate="Created a new plot panel '{result}'",
    model_update=lambda model, result: model.panels.append(result),
    verify=lambda main_window, model: count_panels(main_window) == len(model.panels),
)
def create_panel(main_window, model):
    panel = create_plot_panel()
    # Use ._impl.name to match what main_window.plot_panels() returns
    return panel._impl.name


@registry.register
@ui_action(
    precondition=lambda model: model.has_panels,
    bundles={"panel": "panels"},
    narrate="Removed panel '{panel}'",
    model_update=lambda model, panel: model.remove_panel(panel),
    verify=lambda main_window, model: count_panels(main_window) == len(model.panels),
)
def remove_panel(main_window, model, panel):
    main_window.remove_panel(panel)


@registry.register
@ui_action(
    precondition=lambda model: model.has_panels,
    bundles={"panel": "panels"},
    strategies={
        "t_start": st.floats(min_value=0, max_value=1e9, allow_nan=False),
        "t_stop": st.floats(min_value=0, max_value=1e9, allow_nan=False),
    },
    narrate="Zoomed panel '{panel}' to time range ({t_start}, {t_stop})",
    model_update=lambda model, panel, t_start, t_stop: model.time_ranges.__setitem__(
        panel, (t_start, t_stop)
    ),
    verify=lambda main_window, model, panel, t_start, t_stop: (
        _time_range_close(panel_time_range(main_window, panel), (t_start, t_stop))
    ),
    settle_timeout_ms=200,
)
def zoom_panel(main_window, model, panel, t_start, t_stop):
    from SciQLop.core import TimeRange

    p = main_window.plot_panel(panel)
    if p is not None:
        p.set_time_axis_range(TimeRange(t_start, t_stop))
    return {"panel": panel, "t_start": t_start, "t_stop": t_stop}


def _time_range_close(actual, expected, tol=1.0):
    if actual is None:
        return False
    return abs(actual[0] - expected[0]) < tol and abs(actual[1] - expected[1]) < tol
