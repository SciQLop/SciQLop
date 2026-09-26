"""A failing fetch was logged twice: once with the backtrace by
DataProvider._get_data, then again by the graph recording it as last_error."""
from tests.fixtures import *  # noqa: F401,F403


class _Recorder:
    def __init__(self):
        self.errors = []

    def error(self, msg, *args, **kwargs):
        self.errors.append(msg % args if args else msg)

    def __getattr__(self, name):
        return lambda *a, **k: None


def test_a_failing_fetch_is_logged_once_with_its_traceback(main_window, qtbot, monkeypatch):
    from SciQLop.components.plotting.backend import data_provider
    from SciQLop.components.plotting.ui import time_sync_panel
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    provider_log, graph_log = _Recorder(), _Recorder()
    monkeypatch.setattr(data_provider, "log", provider_log)
    monkeypatch.setattr(time_sync_panel, "log", graph_log)

    def failing_vp(start: float, stop: float):
        raise RuntimeError("boom-once")

    vp = create_virtual_product("test_fetch_error_logging/failing_once", failing_vp,
                                VirtualProductType.Scalar, labels=["y"])
    panel = create_plot_panel()
    try:
        panel.plot_product(vp)
        qtbot.waitUntil(lambda: not panel.is_busy(), timeout=5000)
        qtbot.waitUntil(lambda: any("boom-once" in e for e in graph_log.errors), timeout=5000)
        # Each failing fetch is logged by the graph only (the panel may fetch more
        # than once, so count the logging sites, not the lines).
        assert not [e for e in provider_log.errors if "boom-once" in e]
        assert all("Traceback" in e for e in graph_log.errors if "boom-once" in e)
    finally:
        panel.close()
