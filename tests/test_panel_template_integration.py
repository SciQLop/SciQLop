import pytest
from SciQLop.components.plotting.panel_template import PanelTemplate, TimeRangeModel, PlotModel, ProductModel


class TestFullRoundTrip:
    def test_save_and_load_template(self, tmp_path, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.core import TimeRange
        panel = TimeSyncPanel("roundtrip", time_range=TimeRange(1737000000.0, 1737086400.0))
        qtbot.addWidget(panel)
        t = PanelTemplate.from_panel(panel)
        path = str(tmp_path / "roundtrip.json")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "roundtrip"
        assert loaded.time_range.start is not None

    def test_save_and_load_yaml_template(self, tmp_path, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.core import TimeRange
        panel = TimeSyncPanel("yaml_rt", time_range=TimeRange(1737000000.0, 1737086400.0))
        qtbot.addWidget(panel)
        t = PanelTemplate.from_panel(panel)
        path = str(tmp_path / "roundtrip.yaml")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "yaml_rt"

    def test_apply_clears_and_sets_range(self, tmp_path, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.core import TimeRange
        panel = TimeSyncPanel("apply_test", time_range=TimeRange(0.0, 1.0))
        qtbot.addWidget(panel)
        t = PanelTemplate(
            name="apply",
            time_range=TimeRangeModel(start="2025-01-15T00:00:00Z", stop="2025-01-16T00:00:00Z"),
            plots=[],
        )
        t.apply(panel)
        assert panel.time_range.start() > 1e9
