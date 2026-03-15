# Story-Driven UI Fuzzing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a declarative UI fuzzing framework that generates human-readable failure stories and pseudo-code reproducers, powered by Hypothesis `RuleBasedStateMachine`.

**Architecture:** Actions are plain functions with `@ui_action` decorators carrying narrative templates, model updates, and verification lambdas. An `ActionRegistry` collects them and `build_state_machine()` generates a Hypothesis state machine. After each action, the real app is introspected to verify the model matches.

**Tech Stack:** Python 3, Hypothesis (stateful testing), pytest-qt, PySide6

---

## File Structure

```
tests/fuzzing/
  __init__.py              # empty
  README.md                # contributor docs
  actions.py               # @ui_action decorator, ActionRegistry, build_state_machine, settle()
  model.py                 # AppModel dataclass
  story.py                 # Step, Story (narrative + reproducer rendering)
  introspect.py            # pure query functions against real app
  panel_actions.py         # 3 initial actions: create_panel, remove_panel, zoom_panel (drag_product deferred)
  conftest.py              # test-reports dir setup, story dump on failure
  test_ui_fuzzing.py       # fixture injection + generated state machine test
```

**Key existing files referenced:**
- `SciQLop/user_api/plot/_panel.py` — `create_plot_panel()`, `PlotPanel` wrapper, `time_range` property
- `SciQLop/core/ui/mainwindow.py:286` — `remove_panel()`, `plot_panels()`, `plot_panel(name)`
- `SciQLop/core/__init__.py` — `TimeRange` alias for `SciQLopPlotRange`
- `tests/fixtures.py` — `main_window` fixture (module-scoped)
- `tests/helpers.py` — `drag_and_drop()`, `mouseMove()`
- `pyproject.toml:82-89` — dev dependencies

---

## Chunk 1: Framework Core (story.py, model.py, actions.py)

### Task 1: Add `hypothesis` dev dependency

**Files:**
- Modify: `pyproject.toml:82-89`

- [ ] **Step 1: Add hypothesis to dev dependencies**

In `pyproject.toml`, add `"hypothesis"` to the `dev` list:

```toml
dev = [
    "pytest-runner",
    "pytest",
    "pytest-cov",
    "pytest-qt",
    "hypothesis",
    'pytest-xvfb; platform_system == "Linux"',
]
```

- [ ] **Step 2: Install and verify**

Run: `uv sync`
Run: `uv run python -c "import hypothesis; print(hypothesis.__version__)"`
Expected: prints a version number

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add hypothesis to dev dependencies"
```

---

### Task 2: Build `story.py` — Step and Story

**Files:**
- Create: `tests/fuzzing/__init__.py`
- Create: `tests/fuzzing/story.py`
- Create: `tests/fuzzing/test_story.py`

- [ ] **Step 1: Create `tests/fuzzing/__init__.py`**

Empty file.

- [ ] **Step 2: Write tests for Step and Story**

Create `tests/fuzzing/test_story.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/fuzzing/test_story.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement `story.py`**

Create `tests/fuzzing/story.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import indent
from typing import Any


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


class Story:
    def __init__(self):
        self.steps: list[Step] = []

    def record(self, step: Step):
        self.steps.append(step)

    def narrative(self) -> str:
        return "\n".join(
            f"{i + 1}. {step.narrative}" for i, step in enumerate(self.steps)
        )

    def reproducer(self) -> str:
        lines = [step.as_code() for step in self.steps]
        body = indent("\n".join(lines), "    ") if lines else "    pass"
        return f"def test_reproducer(main_window, qtbot):\n{body}"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/fuzzing/test_story.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add tests/fuzzing/__init__.py tests/fuzzing/story.py tests/fuzzing/test_story.py
git commit -m "feat: add Step and Story for narrative test output"
```

---

### Task 3: Build `model.py` — AppModel

**Files:**
- Create: `tests/fuzzing/model.py`
- Create: `tests/fuzzing/test_model.py`

- [ ] **Step 1: Write tests for AppModel**

Create `tests/fuzzing/test_model.py`:

