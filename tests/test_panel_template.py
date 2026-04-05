import json
import pytest
from pathlib import Path

from SciQLop.components.plotting.panel_template import (
    PanelTemplate, PlotModel, ProductModel, AxisModel,
    TimeRangeModel, IntervalModel, resolve_product_path,
    templates_dir, list_templates, find_template,
)


def _minimal_template(**overrides):
    defaults = dict(
        name="test",
        time_range=TimeRangeModel(start="2025-01-15T00:00:00Z", stop="2025-01-16T00:00:00Z"),
        plots=[PlotModel(products=[ProductModel(path="amda/imf")])],
    )
    defaults.update(overrides)
    return PanelTemplate(**defaults)


class TestPydanticModels:
    def test_minimal_template_roundtrip(self):
        t = _minimal_template()
        data = json.loads(t.model_dump_json())
        t2 = PanelTemplate.model_validate(data)
        assert t2.name == "test"
        assert len(t2.plots) == 1
        assert t2.plots[0].products[0].path == "amda/imf"

    def test_speasy_proxy_format_is_valid(self):
        raw = {
            "name": "ACE IMF",
            "description": "ACE magnetic field",
            "version": 1,
            "time_range": {"start": "2025-01-15T00:00:00Z", "stop": "2025-01-16T00:00:00Z"},
            "plots": [
                {"products": [{"path": "amda/imf"}], "y_axis": {"log": False}}
            ],
        }
        t = PanelTemplate.model_validate(raw)
        assert t.name == "ACE IMF"
        assert t.plots[0].y_axis.log is False

    def test_defaults(self):
        t = _minimal_template()
        assert t.version == 1
        assert t.description == ""
        assert t.intervals == []
        assert t.plots[0].y_axis.log is False
        assert t.plots[0].z_axis.log is False

    def test_intervals(self):
        t = _minimal_template(intervals=[
            IntervalModel(start="2025-01-15T06:00:00Z", stop="2025-01-15T12:00:00Z",
                          color="rgba(255, 120, 80, 0.12)", label="event1")
        ])
        assert len(t.intervals) == 1
        assert t.intervals[0].label == "event1"


class TestResolveProductPath:
    def test_double_slash_path(self):
        assert resolve_product_path("speasy//amda//b_gse") == ["speasy", "amda", "b_gse"]

    def test_single_slash_legacy(self):
        assert resolve_product_path("amda/imf") == ["speasy", "amda", "imf"]

    def test_no_slash(self):
        assert resolve_product_path("scalar_product") == ["speasy", "scalar_product"]


class TestFileIO:
    def test_save_and_load_json(self, tmp_path):
        t = _minimal_template(name="json_test")
        path = str(tmp_path / "test.json")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "json_test"
        assert loaded.plots[0].products[0].path == "amda/imf"

    def test_save_and_load_yaml(self, tmp_path):
        t = _minimal_template(name="yaml_test")
        path = str(tmp_path / "test.yaml")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "yaml_test"

    def test_save_and_load_yml(self, tmp_path):
        t = _minimal_template(name="yml_test")
        path = str(tmp_path / "test.yml")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "yml_test"

    def test_unknown_extension_raises(self, tmp_path):
        t = _minimal_template()
        with pytest.raises(ValueError, match="extension"):
            t.to_file(str(tmp_path / "test.txt"))

    def test_load_unknown_extension_raises(self, tmp_path):
        (tmp_path / "test.txt").write_text("{}")
        with pytest.raises(ValueError, match="extension"):
            PanelTemplate.from_file(str(tmp_path / "test.txt"))


class TestTemplateDiscovery:
    def test_list_templates_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        assert list_templates() == []

    def test_list_templates_finds_json_and_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="a").to_file(str(tmp_path / "a.json"))
        _minimal_template(name="b").to_file(str(tmp_path / "b.yaml"))
        names = [t.name for t in list_templates()]
        assert "a" in names
        assert "b" in names

    def test_find_template_by_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="target").to_file(str(tmp_path / "target.json"))
        t = find_template("target")
        assert t is not None
        assert t.name == "target"

    def test_find_template_json_priority(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="json_version").to_file(str(tmp_path / "dup.json"))
        _minimal_template(name="yaml_version").to_file(str(tmp_path / "dup.yaml"))
        t = find_template("dup")
        assert t.name == "json_version"

    def test_find_template_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        assert find_template("nonexistent") is None


class TestFromPanelCreatePanel:
    def test_from_panel_empty(self, qtbot):
        """An empty panel produces a template with empty plots list."""
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.core import TimeRange
        panel = TimeSyncPanel("test_panel", time_range=TimeRange(1737000000.0, 1737086400.0))
        qtbot.addWidget(panel)
        t = PanelTemplate.from_panel(panel)
        assert t.name == "test_panel"
        assert t.plots == []
        assert t.time_range.start is not None

    def test_apply_sets_time_range(self, qtbot):
        """apply() should set the panel's time range from the template."""
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.core import TimeRange
        t = _minimal_template(name="apply_test")
        panel = TimeSyncPanel("target", time_range=TimeRange(0.0, 1.0))
        qtbot.addWidget(panel)
        t.apply(panel)
        tr = panel.time_range
        assert tr.start() > 1e9


class TestUserAPI:
    def test_list_templates_api(self, tmp_path, monkeypatch):
        from SciQLop.user_api.templates import list_templates as api_list_templates
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="api_test").to_file(str(tmp_path / "api_test.json"))
        results = api_list_templates()
        assert any(t.name == "api_test" for t in results)

    def test_load_by_name(self, tmp_path, monkeypatch):
        from SciQLop.user_api.templates import load
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="by_name").to_file(str(tmp_path / "by_name.yaml"))
        t = load("by_name")
        assert t.name == "by_name"

    def test_load_by_path(self, tmp_path):
        from SciQLop.user_api.templates import load
        path = str(tmp_path / "direct.json")
        _minimal_template(name="direct").to_file(path)
        t = load(path)
        assert t.name == "direct"


class TestZoomLimitPersistence:
    def test_default_max_zoom_is_none(self):
        t = _minimal_template()
        assert t.max_zoom_seconds is None

    def test_max_zoom_roundtrip_json(self, tmp_path):
        t = _minimal_template(max_zoom_seconds=604800)
        path = str(tmp_path / "zoom.json")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.max_zoom_seconds == 604800

    def test_max_zoom_roundtrip_yaml(self, tmp_path):
        t = _minimal_template(max_zoom_seconds=3600)
        path = str(tmp_path / "zoom.yaml")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.max_zoom_seconds == 3600

    def test_old_template_without_zoom_loads(self, tmp_path):
        raw = {
            "name": "legacy",
            "time_range": {"start": "2025-01-15T00:00:00Z", "stop": "2025-01-16T00:00:00Z"},
            "plots": [{"products": [{"path": "amda/imf"}]}],
        }
        import json
        path = tmp_path / "legacy.json"
        path.write_text(json.dumps(raw))
        t = PanelTemplate.from_file(str(path))
        assert t.max_zoom_seconds is None
