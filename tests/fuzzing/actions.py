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
        bundles_map: dict[str, Bundle] = {}

        for action_fn in registry.actions:
            meta: ActionMeta = action_fn._ui_meta
            if meta.target and meta.target not in bundles_map:
                bundles_map[meta.target] = Bundle(meta.target)

        class_dict: dict[str, Any] = {}
        class_dict.update(bundles_map)

        @initialize()
        def _init_model(self):
            self._model = AppModel()
            self._story = Story()

        class_dict["_init_model"] = _init_model

        def teardown(self):
            if self._story.steps:
                last = self._story.steps[-1]
                if last.error is not None:
                    _dump_story(self._story)
            mw = self.__class__.main_window
            for panel_name in list(self._model.panels):
                try:
                    mw.remove_panel(panel_name)
                except Exception:
                    pass
            settle()

        class_dict["teardown"] = teardown

        for action_fn in registry.actions:
            meta: ActionMeta = action_fn._ui_meta
            method_name = action_fn.__name__

            rule_kwargs: dict[str, Any] = {}
            if meta.target:
                rule_kwargs["target"] = bundles_map[meta.target]

            for param_name, bundle_name in (meta.bundles or {}).items():
                rule_kwargs[param_name] = bundles_map[bundle_name]
            for param_name, strategy in (meta.strategies or {}).items():
                rule_kwargs[param_name] = strategy

            def make_rule_method(fn, fn_meta):
                def rule_method(self, **kwargs):
                    mw = self.__class__.main_window

                    try:
                        result = fn(mw, self._model, **kwargs)
                    except Exception as e:
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

                    if isinstance(result, dict):
                        cb_kwargs = {**kwargs, **result, "result": result}
                        narrate_args = {k: str(v) for k, v in result.items()}
                    else:
                        cb_kwargs = {**kwargs, "result": result}
                        narrate_args = {k: str(v) for k, v in kwargs.items()}
                        if result is not None:
                            narrate_args["result"] = str(result)

                    step = Step(
                        action_name=fn.__name__,
                        args=narrate_args,
                        narrate_template=fn_meta.narrate,
                        result=result if not isinstance(result, dict) else None,
                    )
                    self._story.record(step)

                    settle(fn_meta.settle_timeout_ms)

                    model_kwargs = _bind_kwargs(fn_meta.model_update, cb_kwargs)
                    fn_meta.model_update(self._model, **model_kwargs)

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

            # Hypothesis passes `self` (state machine instance), not model
            if meta.precondition:
                user_precond = meta.precondition
                method = precondition(lambda self, _p=user_precond: _p(self._model))(method)

            method = rule(**rule_kwargs)(method)
            class_dict[method_name] = method

        sm_class = type(name, (RuleBasedStateMachine,), class_dict)

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