```python
from tests.fuzzing.model import AppModel


def test_fresh_model_is_empty():
    model = AppModel()
    assert model.panel_count == 0
    assert not model.has_panels
    assert model.products_on == {}


def test_add_panel():
    model = AppModel()
    model.panels.append("Panel-0")
    assert model.panel_count == 1
    assert model.has_panels


def test_products_on_defaults_to_empty_list():
    model = AppModel()
    model.products_on.setdefault("Panel-0", []).append("B_GSE")
    assert model.products_on["Panel-0"] == ["B_GSE"]


def test_remove_panel_cascades():
    model = AppModel()
    model.panels.append("Panel-0")
    model.products_on["Panel-0"] = ["B_GSE", "V_GSE"]
    model.remove_panel("Panel-0")
    assert model.panel_count == 0
    assert "Panel-0" not in model.products_on


def test_reset_clears_everything():
    model = AppModel()
    model.panels.extend(["A", "B"])
    model.products_on["A"] = ["x"]
    model.reset()
    assert model.panel_count == 0
    assert model.products_on == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/fuzzing/test_model.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `model.py`**

Create `tests/fuzzing/model.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppModel:
    panels: list[str] = field(default_factory=list)
    products_on: dict[str, list[str]] = field(default_factory=dict)
    time_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def has_panels(self) -> bool:
        return self.panel_count > 0

    def remove_panel(self, name: str):
        self.panels.remove(name)
        self.products_on.pop(name, None)
        self.time_ranges.pop(name, None)

    def reset(self):
        self.panels.clear()
        self.products_on.clear()
        self.time_ranges.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/fuzzing/test_model.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fuzzing/model.py tests/fuzzing/test_model.py
git commit -m "feat: add AppModel for expected state tracking"
```

---

### Task 4: Build `actions.py` — `@ui_action`, `ActionRegistry`, `settle()`, `build_state_machine()`

This is the most complex piece. It has three sub-parts: the decorator, the registry, and the state machine builder.

**Files:**
- Create: `tests/fuzzing/actions.py`
- Create: `tests/fuzzing/test_actions.py`

- [ ] **Step 1: Write tests for `@ui_action` decorator and `ActionRegistry`**

Create `tests/fuzzing/test_actions.py`:

```python
import inspect

from tests.fuzzing.actions import ui_action, ActionRegistry, settle
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/fuzzing/test_actions.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `actions.py`**

Create `tests/fuzzing/actions.py`:

