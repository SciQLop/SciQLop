# Story-Driven UI Testing & Fuzzing

Declarative, story-driven UI testing for SciQLop. Two modes of use:

1. **Scripted stories** — hand-written sequences of actions that produce human-readable narratives on failure
2. **Fuzzing** — Hypothesis explores random action sequences and shrinks failures automatically

Both modes share the same `@ui_action` vocabulary, so every action you define benefits both.

## Quick Start: Scripted Stories

Write UI tests as a sequence of declared actions. If any step fails, you get the full narrative of what happened plus a pseudo-code reproducer.

```python
from tests.fuzzing.panel_actions import create_panel, remove_panel, zoom_panel

def test_create_and_navigate(story_runner):
    panel = story_runner.run(create_panel)
    story_runner.run(zoom_panel, panel=panel, t_start=0.0, t_stop=100.0)
    story_runner.run(remove_panel, panel=panel)
```

The `story_runner` fixture (from `conftest.py`) handles model tracking, verification after each step, and cleanup.

## Quick Start: Fuzzing

The fuzzer explores random sequences of actions and checks that the app state matches expectations after each step.

```bash
# Run the fuzzer
uv run pytest tests/fuzzing/test_ui_fuzzing.py -v -s

# Run with more examples
uv run pytest tests/fuzzing/test_ui_fuzzing.py -v -s --hypothesis-seed=0
```

## Reading Failure Output

When a test fails (scripted or fuzzed), you see:

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

Stories are also saved to `test-reports/` as `.txt` (narrative) and `.py` (reproducer).

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
4. Register with `@registry.register` — this wires it into the Hypothesis fuzzer
5. Use in scripted tests via `story_runner.run(my_action, panel=...)`

## Two Usage Modes

### StoryRunner (scripted tests)

```python
from tests.fuzzing.actions import StoryRunner

def test_my_workflow(story_runner):
    # story_runner is a fixture, or create manually:
    # runner = StoryRunner(main_window)
    result = story_runner.run(some_action, arg="value")
    story_runner.run(another_action, thing=result)
```

- Each `run()` call: executes the action → settles Qt events → updates model → verifies app state → records step
- On failure: dumps the full narrative up to the failing step
- Cleanup is automatic (via fixture teardown)

### Hypothesis Fuzzer (exploratory testing)

```python
from tests.fuzzing.panel_actions import registry

SciQLopUIFuzzer = registry.build_state_machine(
    name="SciQLopUIFuzzer",
    max_examples=10,       # number of independent runs
    stateful_step_count=10, # max steps per run
)
```

- Hypothesis picks random valid action sequences based on preconditions and bundles
- Automatically shrinks failures to minimal reproducing sequence
- Same actions, same verification, same narrative output

## Architecture

```
actions.py      — @ui_action decorator, run_action(), StoryRunner, ActionRegistry, build_state_machine()
model.py        — AppModel dataclass (expected state)
story.py        — Step + Story (narrative rendering)
introspect.py   — pure queries against real app state
*_actions.py    — action definitions grouped by domain
conftest.py     — story_runner fixture, test-reports directory setup
test_*.py       — pytest entry points
```
