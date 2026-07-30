import functools
import inspect
import warnings

import numpy as np
from enum import Enum
from typing import Callable, List, Optional, Union, Tuple
from datetime import datetime, timezone
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis, VariableAxis
from PySide6.QtGui import QIcon
from SciQLop.core.unique_names import make_simple_incr_name
from SciQLop.core.models import products, ProductsModelNode, ProductsModelNodeType
from SciQLop.core.enums import ParameterType
from SciQLop.components.plotting.backend.data_provider import DataProvider, DataOrder, DataProviderReturnType
from SciQLop.components.plotting.backend.dependencies import (
    depends_marker, describe_target, extract_dependencies_from_callback, resolve_dependency,
)
from SciQLop.core import tracing
from SciQLop.core.istp_hints import istp_metadata_to_hints
from SciQLop.core.plot_hints import PlotHints
from SciQLop.core.speasy_hints import variable_as_istp_meta
from SciQLop.components.theming import register_icon
from SciQLop.components import sciqlop_logging
from inspect import signature

log = sciqlop_logging.getLogger(__name__)

register_icon("Python-logo-notext", QIcon(":/icons/Python-logo-notext.png"))

VirtualProductCallback = Callable[
    [Union[float, datetime, np.datetime64], Union[float, datetime, np.datetime64]], DataProviderReturnType]


def ensure_dt64(x_data):
    if isinstance(x_data, np.ndarray):
        if np.issubdtype(x_data.dtype, np.datetime64):
            return x_data.astype("datetime64[ns]", copy=False)
        if x_data.dtype == np.float64:
            return (x_data * 1e9).astype("datetime64[ns]")
    raise ValueError(
        "can't handle x axis: expected a datetime64 or float64 (epoch seconds) "
        f"numpy array, got {getattr(x_data, 'dtype', type(x_data))}")


class ArgumentsType(Enum):
    Float = 0
    Datetime = 1
    Datetime64 = 2
    Unknown = 3


def _positional_args_types(callback: VirtualProductCallback) -> List[type]:
    try:
        sig = signature(callback, eval_str=True)
    except NameError:
        sig = signature(callback)
    return [
        v.annotation for v in sig.parameters.values()
        if v.default == v.empty and depends_marker(v.annotation) is None
    ]


def _arguments_type(callback: VirtualProductCallback) -> ArgumentsType:
    pos_arg_types = _positional_args_types(callback)
    all_are = lambda types, expected: all(t is expected for t in types)
    if len(pos_arg_types) >= 2:
        if all_are(pos_arg_types[:2], float):
            return ArgumentsType.Float
        if all_are(pos_arg_types[:2], datetime):
            return ArgumentsType.Datetime
        if all_are(pos_arg_types[:2], np.datetime64):
            return ArgumentsType.Datetime64
    return ArgumentsType.Unknown


def _name_callable(callback: VirtualProductCallback) -> str:
    # simple function
    if hasattr(callback, "__name__"):
        return callback.__name__
    # callable object
    elif hasattr(callback, "__class__") and hasattr(callback.__class__, "__name__"):
        return callback.__class__.__name__
    # lambda function
    elif hasattr(callback, "__code__") and hasattr(callback.__code__, "co_name"):
        return f"{callback.__code__.co_name} from {callback.__module__} at {callback.__code__.co_firstlineno}"
    # unknown
    return f"unknown callable {callback}"


def _returns_speasy_variable(callback: VirtualProductCallback):
    return inspect.get_annotations(inspect.unwrap(callback)).get("return") == SpeasyVariable


def _to_datetime(start: float, stop: float) -> Tuple[datetime, datetime]:
    return datetime.fromtimestamp(start, tz=timezone.utc), datetime.fromtimestamp(stop, tz=timezone.utc)


def _to_datetime64(start: float, stop: float) -> Tuple[np.datetime64, np.datetime64]:
    return np.datetime64(int(start * 1e9), "ns"), np.datetime64(int(stop * 1e9), "ns")


def _build_remote_callback(callback: VirtualProductCallback, range_stack: list,
                            knobs_model: Optional[type], knobs_kwarg_name: str) -> Callable:
    """Wrap *callback* for out-of-process execution: apply the same range-type
    conversion and knobs_model shaping that EasyProvider._invoke_callback does
    in-process, so the worker only ever needs to call cb(start, stop, **knobs).

    functools.wraps preserves __module__/__qualname__ so RemoteRegistry's
    plugin_key_for() still groups this product's worker with the rest of its
    plugin instead of with easy_provider itself.
    """
    @functools.wraps(callback)
    def _remote_call(start: float, stop: float, **knobs):
        rng = (start, stop)
        for fn in range_stack:
            rng = fn(rng)
        if knobs_model is not None:
            kwargs = {knobs_kwarg_name: knobs_model(**knobs)}
        else:
            kwargs = dict(knobs)
        return callback(*rng, **kwargs)
    return _remote_call