```python
from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    rule,
    precondition,
    initialize,
)
from hypothesis import settings
from PySide6.QtWidgets import QApplication

from tests.fuzzing.model import AppModel
from tests.fuzzing.story import Step, Story


@dataclass
class ActionMeta:
    narrate: str
    model_update: Callable
    verify: Callable
    precondition: Callable | None = None
    target: str | None = None
    bundles: dict[str, str] | None = None      # param_name -> bundle_name
    strategies: dict[str, Any] | None = None   # param_name -> Hypothesis strategy
    settle_timeout_ms: int = 50


def ui_action(
    *,
    narrate: str,
    model_update: Callable,
    verify: Callable,
    precondition: Callable | None = None,
    target: str | None = None,
    bundles: dict[str, str] | None = None,
    strategies: dict[str, Any] | None = None,
    settle_timeout_ms: int = 50,
):
    meta = ActionMeta(
        narrate=narrate,
        model_update=model_update,
        verify=verify,
        precondition=precondition,
        target=target,
        bundles=bundles,
        strategies=strategies,
        settle_timeout_ms=settle_timeout_ms,
    )

    def decorator(fn):
        fn._ui_meta = meta
        return fn

    return decorator


def settle(timeout_ms: int = 50):
    """Flush Qt event loop until idle."""
    app = QApplication.instance()
    if app is None:
        return
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)


def _bind_kwargs(fn: Callable, kwargs: dict[str, Any]) -> dict[str, Any]:
    params = set(inspect.signature(fn).parameters.keys())
    return {k: v for k, v in kwargs.items() if k in params}


class ActionRegistry:
    def __init__(self):
        self.actions: list[Callable] = []

    def register(self, fn: Callable) -> Callable:
        if not hasattr(fn, "_ui_meta"):
            raise ValueError(f"{fn.__name__} must be decorated with @ui_action")
        self.actions.append(fn)
        return fn

    def build_state_machine(
        self,
        name: str = "UIFuzzTest",
        *,
        max_examples: int = 50,
        stateful_step_count: int = 20,
    ) -> type:
        registry = self
        bundles: dict[str, Bundle] = {}

        # Collect all bundle names referenced by actions
        for action_fn in registry.actions:
            meta: ActionMeta = action_fn._ui_meta
            if meta.target and meta.target not in bundles:
                bundles[meta.target] = Bundle(meta.target)

        # Build class dict with bundles as class attributes
        class_dict: dict[str, Any] = {}
        class_dict.update(bundles)

        def make_init(cls_ref):
            @initialize()
            def _init_model(self):
                self._model = AppModel()
                self._story = Story()
            return _init_model

        class_dict["_init_model"] = make_init(None)

        def make_teardown():
            def teardown(self):
                if self._story.steps:
                    # Check if there was an error in the last step
                    last = self._story.steps[-1]
                    if last.error is not None:
                        _dump_story(self._story)
                # Clean up app state
                mw = self.__class__.main_window
                for panel_name in list(self._model.panels):
                    try:
                        mw.remove_panel(panel_name)
                    except Exception:
                        pass
                settle()
            return teardown

        class_dict["teardown"] = make_teardown()

        # Generate a rule method for each action
        for action_fn in registry.actions:
            meta: ActionMeta = action_fn._ui_meta
            method_name = action_fn.__name__

            # Build rule kwargs for Hypothesis
            rule_kwargs: dict[str, Any] = {}
            if meta.target:
                rule_kwargs["target"] = bundles[meta.target]

            # Inspect action signature for parameters beyond main_window/model.
            # Parameters are matched to bundles or strategies via ActionMeta:
            #   - meta.bundles: dict mapping param_name -> bundle_name
            #   - meta.strategies: dict mapping param_name -> Hypothesis strategy
            for param_name, bundle_name in (meta.bundles or {}).items():
                rule_kwargs[param_name] = bundles[bundle_name]
            for param_name, strategy in (meta.strategies or {}).items():
                rule_kwargs[param_name] = strategy

            def make_rule_method(fn, fn_meta):
                def rule_method(self, **kwargs):
                    mw = self.__class__.main_window

                    # Execute the action
                    try:
                        result = fn(mw, self._model, **kwargs)
                    except Exception as e:
                        # Resolve args for narrative
                        narrate_args = {k: str(v) for k, v in kwargs.items()}
                        step = Step(
                            action_name=fn.__name__,
                            args=narrate_args,
                            narrate_template=fn_meta.narrate,
                            error=e,
                        )
                        self._story.record(step)
                        _dump_story(self._story)
                        raise

                    # Resolve kwargs for callbacks
                    if isinstance(result, dict):
                        cb_kwargs = {**kwargs, **result, "result": result}
                        narrate_args = {k: str(v) for k, v in result.items()}
                    else:
                        cb_kwargs = {**kwargs, "result": result}
                        narrate_args = {k: str(v) for k, v in kwargs.items()}
                        if result is not None:
                            narrate_args["result"] = str(result)

                    # Record the step
                    step = Step(
                        action_name=fn.__name__,
                        args=narrate_args,
                        narrate_template=fn_meta.narrate,
                        result=result if not isinstance(result, dict) else None,
                    )
                    self._story.record(step)

                    # Settle Qt events
                    settle(fn_meta.settle_timeout_ms)

                    # Update model
                    model_kwargs = _bind_kwargs(fn_meta.model_update, cb_kwargs)
                    fn_meta.model_update(self._model, **model_kwargs)

                    # Verify model matches reality
                    verify_kwargs = _bind_kwargs(fn_meta.verify, cb_kwargs)
                    try:
                        ok = fn_meta.verify(mw, self._model, **verify_kwargs)
                        if ok is False:
                            raise AssertionError(
                                f"Verification failed after {fn.__name__}"
                            )
                    except Exception as e:
                        self._story.steps[-1].error = e
                        _dump_story(self._story)
                        raise

                    return result

                return rule_method

            method = make_rule_method(action_fn, meta)
            method.__name__ = method_name

            # Apply @precondition if specified
            # Hypothesis passes `self` (the state machine), not model, so wrap it
            if meta.precondition:
                user_precond = meta.precondition
                method = precondition(lambda self, _p=user_precond: _p(self._model))(method)

            # Apply @rule
            method = rule(**rule_kwargs)(method)

            class_dict[method_name] = method

        # Create the class
        sm_class = type(name, (RuleBasedStateMachine,), class_dict)

        # Apply Hypothesis settings
        sm_class.TestCase.settings = settings(
            max_examples=max_examples,
            stateful_step_count=stateful_step_count,
            deadline=None,
        )

        return sm_class


def _dump_story(story: Story):
    """Print story to stdout and save to test-reports/ if available."""
    import os
    from datetime import datetime

    narrative = story.narrative()
    reproducer = story.reproducer()

    print("\n=== FAILURE STORY ===")
    print(narrative)
    print("\n=== REPRODUCER ===")
    print(reproducer)
    print("=== END ===\n")

    reports_dir = os.environ.get("SCIQLOP_TEST_REPORTS", "test-reports")
    os.makedirs(reports_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(reports_dir, f"story-{timestamp}.txt"), "w") as f:
        f.write(narrative)
    with open(os.path.join(reports_dir, f"story-{timestamp}.py"), "w") as f:
        f.write(reproducer)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/fuzzing/test_actions.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fuzzing/actions.py tests/fuzzing/test_actions.py
git commit -m "feat: add @ui_action decorator, ActionRegistry, and build_state_machine"
```

