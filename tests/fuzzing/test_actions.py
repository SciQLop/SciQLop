import inspect
import pytest

from tests.fuzzing.actions import ui_action, ActionRegistry, StoryRunner, settle
from tests.fuzzing.model import AppModel


def test_ui_action_stores_metadata():
    @ui_action(
        narrate="Did something",
        model_update=lambda model: None,
        verify=lambda main_window, model: True,
    )
    def my_action(main_window, model):
        return "ok"

    assert my_action._ui_meta.narrate == "Did something"
    assert my_action._ui_meta.precondition is None


def test_ui_action_with_precondition():
    @ui_action(
        narrate="X",
        model_update=lambda model: None,
        verify=lambda main_window, model: True,
        precondition=lambda model: model.has_panels,
    )
    def guarded(main_window, model):
        pass

    assert guarded._ui_meta.precondition is not None
    model = AppModel()
    assert not guarded._ui_meta.precondition(model)
    model.panels.append("P")
    assert guarded._ui_meta.precondition(model)


def test_ui_action_with_target():
    @ui_action(
        target="panels",
        narrate="Created '{result}'",
        model_update=lambda model, result: model.panels.append(result),
        verify=lambda main_window, model: True,
    )
    def create(main_window, model):
        return "Panel-0"

    assert create._ui_meta.target == "panels"


def test_registry_collects_actions():
    registry = ActionRegistry()

    @registry.register
    @ui_action(narrate="A", model_update=lambda model: None, verify=lambda mw, model: True)
    def action_a(main_window, model):
        pass

    @registry.register
    @ui_action(narrate="B", model_update=lambda model: None, verify=lambda mw, model: True)
    def action_b(main_window, model):
        pass

    assert len(registry.actions) == 2
    assert registry.actions[0].__name__ == "action_a"


def test_callback_binding_introspects_signature():
    """model_update receives only the kwargs it declares."""
    received = {}

    def capture_update(model, result):
        received["model"] = model
        received["result"] = result

    @ui_action(
        narrate="",
        model_update=capture_update,
        verify=lambda mw, model: True,
    )
    def act(main_window, model):
        return "val"

    meta = act._ui_meta
    kwargs = {"result": "val", "extra": "ignored"}
    params = set(inspect.signature(meta.model_update).parameters.keys())
    bound = {k: v for k, v in kwargs.items() if k in params}
    meta.model_update(model=AppModel(), **bound)
    assert received["result"] == "val"
    assert "extra" not in received


class _FakeMainWindow:
    """Minimal stub for StoryRunner tests (no Qt needed)."""
    _panels: list[str] = []

    def plot_panels(self):
        return list(self._panels)

    def remove_panel(self, name):
        self._panels.remove(name)


def test_story_runner_records_steps():
    @ui_action(
        target="panels",
        narrate="Created panel '{result}'",
        model_update=lambda model, result: model.panels.append(result),
        verify=lambda main_window, model: True,
    )
    def create(main_window, model):
        return "P1"

    mw = _FakeMainWindow()
    runner = StoryRunner(mw)
    result = runner.run(create)

    assert result == "P1"
    assert runner.model.panels == ["P1"]
    assert len(runner.story.steps) == 1
    assert "P1" in runner.story.steps[0].narrative


def test_story_runner_dumps_on_failure():
    @ui_action(
        narrate="Boom",
        model_update=lambda model: None,
        verify=lambda main_window, model: False,
    )
    def failing(main_window, model):
        return None

    runner = StoryRunner(_FakeMainWindow())
    with pytest.raises(AssertionError, match="Verification failed"):
        runner.run(failing)

    assert len(runner.story.steps) == 1
    assert runner.story.steps[0].error is not None
