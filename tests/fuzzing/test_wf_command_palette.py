from tests.fuzzing.palette_actions import (
    toggle_palette,
    open_palette_shortcut,
    close_palette_escape,
    palette_new_plot,
)


def test_palette_opens_and_closes(story_runner):
    result = story_runner.run(toggle_palette)
    assert result == "visible"
    palette = story_runner.main_window._command_palette
    assert palette._list.model().rowCount() > 0
    result = story_runner.run(toggle_palette)
    assert result == "hidden"


def test_palette_ctrl_k_and_escape(story_runner, qtbot):
    story_runner.run(open_palette_shortcut, qtbot=qtbot)
    story_runner.run(close_palette_escape, qtbot=qtbot)


def test_palette_creates_plot_panel(story_runner, qtbot):
    story_runner.run(palette_new_plot, qtbot=qtbot)
    palette = story_runner.main_window._command_palette
    assert not palette.isVisible()
