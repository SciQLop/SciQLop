from SciQLop.user_api.knobs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)


def _import_ipywidgets():
    try:
        import ipywidgets  # type: ignore
        return ipywidgets
    except Exception:
        return None


def _has_widget_comm() -> bool:
    try:
        from IPython import get_ipython
        ip = get_ipython()
        if ip is None:
            return False
        return getattr(ip, "kernel", None) is not None
    except Exception:
        return False


def _number_widget(spec, slider, text):
    """A slider only when both bounds are known, as in the inspector; otherwise
    a number box, since a slider over ±1e18 cannot pick a usable value. Values
    past a single bound are clamped by the knob state."""
    if spec.min is not None and spec.max is not None:
        return slider(min=spec.min, max=spec.max, step=spec.step, value=spec.default,
                      description=spec.label or spec.name)
    return text(step=spec.step, value=spec.default, description=spec.label or spec.name)


def widget_for_spec(spec: KnobSpec):
    w = _import_ipywidgets()
    if w is None:
        return None
    if isinstance(spec, IntKnob):
        return _number_widget(spec, w.IntSlider, w.IntText)
    if isinstance(spec, FloatKnob):
        return _number_widget(spec, w.FloatSlider, w.FloatText)
    if isinstance(spec, BoolKnob):
        return w.Checkbox(value=spec.default,
                          description=spec.label or spec.name)
    if isinstance(spec, ChoiceKnob):
        return w.Dropdown(options=list(spec.choices), value=spec.default,
                          description=spec.label or spec.name)
    if isinstance(spec, StringKnob):
        return w.Text(value=spec.default,
                      description=spec.label or spec.name)
    return None


def bind_state_to_widgets(state, widgets: dict):
    suppress = {"flag": False}

    def _on_widget(name):
        def _handler(change):
            if suppress["flag"]:
                return
            try:
                state.set_value(name, change.new)
            except Exception:
                pass
        return _handler

    for name, widget in widgets.items():
        widget.observe(_on_widget(name), names="value")

    def _on_state(values):
        suppress["flag"] = True
        try:
            for name, widget in widgets.items():
                if name in values and getattr(widget, "value", None) != values[name]:
                    widget.value = values[name]
        finally:
            suppress["flag"] = False

    state.knobs_changed.connect(_on_state)


def display_widgets_for_state(state):
    """Return an HBox of widgets bound to state, or None if unsupported."""
    w = _import_ipywidgets()
    if w is None:
        return None
    widgets = {}
    for spec in state.specs:
        widget = widget_for_spec(spec)
        if widget is not None:
            widgets[spec.name] = widget
    if not widgets:
        return None
    bind_state_to_widgets(state, widgets)
    return w.HBox(children=tuple(widgets.values()))
