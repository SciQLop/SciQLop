"""Implementation of %plot line magic and its tab completer."""
import shlex
import types

from IPython.core.error import UsageError

from SciQLop.user_api.magics.completions import _complete_products, _complete_panels


def _resolve_product(query: str) -> str:
    """Fuzzy-match a product query, returning the top result's full path."""
    matches = _complete_products(query, max_results=1)
    if not matches:
        raise UsageError(f"No product matching '{query}'")
    return matches[0]


def plot_magic(line: str):
    """Line magic: %plot <product> [panel]

    Plot a product in an existing or new panel.
    Product is fuzzy-matched. Panel names with spaces must be quoted.
    """
    args = shlex.split(line)
    if not args:
        raise UsageError("Usage: %plot <product> [panel]")

    from SciQLopPlots import PlotType

    product_path = _resolve_product(args[0])

    if len(args) > 1:
        panel = plot_panel(args[1])
        if panel is None:
            raise UsageError(f"Panel '{args[1]}' not found")
    else:
        panel = create_plot_panel()

    panel.plot_product(product_path, plot_type=PlotType.TimeSeries)


def complete_plot(completer, event):
    """Tab completer for %plot: product (1st arg), panel (2nd arg)."""
    parts = event.line.split()
    if len(parts) <= 2:
        return _complete_products(event.symbol)
    return [p for p in _complete_panels() if p.startswith(event.symbol)]


def plot_panel(name):
    """Lazy wrapper for SciQLop.user_api.plot.plot_panel."""
    from SciQLop.user_api.plot import plot_panel as _pp
    return _pp(name)


def create_plot_panel():
    """Lazy wrapper for SciQLop.user_api.plot.create_plot_panel."""
    from SciQLop.user_api.plot import create_plot_panel as _cpp
    return _cpp()
