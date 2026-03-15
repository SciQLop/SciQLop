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

### Action Declaration

Each user action is a function decorated with `@ui_action`:

```python
@ui_action(
    narrate="Created a new plot panel '{result.name}'",
    model_update=lambda model, result: model.panels.append(result.name),
    verify=lambda app, model: count_panels(app) == len(model.panels),
)
def create_panel(app, model) -> PanelRef:
    panel = create_plot_panel()
    return PanelRef(name=panel.objectName(), widget=panel)

@ui_action(
    precondition=lambda model: len(model.panels) > 0,
    narrate="Dragged product '{product}' onto panel '{panel.name}'",
    model_update=lambda model, panel, product: model.products_on[panel.name].append(product),
    verify=lambda app, model, panel: len(panel_graphs(app, panel)) == len(model.products_on[panel.name]),
)
def drag_product(app, model, panel: FromBundle("panels"), product: FromProducts()):
    do_drag(product_tree_item(product), panel.widget)
```

Key properties:
- `narrate`: format string interpolated with action args and result
- `model_update`: lambda/function that mutates the model after the action
- `verify`: lambda/function that asserts model matches real app state (the introspection layer)
- `precondition`: gates when the action is available (drives the state graph)
- Type annotations like `FromBundle("panels")` tell Hypothesis how to draw values
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

On failure:
- Human narrative printed to stdout (pytest captures it)
- `.txt` narrative + `.py` reproducer saved to `test-reports/`

### Glue: Decorator to RuleBasedStateMachine

`@ui_action` collects metadata at definition time. An `ActionRegistry` accumulates actions and `build_state_machine()` generates the Hypothesis `RuleBasedStateMachine`:

```python
actions = ActionRegistry()

@actions.register
@ui_action(narrate="...", ...)
def create_panel(app, model): ...

SciQLopUITest = actions.build_state_machine(
    name="SciQLopUITest",
    app_fixture="main_window",
)
```

`build_state_machine` wiring:
- Each action becomes a `@rule` method
- `precondition` lambdas become `@precondition` decorators
- `FromBundle(...)` annotations become Hypothesis `Bundle` draws
- Before each rule: execute action, record `Step` in `Story`, run `model_update`
- After each rule: run `verify` (model vs real app)
- On teardown: dump the `Story` regardless of success/failure

### Introspection Helpers

Pure query functions against the real app, used by `verify` lambdas:

```python
# tests/fuzzing/introspect.py
def count_panels(app) -> int: ...
def panel_names(app) -> list[str]: ...
def panel_graphs(app, panel_ref) -> list: ...
def catalog_names(app) -> list[str]: ...
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

Stories are always written to `test-reports/`. CI uploads them as artifacts on failure.

## File Layout

```
tests/
  fuzzing/
    __init__.py
    actions.py          # @ui_action decorator, ActionRegistry, build_state_machine
    model.py            # AppModel dataclass
    story.py            # Step, Story (narrative + reproducer rendering)
    introspect.py       # pure query functions against real app
    panel_actions.py    # create_panel, remove_panel, zoom_panel, drag_product
    test_ui_fuzzing.py  # generated state machine + TestCase
  conftest.py           # story dump hook + test-reports dir setup
```

## Initial Action Vocabulary

Four actions to prove the architecture:

| Action | Precondition | Model Update | Verify |
|--------|-------------|--------------|--------|
| `create_panel` | none | append panel name | panel count matches |
| `remove_panel` | has panels | remove panel name | panel count matches |
| `drag_product` | has panels | append product to panel | graph count matches |
| `zoom_panel` | has panels | update time range | time range matches |

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
