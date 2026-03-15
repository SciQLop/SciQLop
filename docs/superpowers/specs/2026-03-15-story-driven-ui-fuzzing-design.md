# Story-Driven UI Fuzzing

## Problem

SciQLop's UI integration tests are low-level Qt widget manipulations (`qtbot.mouseClick`, `keyClicks`, polling loops). When a test fails, the output is an assertion error with a line number — no context about what the "user" was doing. There's no fuzzing capability, and no way to automatically explore the space of user interactions to find bugs.

## Goals

1. **Human-readable failure narratives** — when a test (or fuzzer run) fails, produce a numbered story of what the user did
2. **Auto-generated reproducer scripts** — the story also renders as a copy-pasteable pytest function
3. **Fuzzer-driven exploration** — Hypothesis `RuleBasedStateMachine` walks a graph of valid actions, with automatic shrinking to minimal failing sequences
4. **Model-based verification** — a lightweight state model tracks expected app state; after each action, introspect the real app and assert the model matches (catches logic bugs, not just crashes)
5. **Declarative extensibility** — adding a new action = one decorated function with a narrate string, model update, and verify step

## Architecture

### Qt Event Loop Integration

Hypothesis's `RuleBasedStateMachine` runs rules synchronously. Qt requires event loop processing between actions for widget layout, signal delivery, and async data loading. This is handled by:

1. **Event flushing after every rule**: the state machine calls `QApplication.processEvents()` after each action, inside a `settle()` helper that loops `processEvents()` with a short polling interval (1ms) until no new events are posted within a small window (e.g., 50ms of idle).
2. **Async data settling**: actions that trigger data loading (e.g., `drag_product`) include a `settle_timeout_ms` parameter. The post-action settle loop polls with `processEvents()` up to that timeout.
3. **Hypothesis settings**: the generated test uses `@settings(deadline=None, max_examples=50, stateful_step_count=20)` because Qt operations are inherently slow. These defaults are configurable via `build_state_machine()`.

### Fixture Injection

`RuleBasedStateMachine` is instantiated by Hypothesis, not pytest, so fixtures aren't injected normally. The solution:

```python
# test_ui_fuzzing.py
@pytest.fixture(scope="module")
def fuzzer_state_machine(main_window, qtbot):
    """Bind live app fixtures to the state machine class."""
    SciQLopUITest.main_window = main_window
    SciQLopUITest.qtbot = qtbot
    return SciQLopUITest

def test_ui_fuzzing(fuzzer_state_machine):
    run_state_machine_as_test(fuzzer_state_machine)
```

The state machine accesses `self.main_window` and `self.qtbot` as class attributes set before Hypothesis runs.

### Test Isolation

Hypothesis runs multiple state machine instances per test invocation. The `teardown()` method cleans up all state created during that execution (removes panels, clears catalogs) to prevent leakage between runs. The model's own state provides the cleanup list — every panel in `model.panels` gets removed.

### Action Declaration

