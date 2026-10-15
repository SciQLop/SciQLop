"""%%layer cell magic — define and register annotation layers from notebook cells."""
import ast

from IPython.core.magic import needs_local_scope

from SciQLop.user_api.layers._provider import define_layer
from SciQLop.user_api.layers.types import Marker, Span, HLine
from SciQLop.components.sciqlop_logging import getLogger as _getLogger

log = _getLogger(__name__)


def _parse_args(line: str):
    import argparse
    import shlex
    parser = argparse.ArgumentParser(prog="%%layer", add_help=False)
    parser.add_argument("--path", type=str, default=None)
    parser.add_argument("--scope", type=str, default="auto",
                        choices=["auto", "panel", "plot"])
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


@needs_local_scope
def layer_magic(line: str, cell: str, local_ns=None):
    """%%layer cell magic — define an annotation layer from a function in the cell."""
    user_ns = local_ns if local_ns is not None else {}
    _inject_type_names(user_ns)

    args = _parse_args(line)
    func = _extract_function(cell, user_ns)
    func_name = func.__name__

    define_layer(args.path or func_name, func, args.scope)

    log.info(f"Layer '{func_name}' registered — drag from product tree onto a plot")
