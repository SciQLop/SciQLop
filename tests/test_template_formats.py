"""Template file formats are contributions to sciqlop.template_formats (Tier 3 spec §4.1)."""
import json
from pathlib import Path

import pytest

from SciQLop.components.plotting import panel_template
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel
from SciQLop.components.plotting.template_formats import (TEMPLATE_FORMATS, TemplateFormat, file_dialog_filter,
                                                          formats_dialog_filter,
                                                          format_for, template_suffixes)
from SciQLop.core.extensions import owned_by


def _template(name="tf_demo"):
    return PanelTemplate(name=name, plots=[PlotModel(products=[ProductModel(path="speasy//amda//imf",
                                                                            kind="speasy", graph_type="Line",
                                                                            y_axis="y")])])


@pytest.fixture
def plugin_format(qapp):
    with owned_by("tf_demo"):
        TEMPLATE_FORMATS.contribute(TemplateFormat("tf_demo.jsonl", "JSON on one line", (".tpl",),
                                                   loads=json.loads, dumps=json.dumps))
    yield
    TEMPLATE_FORMATS.remove_owner("tf_demo")


def test_the_core_formats_cover_today_s_suffixes():
    assert set(template_suffixes()) >= {".json", ".yaml", ".yml"}
    assert format_for(Path("a.yml")).id == "yaml"
    assert "*.json" in file_dialog_filter() and "*.yml" in file_dialog_filter()


def test_an_unknown_suffix_lists_the_supported_ones():
    with pytest.raises(ValueError, match=r"Unsupported file extension: \.txt.*\.json"):
        format_for(Path("a.txt"))


def test_a_plugin_format_round_trips_a_template(plugin_format, tmp_path):
    path = tmp_path / "demo.tpl"
    _template().to_file(str(path))
    assert json.loads(path.read_text())["name"] == "tf_demo"
    assert PanelTemplate.from_file(str(path)).name == "tf_demo"


def test_templates_in_a_plugin_format_are_listed_until_it_is_withdrawn(plugin_format, monkeypatch, tmp_path):
    monkeypatch.setattr(panel_template, "templates_dir", lambda: tmp_path)
    _template("tf_listed").to_file(str(tmp_path / "tf_listed.tpl"))
    assert "tf_listed" in [t.name for t in panel_template.list_templates()]
    TEMPLATE_FORMATS.remove_owner("tf_demo")
    assert "tf_listed" not in [t.name for t in panel_template.list_templates()]
    assert (tmp_path / "tf_listed.tpl").exists()


def test_an_unknown_suffix_in_the_templates_folder_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(panel_template, "templates_dir", lambda: tmp_path)
    (tmp_path / "notes.txt").write_text("not a template")
    _template("tf_json").to_file(str(tmp_path / "tf_json.json"))
    assert [t.name for t in panel_template.list_templates()] == ["tf_json"]


def test_user_api_load_reads_a_plugin_format_file(plugin_format, tmp_path):
    from SciQLop.user_api import templates
    path = tmp_path / "demo.tpl"
    _template().to_file(str(path))
    assert templates.load(str(path)).name == "tf_demo"


def test_the_export_dialog_filter_has_one_entry_per_format(plugin_format):
    entries = formats_dialog_filter().split(";;")
    assert entries[:2] == ["JSON (*.json)", "YAML (*.yaml *.yml)"]
    assert any(e.endswith("(*.tpl)") for e in entries[2:])


@pytest.mark.parametrize("suffixes", [("tpl",), (".tar.gz",)])
def test_a_suffix_must_be_a_single_dotted_extension(suffixes):
    with pytest.raises(ValueError, match="bad_fmt"):
        TemplateFormat("bad_fmt", "Bad", suffixes, loads=json.loads, dumps=json.dumps)
