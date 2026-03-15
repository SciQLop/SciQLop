# UI Fuzzing Framework

Declarative, story-driven UI fuzzing for SciQLop using Hypothesis stateful testing.

## How It Works

The fuzzer explores random sequences of user actions (create panel, zoom, remove panel, etc.) and checks that the app state matches expectations after each step. When something fails, it produces:

1. A **human-readable story** of what the user did
2. A **pseudo-code reproducer** you can adapt into a regression test

Hypothesis automatically **shrinks** failing sequences to the minimal steps needed to reproduce the bug.

## Running

```bash
# Run the fuzzer
uv run pytest tests/fuzzing/test_ui_fuzzing.py -v -s

# Run with more examples (slower, better coverage)
uv run pytest tests/fuzzing/test_ui_fuzzing.py -v -s --hypothesis-seed=0
```

Failure stories are saved to `test-reports/` as `.txt` (narrative) and `.py` (reproducer).

## Reading Failure Output

When the fuzzer finds a bug, you'll see output like:

```
=== FAILURE STORY ===
1. Created a new plot panel 'Panel-0'
2. Created a new plot panel 'Panel-1'
3. Zoomed panel 'Panel-0' to time range (1000.0, 2000.0)
4. Removed panel 'Panel-0'
5. Removed panel 'Panel-0' → ERROR: panel not found

=== REPRODUCER ===
def test_reproducer(main_window, qtbot):
    actions.create_panel()
    actions.create_panel()
    actions.zoom_panel(panel='Panel-0', t_start='1000.0', t_stop='2000.0')
    actions.remove_panel(panel='Panel-0')
    actions.remove_panel(panel='Panel-0')
=== END ===
```

## Adding a New Action

1. Write a function in `panel_actions.py` (or a new `*_actions.py` file) with `@ui_action`:

```python
@registry.register
@ui_action(
    precondition=lambda model: ...,        # when is this action valid?
    narrate="Did something to '{panel}'",  # human-readable template
    model_update=lambda model, panel: ..., # update expected state
    verify=lambda main_window, model: ..., # check real app matches
)
def my_action(main_window, model, panel):
    # Qt interaction code here
    ...
```

2. If the action introduces new state, add a field to `AppModel` in `model.py`
3. If you need to query new app state, add a helper to `introspect.py`
4. Register the function with `@registry.register`

That's it — the framework handles wiring it into the Hypothesis state machine.

## Architecture

```
actions.py      — @ui_action decorator, ActionRegistry, build_state_machine()
model.py        — AppModel dataclass (expected state)
story.py        — Step + Story (narrative rendering)
introspect.py   — pure queries against real app state
*_actions.py    — action definitions grouped by domain
conftest.py     — test-reports directory setup
test_*.py       — pytest entry points
```
