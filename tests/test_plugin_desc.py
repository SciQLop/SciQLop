"""plugin.json: a minimal file is name + version; new keys are dependencies, optional_dependencies, provides."""
import json

from SciQLop.components.plugins.backend.loader import plugin_desc
from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc


def _write(tmp_path, data):
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_minimal_plugin_json_is_name_and_version(tmp_path):
    desc = PluginDesc.from_json(_write(tmp_path, {"name": "Mini", "version": "0.1.0"}))
    assert (desc.description, desc.authors, desc.license) == ("", [], "")
    assert (desc.dependencies, desc.optional_dependencies, desc.provides) == ([], [], {})


def test_new_keys_are_read(tmp_path):
    desc = PluginDesc.from_json(_write(tmp_path, {
        "name": "Study", "version": "1.0.0", "dependencies": ["vdf>=1.2,<2"],
        "optional_dependencies": ["mars"], "provides": {"sciqlop.scenes.scenes": ["Jupiter"]}}))
    assert desc.dependencies == ["vdf>=1.2,<2"] and desc.optional_dependencies == ["mars"]
    assert desc.provides == {"sciqlop.scenes.scenes": ["Jupiter"]}


def test_old_style_plugin_json_still_validates(tmp_path):
    desc = PluginDesc.from_json(_write(tmp_path, {
        "name": "Old", "version": "1.0", "description": "x",
        "authors": [{"name": "a", "email": "a@b.c", "organization": "o"}], "license": "MIT",
        "python_dependencies": ["numpy"], "dependencies": ["tscat_catalogs"]}))
    assert desc.dependencies == ["tscat_catalogs"]


def test_unknown_keys_are_reported_not_silently_dropped(tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(plugin_desc.log, "warning", lambda *a: warnings.append(a))
    PluginDesc.from_json(_write(tmp_path, {"name": "T", "version": "1", "provide": {}}))
    assert warnings and "provide" in str(warnings[0])


def test_unknown_keys_are_warned_once_per_file(tmp_path, monkeypatch):
    # SciQLop's logger emits a Qt signal, not a stdlib record, so caplog cannot see it.
    warnings = []
    monkeypatch.setattr(plugin_desc.log, "warning", lambda msg, *args: warnings.append(msg % args))
    path = tmp_path / "plugin.json"
    path.write_text('{"name": "x", "version": "1.0.0", "colour": "red"}')
    PluginDesc.from_json(str(path))
    PluginDesc.from_json(str(path))
    assert sum("unknown keys ignored: colour" in w for w in warnings) == 1
