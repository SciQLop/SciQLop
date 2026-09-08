"""Aggregate-level (panel and plot) Python snippets that reproduce a
SciQLop view, rendered from the shared ``PanelTemplate`` model.

Per-graph snippets stay in each provider's ``python_snippets`` — those have
provider-specific shapes (Speasy vs EasyProvider) and at least two variants
(SciQLop vs notebook). The aggregate snippets here are simpler: one SciQLop
reproducer emitting ``panel.plot_product`` per source-bound product and
noting any non-reproducible ones.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from SciQLop.components.plotting.panel_template import PanelTemplate, ProductModel


def _iso_range(template: PanelTemplate) -> tuple[str, str]:
    if template.time_range is not None:
        return template.time_range.start, template.time_range.stop
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return (now - timedelta(days=1)).isoformat(), now.isoformat()


def _plot_product_lines(products: list[ProductModel], plot_index: int) -> tuple[list[str], list[str]]:
    """Lines for one plot's products + per-skip notes."""
    lines: list[str] = []
    skipped: list[str] = []
    for product in products:
        if product.kind is None:
            skipped.append(f"plot {plot_index} / {product.label} — no source context")
            continue
        if not product.path:
            skipped.append(
                f"plot {plot_index} / {product.label} — {product.kind} graph "
                "(function/static, not reproducible from a snippet)"
            )
            continue
        kw = f", product_inputs={product.knobs!r}" if product.knobs else ""
        kw += f", plot_index={plot_index}" if lines else ""
        lines.append(f'panel.plot_product("{product.path}"{kw})')
    return lines, skipped


def panel_reproducer_snippet(panel) -> Optional[str]:
    """Reproduce every plot+graph in ``panel`` as one SciQLop script.

    Returns None if the panel has no reproducible graphs (e.g., only static
    data or function plots) — caller should hide the menu entry in that case.
    """
    from SciQLop.core.snippets import render_snippet
    template = PanelTemplate.from_panel(panel)
    plot_lines: list[str] = []
    skipped: list[str] = []
    for i, plot in enumerate(template.plots):
        lines, plot_skipped = _plot_product_lines(plot.products, plot_index=i)
        plot_lines.extend(lines)
        skipped.extend(plot_skipped)
    if not plot_lines:
        return None
    start_iso, stop_iso = _iso_range(template)
    return render_snippet(
        "panel_reproducer.j2",
        start_iso=start_iso, stop_iso=stop_iso,
        plot_lines=plot_lines, skipped=skipped,
    )


def plot_reproducer_snippet(panel, plot_index: int) -> Optional[str]:
    """Reproduce a single plot (by index) as one SciQLop script."""
    from SciQLop.core.snippets import render_snippet
    template = PanelTemplate.from_panel(panel)
    if not (0 <= plot_index < len(template.plots)):
        return None
    lines, skipped = _plot_product_lines(template.plots[plot_index].products, plot_index=0)
    if not lines:
        return None
    start_iso, stop_iso = _iso_range(template)
    return render_snippet(
        "plot_reproducer.j2",
        start_iso=start_iso, stop_iso=stop_iso,
        plot_lines=lines, skipped=skipped,
    )
