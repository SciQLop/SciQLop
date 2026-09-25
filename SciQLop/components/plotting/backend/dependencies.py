import inspect
import logging
import threading
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Any, Callable, Optional, Union, get_args, get_origin, get_type_hints

log = logging.getLogger(__name__)

ProductPath = Union[str, list]
DependencyTarget = Union[ProductPath, object, Callable[[float, float], Any]]


@dataclass(frozen=True, slots=True)
class Depends:
    """Signature marker declaring a virtual-product dependency.

    Used as ``Annotated[SpeasyVariable, Depends(target, pad=...)]``. ``target`` is a
    product path (``"a//b"`` or ``["a", "b"]``), a ``VirtualProduct`` handle, or a
    ``callable(start, stop)``. ``pad`` widens the resolution window symmetrically
    (seconds as ``float`` or ``datetime.timedelta``). Dependencies are always
    resolved in float epoch seconds, regardless of the consuming callback's
    start/stop type."""
    target: DependencyTarget
    pad: Optional[Union[float, timedelta]] = None


@dataclass(frozen=True, slots=True)
class DependsSpec:
    name: str
    target: DependencyTarget
    pad: float  # seconds, 0.0 when unset


def _pad_seconds(pad) -> float:
    if pad is None:
        return 0.0
    if isinstance(pad, timedelta):
        return pad.total_seconds()
    return float(pad)


def depends_marker(annotation) -> Optional[Depends]:
    if get_origin(annotation) is Annotated:
        for extra in get_args(annotation)[1:]:
            if isinstance(extra, Depends):
                return extra
    return None


def extract_dependencies_from_callback(callback) -> list[DependsSpec]:
    try:
        hints = get_type_hints(callback, include_extras=True)
    except (NameError, TypeError) as e:
        # String annotations that fail to resolve would silently lose their
        # Depends markers, surfacing later as a confusing "missing positional
        # argument" at fetch time — warn now, at registration.
        log.warning("cannot resolve type hints for %s (%s); "
                    "string-annotated Depends dependencies will be ignored",
                    getattr(callback, "__qualname__", callback), e)
        hints = {}
    sig = inspect.signature(callback)
    specs = []
    for name, param in sig.parameters.items():
        marker = depends_marker(hints.get(name, param.annotation))
        if marker is not None:
            specs.append(DependsSpec(name=name, target=marker.target,
                                     pad=_pad_seconds(marker.pad)))
    return specs


_MAX_DEPTH = 16  # arbitrary cap; real dependency chains are rarely more than a few deep
_state = threading.local()


def describe_target(target) -> str:
    if isinstance(target, str):
        return target
    if isinstance(target, list):
        return "//".join(target)
    path = getattr(target, "path", None)
    if isinstance(path, str):
        return path
    return getattr(target, "__qualname__", None) or repr(target)


def _without_colour(data):
    """A dependency wants the data; a coloured VP's colour is for its own plot."""
    from SciQLop.user_api.data_types import Colored
    return data.data if isinstance(data, Colored) else data


def _resolve_path(target, start: float, stop: float):
    from SciQLop.core.models import products
    from SciQLop.components.plotting.backend.data_provider import providers
    path = target.split("//") if isinstance(target, str) else list(target)
    node = products.node(path)
    if node is None:
        raise ValueError(f"product not found: {'//'.join(path)}")
    provider = providers.get(node.provider())
    if provider is None:
        raise ValueError(f"no provider for product: {'//'.join(path)}")
    return _without_colour(provider.get_data(node, start, stop))


def resolve_product_path(target, start: float, stop: float):
    """Public entry point: resolve a `//`-path (or list of paths) to provider
    data for [start, stop]. Thin wrapper over the VP dependency resolver,
    without the extra time padding `Depends(pad=...)` applies for VP callbacks."""
    return _resolve_path(target, start, stop)


def _resolve_target(target, start: float, stop: float):
    if isinstance(target, (str, list)):
        return _resolve_path(target, start, stop)
    if callable(target):
        return _without_colour(target(start, stop))
    from SciQLop.user_api.virtual_products import VirtualProduct
    if isinstance(target, VirtualProduct):
        impl = getattr(target, "_impl", None)
        if impl is None:
            raise TypeError(f"VirtualProduct has no resolvable data source: {describe_target(target)}")
        return _without_colour(impl.get_data(None, start, stop))
    raise TypeError(f"unsupported dependency target: {target!r}")


def resolve_dependency(spec, start: float, stop: float):
    depth = getattr(_state, "depth", 0)
    if depth >= _MAX_DEPTH:
        raise RecursionError(
            f"dependency resolution exceeded depth {_MAX_DEPTH} resolving "
            f"{describe_target(spec.target)} — possible dependency cycle")
    _state.depth = depth + 1
    try:
        return _resolve_target(spec.target, start - spec.pad, stop + spec.pad)
    finally:
        _state.depth = depth
