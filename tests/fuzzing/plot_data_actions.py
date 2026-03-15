from __future__ import annotations

import time

from PySide6.QtWidgets import QApplication

from tests.fuzzing.actions import ui_action


@ui_action(
    narrate="Plotted static data on panel '{panel}'",
    model_update=lambda model: None,
    verify=lambda main_window, model: True,
)
def plot_static_data(main_window, model, panel, x, y):
    from SciQLop.user_api.plot import plot_panel

    p = plot_panel(panel)
    plot, graph = p.plot(x, y)
    _wait_for_graph_data(graph)
    return {"panel": panel, "plot": plot, "graph": graph}


@ui_action(
    narrate="Plotted spectrogram on panel '{panel}'",
    model_update=lambda model: None,
    verify=lambda main_window, model: True,
)
def plot_static_spectro(main_window, model, panel, x, y, z):
    from SciQLop.user_api.plot import plot_panel

    p = plot_panel(panel)
    plot, graph = p.plot(x, y, z)
    _wait_for_graph_data(graph)
    return {"panel": panel, "plot": plot, "graph": graph}


def _wait_for_graph_data(graph, timeout_s=10.0):
    app = QApplication.instance()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if graph.data is not None and graph.data[0] is not None:
            return
        if app:
            app.processEvents()
        time.sleep(0.001)