---

## Chunk 2: Introspection, Panel Actions, and Integration Test

### Task 5: Build `introspect.py` — app state queries

**Files:**
- Create: `tests/fuzzing/introspect.py`

No separate test file — these are trivial delegations to existing APIs that will be tested through the integration test in Task 7.

- [ ] **Step 1: Implement introspection helpers**

Create `tests/fuzzing/introspect.py`:

```python
from __future__ import annotations


def count_panels(main_window) -> int:
    return len(main_window.plot_panels())


def panel_names(main_window) -> list[str]:
    return list(main_window.plot_panels())


def panel_graph_count(main_window, panel_name: str) -> int:
    panel = main_window.plot_panel(panel_name)
    if panel is None:
        return 0
    # Each plot in the panel can have multiple graphs
    graphs = []
    for plot in panel.plots:
        graphs.extend(plot.plottables)
    return len(graphs)


def panel_time_range(main_window, panel_name: str) -> tuple[float, float] | None:
    panel = main_window.plot_panel(panel_name)
    if panel is None:
        return None
    tr = panel.time_range
    return (tr.start(), tr.stop())
```

- [ ] **Step 2: Commit**

```bash
git add tests/fuzzing/introspect.py
git commit -m "feat: add introspection helpers for app state queries"
```

---

### Task 6: Build `panel_actions.py` — initial 3 actions

**Files:**
- Create: `tests/fuzzing/panel_actions.py`

- [ ] **Step 1: Implement the 4 initial actions**

Create `tests/fuzzing/panel_actions.py`:

```python
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
    # panel is a name string drawn from the panels bundle
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
```

**Note on `drag_product`:** The existing `drag_and_drop()` helper is marked xfail in tests — it's unreliable. Start with 3 reliable actions (create, remove, zoom). `drag_product` can be added once DnD simulation is stable. This keeps the initial integration clean.

- [ ] **Step 2: Commit**

```bash
git add tests/fuzzing/panel_actions.py
git commit -m "feat: add initial panel actions (create, remove, zoom)"
```

---

### Task 7: Build `conftest.py` and `test_ui_fuzzing.py` — integration

**Files:**
- Create: `tests/fuzzing/conftest.py`
- Create: `tests/fuzzing/test_ui_fuzzing.py`

- [ ] **Step 1: Create `tests/fuzzing/conftest.py`**

```python
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def fuzzing_reports_dir():
    """Ensure test-reports directory exists for story dumps."""
    reports_dir = os.environ.get("SCIQLOP_TEST_REPORTS", "test-reports")
    os.makedirs(reports_dir, exist_ok=True)
```

- [ ] **Step 2: Create `test_ui_fuzzing.py`**

```python
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
    # Cleanup is handled by state machine teardown


def test_ui_fuzzing(fuzzer_class):
    """Run the stateful UI fuzzer."""
    run_state_machine_as_test(fuzzer_class)
```

- [ ] **Step 3: Run the fuzzer test**

Run: `uv run pytest tests/fuzzing/test_ui_fuzzing.py -v -s`
Expected: PASS (Hypothesis explores action sequences with create/remove/zoom)

If it fails, examine the story output printed to stdout. The narrative should clearly describe what happened. Fix any issues in the actions or introspection helpers.

- [ ] **Step 4: Commit**

```bash
git add tests/fuzzing/conftest.py tests/fuzzing/test_ui_fuzzing.py
git commit -m "feat: add UI fuzzer integration test with Hypothesis state machine"
```

---

### Task 8: Write `README.md` for contributors

**Files:**
- Create: `tests/fuzzing/README.md`

- [ ] **Step 1: Write the README**

Create `tests/fuzzing/README.md`:

```markdown
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
def my_action(main_window, model, panel: str):
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

- [ ] **Step 2: Commit**

```bash
git add tests/fuzzing/README.md
git commit -m "docs: add README for UI fuzzing framework"
```

---

## Chunk 3: CI Integration

### Task 9: Add CI artifact upload for fuzzer stories

**Files:**
- Modify: `.github/workflows/` (the test workflow file)

- [ ] **Step 1: Find the test workflow**

Run: `ls .github/workflows/` to find the CI workflow that runs tests.

- [ ] **Step 2: Add artifact upload step**

After the pytest step, add:

```yaml
- uses: actions/upload-artifact@v4
  if: failure()
  with:
    name: fuzzer-stories
    path: test-reports/
    if-no-files-found: ignore
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/<workflow-file>
git commit -m "ci: upload fuzzer story artifacts on test failure"
```
