from tests.fuzzing.story import Step, Story


def test_step_narrative_formats_args():
    step = Step(
        action_name="create_panel",
        args={"panel_name": "Panel-0"},
        narrate_template="Created panel '{panel_name}'",
    )
    assert step.narrative == "Created panel 'Panel-0'"


def test_step_narrative_with_result():
    step = Step(
        action_name="create_panel",
        args={},
        narrate_template="Created panel '{result}'",
        result="Panel-0",
    )
    assert step.narrative == "Created panel 'Panel-0'"


def test_step_as_code():
    step = Step(
        action_name="create_panel",
        args={"panel_name": "Panel-0"},
        narrate_template="",
    )
    assert step.as_code() == "actions.create_panel(panel_name='Panel-0')"


def test_story_narrative_numbers_steps():
    story = Story()
    story.record(Step("a", {}, "Did A"))
    story.record(Step("b", {"x": "1"}, "Did B with {x}"))
    lines = story.narrative().split("\n")
    assert lines[0] == "1. Did A"
    assert lines[1] == "2. Did B with 1"


def test_story_reproducer():
    story = Story()
    story.record(Step("create_panel", {}, ""))
    story.record(Step("zoom", {"t": "42"}, ""))
    code = story.reproducer()
    assert "def test_reproducer(main_window, qtbot):" in code
    assert "actions.create_panel()" in code
    assert "actions.zoom(t='42')" in code


def test_empty_story():
    story = Story()
    assert story.narrative() == ""
    assert "def test_reproducer" in story.reproducer()
