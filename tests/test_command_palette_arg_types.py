from tests.fixtures import *


def test_panel_arg_completions(qtbot, main_window):
    from SciQLop.components.command_palette.arg_types import PanelArg

    arg = PanelArg()
    completions = arg.completions({})
    values = [c.value for c in completions]
    assert "__new__" in values


def test_time_range_arg_presets():
    from SciQLop.components.command_palette.arg_types import TimeRangeArg

    arg = TimeRangeArg()
    completions = arg.completions({})
    displays = [c.display for c in completions]
    assert "Last hour" in displays
    assert "Last day" in displays