Each user action is a function decorated with `@ui_action`. All callbacks (`model_update`, `verify`) receive the same signature: `(model, **action_kwargs)` where `action_kwargs` includes all named action parameters plus `result` (the action's return value). The decorator introspects the signature once at registration time and binds the right subset of kwargs to each callback.

```python
@ui_action(
    target="panels",
    narrate="Created a new plot panel '{result.name}'",
    model_update=lambda model, result: model.panels.append(result.name),
    verify=lambda main_window, model: count_panels(main_window) == len(model.panels),
)
def create_panel(main_window, model) -> PanelRef:
    panel = create_plot_panel()
    return PanelRef(name=panel.objectName(), widget=panel)

@ui_action(
    precondition=lambda model: len(model.panels) > 0,
    narrate="Dragged product '{product_name}' onto panel '{panel_name}'",
    model_update=lambda model, panel_name, product_name: model.products_on[panel_name].append(product_name),
    verify=lambda main_window, model, panel_name: (
        len(panel_graphs(main_window, panel_name)) == len(model.products_on[panel_name])
    ),
)
def drag_product(main_window, model, panel: bundles.panels, product: st.sampled_from(PRODUCTS)):
    do_drag(product_tree_item(product), panel.widget)
    return {"panel_name": panel.name, "product_name": product}
```

Key properties:
- `narrate`: format string interpolated with action kwargs (all values are pre-resolved to strings/primitives by the decorator before formatting — no `.name` access in templates)
- `model_update`: called with `(model, **relevant_kwargs)` — signature introspection binds only the parameters the lambda declares
- `verify`: called with `(main_window, model, **relevant_kwargs)` — same introspection-based binding
- `precondition`: gates when the action is available (drives the state graph)
- Action parameters use standard Hypothesis strategies and `Bundle` references directly (e.g., `bundles.panels`, `st.sampled_from(...)`) — no custom `FromBundle` wrapper
- The function body contains only the raw Qt interaction code

### App Model

A simple dataclass tracking expected state — no simulation, just enough for preconditions and verification:

```python
@dataclass
class AppModel:
    panels: list[str] = field(default_factory=list)
    products_on: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    catalogs: list[str] = field(default_factory=list)

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def has_panels(self) -> bool:
        return self.panel_count > 0
```

Grows organically — add a field when a new action touches a new aspect of the app.

### Narrative & Reproducer System

Every action execution is recorded as a `Step`:

```python
@dataclass
class Step:
    action_name: str
    args: dict[str, str]
    narrate_template: str
    result: Any = None
    error: Exception | None = None

    @property
    def narrative(self) -> str:
        return self.narrate_template.format(**self.args, result=self.result)

    def as_code(self) -> str:
        args_str = ", ".join(f"{k}={v!r}" for k, v in self.args.items())
        return f"actions.{self.action_name}({args_str})"
```

A `Story` collects steps and renders both outputs:

```python
class Story:
    steps: list[Step]

    def narrative(self) -> str:
        return "\n".join(
            f"{i+1}. {step.narrative}" for i, step in enumerate(self.steps)
        )

    def reproducer(self) -> str:
        lines = [step.as_code() for step in self.steps]
        return "def test_reproducer(app, qtbot):\n" + indent("\n".join(lines))
```

The `narrate_template` is pre-interpolated by the decorator using resolved primitive values, so `Step.args` values are always strings — no object attribute access in templates.

The reproducer renders human-guidance pseudo-code, not directly runnable scripts. Each line maps to a named action with its resolved arguments, making it straightforward to manually reconstruct a test from the output.

On failure only:
- Human narrative printed to stdout (pytest captures it)
- `.txt` narrative + `.py` reproducer saved to `test-reports/`

Stories are kept in memory during the run and only dumped to disk on failure. No files are written for passing runs.

### Glue: Decorator to RuleBasedStateMachine

`@ui_action` collects metadata at definition time. An `ActionRegistry` accumulates actions and `build_state_machine()` generates the Hypothesis `RuleBasedStateMachine`:

```python
actions = ActionRegistry()

@actions.register
@ui_action(narrate="...", ...)
def create_panel(main_window, model): ...

SciQLopUITest = actions.build_state_machine(
    name="SciQLopUITest",
    app_fixture="main_window",
)
```

`build_state_machine` wiring:
- Each action becomes a `@rule` method
- `precondition` lambdas become `@precondition` decorators
- Bundle mechanics: `build_state_machine()` declares `Bundle` class attributes (e.g., `panels = Bundle("panels")`) on the generated class. Actions that produce objects (e.g., `create_panel`) are wired as `@rule(target=panels)`. Actions that consume them (e.g., `drag_product`) are wired as `@rule(panel=panels)`. The decorator detects this from the action's type annotations: `panel: bundles.panels` maps to `panels` bundle draw, and a `target="panels"` kwarg on `@ui_action` maps to `@rule(target=panels)`
- Before each rule: execute action, record `Step` in `Story`, run `model_update`
- After each rule: run `verify` (model vs real app)
- On teardown: dump the `Story` on failure only; clean up all model-tracked state (panels, products) for isolation between runs

### Introspection Helpers

Pure query functions against the real app, used by `verify` lambdas:

```python
# tests/fuzzing/introspect.py
def count_panels(main_window) -> int: ...
def panel_names(main_window) -> list[str]: ...
def panel_graphs(main_window, panel_ref) -> list: ...
def catalog_names(main_window) -> list[str]: ...
```

No side effects. Add helpers as you add action types.

### CI Integration

```yaml
- uses: actions/upload-artifact@v4
  if: failure()
  with:
    name: fuzzer-stories
    path: test-reports/
```

Story files are only written on failure. CI uploads `test-reports/` as artifacts when tests fail.

## File Layout

```
tests/
  fuzzing/
    __init__.py
    README.md           # human-facing docs: how it works, how to extend, how to read output
    actions.py          # @ui_action decorator, ActionRegistry, build_state_machine
    model.py            # AppModel dataclass
    story.py            # Step, Story (narrative + reproducer rendering)
    introspect.py       # pure query functions against real app
    panel_actions.py    # create_panel, remove_panel, zoom_panel, drag_product
    test_ui_fuzzing.py  # generated state machine + TestCase
    conftest.py         # story dump hook + test-reports dir setup (scoped to fuzzing/)
```

## Initial Action Vocabulary

Four actions to prove the architecture:

| Action | Precondition | Model Update | Verify |
|--------|-------------|--------------|--------|
| `create_panel` | none | append panel name | panel count matches |
| `remove_panel` | has panels | remove panel name + clean up `products_on[name]` | panel count matches (uses `main_window.remove_panel()` internal API — no public user API exists yet) |
| `drag_product` | has panels | append product to panel | graph count matches |
| `zoom_panel` | has panels | update time range | time range matches |

## Hypothesis Configuration

The generated test uses:
```python
@settings(deadline=None, max_examples=50, stateful_step_count=20)
```
- `deadline=None`: Qt operations are inherently slow and would hit Hypothesis's default 200ms deadline
- `max_examples` / `stateful_step_count`: configurable via `build_state_machine()` kwargs

## Documentation

A `README.md` in `tests/fuzzing/` explains the framework for contributors: how it works, how to add new actions, how to read failure output, and how to run the fuzzer locally. This is the primary human-facing documentation for the framework.

## Dependencies

- `hypothesis` (new dev dependency)
- `pytest-qt` (existing)
- `pytest-xvfb` (existing)

## Out of Scope (for now)

- Catalog actions (add when architecture is proven)
- Command palette actions
- Jupyter kernel interactions
- Multi-window scenarios
- Parallel/concurrent action sequences
