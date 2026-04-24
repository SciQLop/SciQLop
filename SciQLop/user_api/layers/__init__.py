"""Annotation layers — experimental API for reactive visual overlays on plots.

Layers are functions that return lists of annotations (Marker, Span, HLine)
and are rendered as visual overlays on existing plots. They react to time-range
changes and support tunable knobs.

.. warning::
    This is an experimental API. It may change or be removed in future versions.
"""
from SciQLop.user_api._annotations import experimental_api
from SciQLop.user_api.layers.types import Marker, Span, HLine, Annotation
from SciQLop.user_api.layers.registry import _registry

__all__ = ["Marker", "Span", "HLine", "Annotation", "register_layer"]


@experimental_api()
def register_layer(path: str = None):
    """Decorator to register a function as an annotation layer.

    The decorated function appears in the product tree under Layers/ and
    can be dragged onto any plot.

    Parameters
    ----------
    path : str, optional
        Path in the product tree (under Layers/). Defaults to the function name.

    Example
    -------
    ::

        @register_layer("detectors/peaks")
        def find_peaks(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
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
