"""Opening a template must fetch each graph once, for the template's range.

GH #143 saw the graphs of a freshly opened template fetch twice."""
import numpy as np

from tests.fixtures import *  # noqa: F401,F403

START = "2025-04-12T00:00:00+00:00"
STOP = "2025-04-13T00:00:00+00:00"


def _recording_vp(path, calls):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    def scalar(start: float, stop: float):
        calls.append((start, stop))
        t = np.linspace(start, stop, 16)
        return t, np.sin(t)
    return create_virtual_product(path, scalar, VirtualProductType.Scalar, labels=["s"])


def _template(product_paths, start=START, stop=STOP, max_zoom_seconds=None):
    from SciQLop.components.plotting.panel_template import (
        PanelTemplate, PlotModel, ProductModel, TimeRangeModel,
    )
    return PanelTemplate(
        name="fetch-count",
        time_range=TimeRangeModel(start=start, stop=stop),
        max_zoom_seconds=max_zoom_seconds,
        plots=[PlotModel(products=[ProductModel(path=p, label=p)]) for p in product_paths],
    )


def test_template_fetches_each_graph_once(qtbot, main_window):
    calls = []
    _recording_vp("template_fetch_probe/a", calls)
    _template(["template_fetch_probe//a"]).create_panel(main_window)
    qtbot.wait(1500)
    assert len(calls) == 1


def test_week_long_template_with_zoom_limit_fetches_each_graph_once(qtbot, main_window):
    calls = []
    _recording_vp("template_fetch_probe/b", calls)
    _recording_vp("template_fetch_probe/c", calls)
    _template(["template_fetch_probe//b", "template_fetch_probe//c"],
              start="2025-04-12T04:04:55.491489+00:00",
              stop="2025-04-19T03:53:50.399686+00:00",
              max_zoom_seconds=604800.0).create_panel(main_window)
    qtbot.wait(1500)
    assert len(calls) == 2