class EasyProvider(DataProvider):
    def __init__(self, path, callback: VirtualProductCallback, parameter_type: ParameterType, metadata: dict,
                 data_order=DataOrder.Y_FIRST,
                 cacheable=False, debug=False,
                 knobs_model: Optional[type] = None,
                 knobs_kwarg_name: str = "knobs",
                 out_of_process: bool = False,
                 display_name: Optional[str] = None):
        super(EasyProvider, self).__init__(name=make_simple_incr_name(_name_callable(callback)), data_order=data_order,
                                           cacheable=cacheable)
        self._path = path.split('/')
        # The node NAME is the product's identity: `ProductsModel::node(path)`
        # resolves a path by matching it, so it must stay the path leaf. A
        # display name is presentation and is set separately below — swapping
        # the name for it doesn't relabel the product, it moves it, and every
        # path-based plot route (panel.plot, %plot, saved panels) stops
        # finding it.
        product_name = self._path[-1]
        product_path = self._path[:-1]

        # Extract and validate dependencies early, before any side effects
        dependency_specs = extract_dependencies_from_callback(callback)

        # Guard: out_of_process incompatibilities must be checked before products.add_node()
        if out_of_process:
            if debug:
                raise ValueError(
                    f"virtual product '{path}': out_of_process=True is incompatible with "
                    f"debug=True (debug diagnostics require the callback to run in-process)")
            if dependency_specs:
                dep_names = [s.name for s in dependency_specs]
                raise ValueError(
                    f"virtual product '{path}': out_of_process=True does not support "
                    f"Depends() dependencies (found on parameter(s) {dep_names}); "
                    f"resolve dependencies in-process or drop out_of_process")

        metadata = {
            "description": f"Virtual {parameter_type.name} product built from Python function: {self.name}",
            **metadata,
            "stable_id": path,
            **({"remote": "True"} if out_of_process else {}),
        }
        node = ProductsModelNode(product_name, self.name, metadata, ProductsModelNodeType.PARAMETER,
                                 parameter_type, "", None)
        if display_name:
            node.set_display_name(display_name)
        products.add_node(product_path, node)
        self._callback = callback
        self._parameter_type = parameter_type
        self._debug = debug
        self._knobs_model = knobs_model
        self._knobs_kwarg_name = knobs_kwarg_name
        self._knob_specs = self._compute_knob_specs(callback, knobs_model)
        self._dependency_specs = dependency_specs

        stack = []
        arguments_type = _arguments_type(callback)
        match arguments_type:
            case ArgumentsType.Datetime:
                stack.append(lambda rng: _to_datetime(*rng))
            case ArgumentsType.Datetime64:
                stack.append(lambda rng: _to_datetime64(*rng))
            case ArgumentsType.Float:
                pass
            case ArgumentsType.Unknown:
                warnings.warn(f"""Can't determine arguments type for {self.name}, missing type hints, assuming float by default.
Please add type hints to the callback function to avoid this warning:
def {self.name}(start: float, stop: float) -> Optional[SpeasyVariable]:
    ...
            """)
        self._range_stack = stack

        if out_of_process:
            # Guards already checked earlier in __init__, so just register
            from SciQLop.components.plotting.backend.remote.registry import remote_registry
            remote_callback = _build_remote_callback(
                callback, self._range_stack, knobs_model, knobs_kwarg_name)
            arity = 3 if parameter_type == ParameterType.Spectrogram else 2
            remote_registry().register(path, remote_callback, arity)

    @staticmethod
    def _compute_knob_specs(callback, knobs_model):
        from SciQLop.user_api.knobs import (
            extract_specs_from_callback, extract_specs_from_model,
        )
        if knobs_model is not None:
            return extract_specs_from_model(knobs_model)
        return extract_specs_from_callback(callback)

    def _refresh_knob_specs(self):
        self._knob_specs = self._compute_knob_specs(self._callback, self._knobs_model)

    def get_knobs(self, product) -> list:
        return list(self._knob_specs)

    def _apply_range(self, start, stop):
        rng = (start, stop)
        for fn in self._range_stack:
            rng = fn(rng)
        return rng

    def _resolve_dependencies(self, start, stop) -> Optional[dict]:
        """Resolve declared dependencies into callback kwargs.

        Returns the kwargs dict, or ``None`` to signal the VP should yield no
        data: a dependency that resolves to ``None`` raises in debug mode (so the
        author sees it) but is discarded in normal mode (so a missing upstream
        does not crash the plot panel)."""
        out = {}
        for spec in self._dependency_specs:
            try:
                data = resolve_dependency(spec, start, stop)
            except Exception as e:
                raise RuntimeError(
                    f"{self.name}: failed to resolve dependency '{spec.name}' "
                    f"({describe_target(spec.target)}): {e}") from e
            if data is None:
                if self._debug:
                    raise RuntimeError(
                        f"{self.name}: dependency '{spec.name}' "
                        f"({describe_target(spec.target)}) resolved to no data")
                log.debug("%s: discarding result, dependency '%s' (%s) resolved to no data",
                          self.name, spec.name, describe_target(spec.target))
                return None
            out[spec.name] = data
        return out

    def _invoke_callback(self, start, stop, knobs):
        rng = self._apply_range(start, stop)
        if self._knobs_model is not None:
            model = self._knobs_model(**(knobs or {}))
            kwargs = {self._knobs_kwarg_name: model}
        else:
            kwargs = dict(knobs or {})
        n_knobs = len(kwargs)
        deps = self._resolve_dependencies(start, stop)
        if deps is None:
            return None
        kwargs.update(deps)
        with tracing.zone("vp.callback", cat="vp",
                          vp=self.name, n_knobs=n_knobs, n_deps=len(self._dependency_specs),
                          start=float(start), stop=float(stop)):
            if self._debug:
                from SciQLop.user_api.virtual_products.validation import validate_and_call
                result = validate_and_call(self._callback, *rng, None, None, **kwargs)
                for d in result.diagnostics:
                    if d.level == "error":
                        log.error(f"{self.name}: {d.message}")
                    elif d.level == "warning":
                        log.warning(f"{self.name}: {d.message}")
                return result.data
            return self._callback(*rng, **kwargs)

    def get_data(self, product, start: float, stop: float, knobs=None) -> DataProviderReturnType:
        return self._invoke_callback(start, stop, knobs)

    @property
    def path(self):
        return self._path

    def labels(self, node) -> List[str]:
        return node.metadata().get("components", "").split(';')

    def python_snippets(self, ctx, graph=None) -> dict:
        if ctx.kind != "vp" or self._callback is None:
            return {}
        cb = self._callback
        mod_name = getattr(cb, "__module__", None)
        qualname = getattr(cb, "__qualname__", None)
        if not (mod_name and qualname):
            return {}
        from SciQLop.core.graph_context import _is_importable
        from SciQLop.core.snippets import render_snippet, format_product_path
        from datetime import datetime, timedelta, timezone

        rng = None
        if graph is not None:
            try:
                from SciQLop.core.graph_context import graph_time_range
                rng = graph_time_range(graph)
            except Exception:
                rng = None
        if rng is not None:
            t0, t1 = rng
            start_iso = datetime.fromtimestamp(t0, tz=timezone.utc).replace(microsecond=0).isoformat()
            stop_iso = datetime.fromtimestamp(t1, tz=timezone.utc).replace(microsecond=0).isoformat()
        else:
            now = datetime.now(timezone.utc).replace(microsecond=0)
            start_iso, stop_iso = (now - timedelta(days=1)).isoformat(), now.isoformat()

        product_path = format_product_path(ctx.product_path) or format_product_path(self._path)
        template = ("vp_reproducer.j2" if _is_importable(mod_name, qualname, cb)
                    else "vp_reproducer_unimportable.j2")
        snippet = render_snippet(
            template,
            start_iso=start_iso,
            stop_iso=stop_iso,
            module=mod_name,
            qualname=qualname,
            product_path=product_path,
            knobs=repr(ctx.knobs) if ctx.knobs else None,
            knobs_kwarg=self._knobs_kwarg_name,
        )
        return {"Reproduce in SciQLop": snippet}

    def plot_hints_from_variable(self, node, variable) -> PlotHints:
        if not isinstance(variable, SpeasyVariable):
            return PlotHints()
        try:
            meta = variable_as_istp_meta(variable)
            if self._parameter_type == ParameterType.Spectrogram:
                meta.setdefault("DISPLAY_TYPE", "spectrogram")
            return istp_metadata_to_hints(meta)
        except Exception:
            log.debug("plot_hints_from_variable failed for %s", self.name, exc_info=True)
            return PlotHints()

    def extended_metadata(self, ctx) -> dict:
        return {
            "vp_path": "/".join(self._path),
            "callback": {
                "module": getattr(self._callback, "__module__", None),
                "qualname": getattr(self._callback, "__qualname__", None),
            },
            "knobs_schema": (
                self._knobs_model.model_json_schema()
                if self._knobs_model is not None else None
            ),
            "knob_specs": [s.model_dump() if hasattr(s, "model_dump") else s
                           for s in self._knob_specs],
            "dependencies": [
                {"name": s.name, "target": describe_target(s.target), "pad": s.pad}
                for s in self._dependency_specs
            ],
        }


