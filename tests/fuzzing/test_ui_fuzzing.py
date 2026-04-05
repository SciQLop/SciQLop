import pytest
from hypothesis.stateful import run_state_machine_as_test

from tests.fuzzing.panel_actions import registry


SciQLopUIFuzzer = registry.build_state_machine(
    name="SciQLopUIFuzzer",
    max_examples=10,
    stateful_step_count=10,
)


@pytest.fixture(scope="module")
def fuzzer_class(main_window, qtbot):
    """Inject live Qt fixtures into the state machine class."""
    SciQLopUIFuzzer.main_window = main_window
    SciQLopUIFuzzer.qtbot = qtbot
    yield SciQLopUIFuzzer


def test_ui_fuzzing(fuzzer_class):
    """Run the stateful UI fuzzer."""
    run_state_machine_as_test(fuzzer_class)
