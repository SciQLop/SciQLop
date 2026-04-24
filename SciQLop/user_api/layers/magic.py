"""%%layer cell magic — define and register annotation layers from notebook cells."""
import ast

from IPython.core.magic import needs_local_scope

from SciQLop.user_api.layers.registry import _registry
from SciQLop.user_api.layers.types import Marker, Span, HLine


def _parse_args(line: str):
    import argparse
    import shlex
    parser = argparse.ArgumentParser(prog="%%layer", add_help=False)
    parser.add_argument("--path", type=str, default=None)
    parser.add_argument("--debug", action="store_true", default=False)
    return parser.parse_args(shlex.split(line))


def _extract_function(cell: str, user_ns: dict) -> callable:
    exec(cell, user_ns)
    tree = ast.parse(cell)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return user_ns[node.name]
    raise ValueError("No function definition found in cell")


def _inject_type_names(user_ns: dict):
    user_ns.setdefault("Marker", Marker)
    user_ns.setdefault("Span", Span)
    user_ns.setdefault("HLine", HLine)


def _get_log():
    from SciQLop.components import sciqlop_logging
    return sciqlop_logging.getLogger(__name__)


def _invoke_on_main_thread(func, *args, **kwargs):
    from SciQLop.user_api.threading import invoke_on_main_thread
    return invoke_on_main_thread(func, *args, **kwargs)


def _register_layer_provider(name, wrapper, path):
    from SciQLop.user_api.layers._provider import LayerProvider, _layer_providers
    existing = _layer_providers.get(name)
    if existing is not None:
        existing._callback = wrapper
        existing.refresh_knob_specs()
        return existing

    def _do():
        return LayerProvider(path, wrapper)

    return _invoke_on_main_thread(_do)


@needs_local_scope
def layer_magic(line: str, cell: str, local_ns=None):
    """%%layer cell magic — define an annotation layer from a function in the cell."""
    user_ns = local_ns if local_ns is not None else {}
    _inject_type_names(user_ns)

    args = _parse_args(line)
    func = _extract_function(cell, user_ns)
    func_name = func.__name__

    entry = _registry.register(func_name, func)

    layer_path = args.path or func_name
    _register_layer_provider(func_name, entry.wrapper, layer_path)

    _get_log().info(f"Layer '{func_name}' registered — drag from product tree onto a plot")

    if args.debug:
        try:
            from SciQLop.user_api.knobs import extract_specs_from_callback
            from SciQLop.user_api.virtual_products.ipywidgets_binding import display_widgets_for_state
            from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
            from IPython.display import display

            specs = extract_specs_from_callback(func)
            if specs:
                state = GraphKnobState(specs)
                box = display_widgets_for_state(state)
                if box is not None:
                    display(box)
        except Exception:
            _get_log().warning("ipywidgets binding failed", exc_info=True)

    return func, args