class EasyScalar(EasyProvider):
    def __init__(self, path, get_data_callback: VirtualProductCallback, component_name: str, metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False, debug=False,
                 knobs_model=None, knobs_kwarg_name="knobs", out_of_process: bool = False):
        super().__init__(path=path, callback=get_data_callback, parameter_type=ParameterType.Scalar,
                         metadata={**metadata, "components": component_name},
                         data_order=data_order, cacheable=cacheable, debug=debug,
                         knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name,
                         out_of_process=out_of_process)
        self._columns = [component_name]

    def get_data(self, product, start, stop, knobs=None):
        res = self._invoke_callback(start, stop, knobs)
        if type(res) is SpeasyVariable:
            return res
        elif type(res) is tuple:
            x, y = res
            return SpeasyVariable(axes=[VariableTimeAxis(ensure_dt64(x))],
                                  values=DataContainer(np.ascontiguousarray(y)),
                                  columns=self._columns)
        return None


class EasyVector(EasyProvider):
    def __init__(self, path, get_data_callback: VirtualProductCallback, components_names: List[str], metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False, debug=False,
                 knobs_model=None, knobs_kwarg_name="knobs", out_of_process: bool = False):
        super().__init__(path=path, callback=get_data_callback, parameter_type=ParameterType.Vector,
                         metadata={**metadata, "components": ';'.join(components_names)},
                         data_order=data_order, cacheable=cacheable, debug=debug,
                         knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name,
                         out_of_process=out_of_process)
        self._columns = components_names

    def get_data(self, product, start, stop, knobs=None) -> Optional[DataProviderReturnType]:
        res = self._invoke_callback(start, stop, knobs)
        if type(res) is SpeasyVariable:
            return res
        elif type(res) in (tuple, list) and len(res) == 2:
            x, y = res
            return SpeasyVariable(axes=[VariableTimeAxis(ensure_dt64(x))],
                                  values=DataContainer(np.ascontiguousarray(y)),
                                  columns=self._columns)
        elif type(res) in (tuple, list) and len(res) >= 3:
            return res
        else:
            return None


