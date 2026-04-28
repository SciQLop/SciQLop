"""Annotation layers — experimental API for reactive visual overlays on plots.

Layers are functions that return lists of annotations (Marker, Span, HLine)
and are rendered as visual overlays on existing plots.

Two callback shapes are supported:

- **Range-only** (classic): ``f(start, stop, **knobs) -> list[Annotation]``
  Re-evaluated on every time-range change.

- **Data-aware**: ``f(data: Vector, **knobs) -> list[Annotation]``
  Receives the actual graph data. Type-hint the ``data`` parameter with
  ``Scalar``, ``Vector``, ``MultiComponent``, or ``Spectrogram`` to
  automatically select the matching graph on the plot.

.. warning::
    This is an experimental API. It may change or be removed in future versions.
"""
from SciQLop.user_api._annotations import experimental_api
from SciQLop.user_api.layers.types import Marker, Span, HLine, Annotation
from SciQLop.user_api.data_types import Scalar, Vector, MultiComponent, Spectrogram  # noqa: F401
from SciQLop.user_api.layers.registry import _registry

__all__ = [
    "Marker", "Span", "HLine", "Annotation",
    "Scalar", "Vector", "MultiComponent", "Spectrogram",
    "register_layer",
]


@experimental_api()
def register_layer(path: str = None):
    """Decorator to register a function as an annotation layer.

    The decorated function appears in the product tree under Layers/ and
    can be dragged onto any plot.

    Parameters
    ----------
    path : str, optional
        Path in the product tree (under Layers/). Defaults to the function name.

    Examples
    --------
    Range-only (re-evaluated on time-range change)::

        @register_layer("detectors/peaks")
        def find_peaks(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
            ...

    Data-aware (receives graph data, re-evaluated on data change)::

        @register_layer("analysis/threshold")
        def threshold_crossings(data: Vector, level: float = 10.0) -> list[Span]:
            ...
    """
    def decorator(func):
        name = func.__name__
        entry = _registry.register(name, func)
        layer_path = path or name

        from SciQLop.user_api.layers._provider import _layer_providers
        if name not in _layer_providers:
            from SciQLop.user_api.threading import invoke_on_main_thread
            from SciQLop.user_api.layers._provider import LayerProvider
            invoke_on_main_thread(lambda: LayerProvider(layer_path, entry.wrapper))

        return func
    return decorator
