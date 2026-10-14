import numpy as np

RE = 6371.2


class FakeVariable:
    def __init__(self, values, meta):
        self.time = np.array(["2015-10-16T00:00", "2015-10-16T00:10"], dtype="datetime64[ns]")
        self.values = np.asarray(values, dtype=float)
        self.meta = meta
        self.unit = meta.get("UNITS")


def threedview_meta(frame):
    """The metadata speasy gives a cdpp3dview trajectory (recorded 2026-10-14)."""
    return {"CATDESC": f"position in {frame} frame", "UNITS": "km", "FIELDNAM": "Position"}


def wait_for_data(qtbot, graph):
    qtbot.waitUntil(lambda: graph.data() is not None and graph.data()[0] is not None
                    and len(graph.data()[0]) > 0, timeout=5000)


def proj_of(sp):
    return sp.projection._get_impl_or_raise()


def overlay_text(sub):
    return sub.overlay().text() or ""