class EasyMultiComponent(EasyVector):
    def __init__(self, path, get_data_callback: VirtualProductCallback, components_names: List[str], metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False, debug=False,
                 knobs_model=None, knobs_kwarg_name="knobs", out_of_process: bool = False):
        # Skip EasyVector.__init__ intentionally — same logic but with Multicomponents type
        EasyProvider.__init__(self, path=path, callback=get_data_callback,
                              parameter_type=ParameterType.Multicomponents,
                              metadata={**metadata, "components": ';'.join(components_names)},
                              data_order=data_order, cacheable=cacheable, debug=debug,
                              knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name,
                              out_of_process=out_of_process)
        self._columns = components_names


class EasySpectrogram(EasyProvider):
    def __init__(self, path, get_data_callback: VirtualProductCallback, metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False, debug=False,
                 knobs_model=None, knobs_kwarg_name="knobs", out_of_process: bool = False,
                 display_name: Optional[str] = None):
        super().__init__(path=path, callback=get_data_callback,
                         parameter_type=ParameterType.Spectrogram,
                         metadata={**metadata},
                         data_order=data_order,
                         cacheable=cacheable,
                         debug=debug,
                         knobs_model=knobs_model,
                         knobs_kwarg_name=knobs_kwarg_name,
                         out_of_process=out_of_process,
                         display_name=display_name)

    def get_data(self, product, start, stop, knobs=None) -> Optional[DataProviderReturnType]:
        res = self._invoke_callback(start, stop, knobs)
        if type(res) is SpeasyVariable:
            return res
        elif type(res) is tuple:
            x, y, z = res
            return SpeasyVariable(axes=[VariableTimeAxis(ensure_dt64(x)), VariableAxis(np.ascontiguousarray(y))],
                                  values=DataContainer(np.ascontiguousarray(z)))
        else:
            return None
