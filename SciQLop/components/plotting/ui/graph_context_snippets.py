"""Aggregate-level (panel and plot) Python snippets that reproduce a
SciQLop view.

Per-graph snippets stay in each provider's ``python_snippets`` — those have
provider-specific shapes (Speasy vs EasyProvider) and at least two variants
(SciQLop vs notebook). The aggregate snippets here are simpler: one SciQLop
reproducer, walking graphs in panel order, emitting ``panel.plot_product``
per source-bound graph and noting any non-reproducible ones.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from SciQLopPlots import SciQLopPlot, SciQLopGraphInterface

from SciQLop.core.graph_context import context_of, graph_name


def ordered_plots(panel) -> list:
    """Real ``SciQLopPlot`` widgets in the order ``panel.plots()`` reports —
    ``findChildren`` alone returns Qt insertion order which doesn't match the
    panel's logical layout after templates / re-orderings.
    """
    try:
        ptrs = list(panel.plots())
    except Exception:
        return list(panel.findChildren(SciQLopPlot))
    by_name = {p.objectName(): p for p in panel.findChildren(SciQLopPlot)}
    out = []
    for ptr in ptrs:
        widget = by_name.get(ptr.objectName())
        if widget is not None:
            out.append(widget)
    return out


def _iso_range(panel) -> tuple[str, str]:
    """Live panel time range as ISO strings, with a sane fallback."""
    try:
        r = panel.time_axis_range()
        t0 = datetime.fromtimestamp(float(r.start()), tz=timezone.utc)
        t1 = datetime.fromtimestamp(float(r.stop()), tz=timezone.utc)
        return (t0.replace(microsecond=0).isoformat(),
                t1.replace(microsecond=0).isoformat())
    except Exception:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        return (now - timedelta(days=1)).isoformat(), now.isoformat()


def _product_path_arg(ctx) -> Optional[str]:
    """Return a Python literal for ``plot_product``'s product argument, or
    None if this graph isn't reproducible from a path.
    """
    if ctx.kind == "speasy":
        if ctx.product_path:
            return repr(ctx.product_path)
        if ctx.speasy_id:
            return f'["{ctx.speasy_id}"]'
        return None
    if ctx.kind == "vp":
        if ctx.product_path:
            return repr(ctx.product_path)
        if ctx.vp_path:
            return repr(ctx.vp_path.split("/"))
        return None
    return None


def _plot_product_lines(graphs: Iterable, plot_index: int) -> tuple[list[str], list[str]]:
    """Lines for one plot's graphs + per-skip notes."""
    lines: list[str] = []
    skipped: list[str] = []
    first = True
    for g in graphs:
        ctx = context_of(g)
        if ctx is None:
            skipped.append(f"plot {plot_index} / {graph_name(g)} — no source context")
            continue
        arg = _product_path_arg(ctx)
        if arg is None:
            skipped.append(
                f"plot {plot_index} / {graph_name(g)} — {ctx.kind} graph "
                "(function/static, not reproducible from a snippet)"
            )
            continue
        kw = f", plot_index={plot_index}" if not first else ""
        lines.append(f"panel.plot_product({arg}{kw})")
        if ctx.knobs:
            lines.append(f"#   knobs at capture time: {ctx.knobs!r}")
        first = False
    return lines, skipped


def _header(panel) -> list[str]:
    start_iso, stop_iso = _iso_range(panel)
    return [
        "from datetime import datetime",
        "from SciQLop.user_api.plot import create_plot_panel",
        "from SciQLop.core import TimeRange",
        "",
        f'start = datetime.fromisoformat("{start_iso}")',
        f'stop  = datetime.fromisoformat("{stop_iso}")',
        "",
        "panel = create_plot_panel()",
        "panel.time_range = TimeRange(start.timestamp(), stop.timestamp())",
        "",
    ]


def panel_reproducer_snippet(panel) -> Optional[str]:
    """Reproduce every plot+graph in ``panel`` as one SciQLop script.

    Returns None if the panel has no reproducible graphs (e.g., only static
    data or function plots) — caller should hide the menu entry in that case.
    """
    plots = ordered_plots(panel)
    body: list[str] = []
    all_skipped: list[str] = []
    for i, plot in enumerate(plots):
        graphs = list(plot.findChildren(SciQLopGraphInterface))
        if not graphs:
            continue
        lines, skipped = _plot_product_lines(graphs, plot_index=i)
        body.extend(lines)
        all_skipped.extend(skipped)
    if not body:
        return None
    out = _header(panel) + body
    if all_skipped:
        out.append("")
        out.append("# Not included in this snippet:")
        for s in all_skipped:
            out.append(f"#   - {s}")
    return "\n".join(out) + "\n"


def plot_reproducer_snippet(panel, plot_index: int) -> Optional[str]:
    """Reproduce a single plot (by index) as one SciQLop script."""
    plots = ordered_plots(panel)
    if not (0 <= plot_index < len(plots)):
        return None
    graphs = list(plots[plot_index].findChildren(SciQLopGraphInterface))
    if not graphs:
        return None
    lines, skipped = _plot_product_lines(graphs, plot_index=0)
    if not lines:
        return None
    out = _header(panel) + lines
    if skipped:
        out.append("")
        out.append("# Not included in this snippet:")
        for s in skipped:
            out.append(f"#   - {s}")
    return "\n".join(out) + "\n"
