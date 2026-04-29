import inspect
import logging
from typing import (Annotated, Any, Literal, get_args, get_origin,
                    get_type_hints)

from SciQLop.user_api.knobs.marker import Knob
from SciQLopPlots import SciQLopPlotRange

from SciQLop.user_api.knobs.specs import (
    BoolKnob, ChoiceKnob, FloatKnob, IntKnob, KnobSpec, StringKnob,
    TimeRangeKnob, ThresholdKnob,
)

log = logging.getLogger(__name__)

_RESERVED = {"start", "stop", "data"}


def _has_concrete_default(field) -> bool:
    return type(field.default).__name__ != "PydanticUndefinedType"


def _split_annotation(annot):
    if get_origin(annot) is Annotated:
        args = get_args(annot)
        return args[0], [a for a in args[1:] if isinstance(a, Knob)]
    return annot, []


def _normalize_choices(raw) -> tuple[tuple[str, Any], ...]:
    if raw is None:
        return ()
    out = []
    for item in raw:
        if isinstance(item, tuple) and len(item) == 2:
            out.append((str(item[0]), item[1]))
        else:
            out.append((str(item), item))
    return tuple(out)


def _kwargs_meta(marker: Knob | None) -> dict:
    if marker is None:
        return {}
    meta = {"label": marker.label, "unit": marker.unit,
            "description": marker.description, "apply": marker.apply}
    if marker.widget:
        meta["widget"] = marker.widget
    if marker.color:
        meta["color"] = marker.color
    return meta


def _is_time_range(base, marker, default) -> bool:
    if marker is not None and marker.widget == "vspan":
        return True
    if base is SciQLopPlotRange or isinstance(default, SciQLopPlotRange):
        return True
    return False


def _is_threshold(marker) -> bool:
    return marker is not None and marker.widget == "hline"


def _spec_from_kwarg(name: str, annot, default: Any) -> KnobSpec | None:
    base, markers = _split_annotation(annot)
    marker = markers[0] if markers else None

    if _is_time_range(base, marker, default):
        meta = _kwargs_meta(marker)
        color = meta.pop("color", "") or "#3498db"
        return TimeRangeKnob(name=name, default=default or SciQLopPlotRange(0.25, 0.75),
                             color=color, **meta)

    if _is_threshold(marker):
        meta = _kwargs_meta(marker)
        color = meta.pop("color", "") or "#e74c3c"
        return ThresholdKnob(name=name, default=float(default),
                             min=marker.min if marker else None,
                             max=marker.max if marker else None,
                             step=marker.step if marker and marker.step is not None else 0.01,
                             color=color, **meta)

    if get_origin(base) is Literal:
        choices = _normalize_choices(get_args(base))
        return ChoiceKnob(name=name, default=default, choices=choices,
                          **_kwargs_meta(marker))

    if marker is not None and marker.choices:
        return ChoiceKnob(name=name, default=default,
                          choices=_normalize_choices(marker.choices),
                          **_kwargs_meta(marker))

    if base is bool or isinstance(default, bool):
        return BoolKnob(name=name, default=bool(default),
                        **_kwargs_meta(marker))

    if base is int or (base is inspect.Parameter.empty and isinstance(default, int)
                       and not isinstance(default, bool)):
        return IntKnob(name=name, default=int(default),
                       min=marker.min if marker else None,
                       max=marker.max if marker else None,
                       step=marker.step if marker and marker.step is not None else 1,
                       **_kwargs_meta(marker))

    if base is float or (base is inspect.Parameter.empty and isinstance(default, float)):
        return FloatKnob(name=name, default=float(default),
                         min=marker.min if marker else None,
                         max=marker.max if marker else None,
                         step=marker.step if marker and marker.step is not None else 0.01,
                         **_kwargs_meta(marker))

    if base is str or isinstance(default, str):
        return StringKnob(name=name, default=str(default),
                          pattern=marker.pattern if marker else "",
                          **_kwargs_meta(marker))

    return None


def extract_specs_from_callback(callback) -> list[KnobSpec]:
    sig = inspect.signature(callback)
    if any(p.kind in (inspect.Parameter.VAR_POSITIONAL,
                      inspect.Parameter.VAR_KEYWORD)
           for p in sig.parameters.values()):
        log.warning("%r uses *args/**kwargs; knobs disabled",
                    getattr(callback, "__name__", callback))
        return []

    try:
        hints = get_type_hints(callback, include_extras=True)
    except (NameError, TypeError):
        hints = {}

    specs: list[KnobSpec] = []
    for pname, param in sig.parameters.items():
        if pname in _RESERVED:
            continue
        if param.default is inspect.Parameter.empty:
            continue
        annot = hints.get(pname, param.annotation)
        spec = _spec_from_kwarg(pname, annot, param.default)
        if spec is not None:
            specs.append(spec)
    return specs


def _model_field_to_spec(name: str, field) -> KnobSpec | None:
    if not _has_concrete_default(field):
        return None
    annot = field.annotation
    extra = (field.json_schema_extra or {})
    knob_extra = extra.get("knob", {}) if isinstance(extra, dict) else {}
    meta = {"label": knob_extra.get("label", ""),
            "unit": knob_extra.get("unit", ""),
            "description": knob_extra.get("description", ""),
            "apply": knob_extra.get("apply", "live")}

    if get_origin(annot) is Literal:
        choices = _normalize_choices(get_args(annot))
        return ChoiceKnob(name=name, default=field.default, choices=choices, **meta)

    metadata = list(getattr(field, "metadata", []) or [])
    ge = next((m.ge for m in metadata if hasattr(m, "ge")), None)
    le = next((m.le for m in metadata if hasattr(m, "le")), None)
    multiple_of = next((m.multiple_of for m in metadata
                        if hasattr(m, "multiple_of")), None)
    pattern = next((m.pattern for m in metadata if hasattr(m, "pattern")), None)

    if annot is bool:
        return BoolKnob(name=name, default=bool(field.default), **meta)
    if annot is int:
        return IntKnob(name=name, default=int(field.default),
                       min=ge, max=le, step=multiple_of or 1, **meta)
    if annot is float:
        return FloatKnob(name=name, default=float(field.default),
                         min=ge, max=le, step=multiple_of or 0.01, **meta)
    if annot is str:
        return StringKnob(name=name, default=str(field.default),
                          pattern=pattern or "", **meta)
    return None


def extract_specs_from_model(model_cls) -> list[KnobSpec]:
    specs = []
    for name, field in model_cls.model_fields.items():
        spec = _model_field_to_spec(name, field)
        if spec is not None:
            specs.append(spec)
    return specs
