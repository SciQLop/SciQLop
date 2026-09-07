"""Loader backstop: don't load a folder plugin incompatible with the host."""
import json
from types import SimpleNamespace

import SciQLop
from SciQLop.components.plugins.backend.loader import loader
from SciQLop.components.plugins.backend.loader.loader import (
    entry_point_host_compatible, plugin_host_compatible,
)


def _make_plugin(folder, name, python_dependencies):
    pdir = folder / name
    pdir.mkdir(parents=True)
    (pdir / "plugin.json").write_text(json.dumps({
        "name": name,
        "version": "1.0.0",
        "description": "x",
        "authors": [{"name": "a", "email": "a@b.c", "organization": "o"}],
        "license": "MIT",
        "python_dependencies": python_dependencies,
    }))
    return pdir


def test_incompatible_plugin_is_gated_out(tmp_path, monkeypatch):
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    _make_plugin(tmp_path, "future_plugin", ["SciQLop>=0.20", "numpy"])
    assert plugin_host_compatible(str(tmp_path), "future_plugin") is False


def test_dev_build_loads_plugin_targeting_its_release(tmp_path, monkeypatch):
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    _make_plugin(tmp_path, "ok_plugin", ["SciQLop>=0.13.0,<0.14.0", "speasy>=1.7"])
    assert plugin_host_compatible(str(tmp_path), "ok_plugin") is True


def test_plugin_without_sciqlop_requirement_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    _make_plugin(tmp_path, "no_req", ["numpy", "matplotlib>=3.8"])
    assert plugin_host_compatible(str(tmp_path), "no_req") is True


def test_missing_plugin_json_is_not_gated(tmp_path):
    (tmp_path / "bare_module").mkdir()
    assert plugin_host_compatible(str(tmp_path), "bare_module") is True


def test_malformed_plugin_json_is_not_gated_here(tmp_path):
    pdir = tmp_path / "broken"
    pdir.mkdir()
    (pdir / "plugin.json").write_text("{ not json")
    assert plugin_host_compatible(str(tmp_path), "broken") is True


def _make_entry_point(name, requires):
    return SimpleNamespace(name=name, dist=SimpleNamespace(requires=requires))


def test_incompatible_entry_point_plugin_is_gated_out(monkeypatch):
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    warnings = []
    monkeypatch.setattr(loader.log, "warning", lambda *a, **k: warnings.append(a))
    ep = _make_entry_point("future_ep_plugin", ["SciQLop>=0.20"])
    assert entry_point_host_compatible(ep) is False
    assert warnings == [(
        "Skipping plugin %r: requires SciQLop %s but host is %s",
        "future_ep_plugin", ">=0.20", "0.13.0.dev0",
    )]


def test_entry_point_plugin_with_no_sciqlop_requirement_loads(monkeypatch):
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    ep = _make_entry_point("no_req_ep_plugin", None)
    assert entry_point_host_compatible(ep) is True


def test_entry_point_without_dist_loads(monkeypatch):
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    ep = SimpleNamespace(name="no_dist_plugin", dist=None)
    assert entry_point_host_compatible(ep) is True


def test_dev_build_loads_entry_point_plugin_targeting_its_release(monkeypatch):
    monkeypatch.setattr(SciQLop, "__version__", "0.13.0.dev0")
    ep = _make_entry_point("dev_ep_plugin", ["SciQLop>=0.13.0,<0.14.0"])
    assert entry_point_host_compatible(ep) is True
