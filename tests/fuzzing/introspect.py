from __future__ import annotations


def count_panels(main_window) -> int:
    return len(main_window.plot_panels())


def panel_names(main_window) -> list[str]:
    return list(main_window.plot_panels())


def panel_graph_count(main_window, panel_name: str) -> int:
    panel = main_window.plot_panel(panel_name)
    if panel is None:
        return 0
    graphs = []
    for plot in panel.plots:
        graphs.extend(plot.plottables)
    return len(graphs)


def panel_time_range(main_window, panel_name: str) -> tuple[float, float] | None:
    panel = main_window.plot_panel(panel_name)
    if panel is None:
        return None
    tr = panel.time_range
    return (tr.start(), tr.stop())
