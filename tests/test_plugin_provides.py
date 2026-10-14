"""plugin.json provides is a summary; the loader warns when it drifts from what the code registered."""
import json
from unittest.mock import MagicMock

import pytest

from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.components.plugins.backend.loader.provides import provides_drift, registered_by
from SciQLop.core import extensions
from SciQLop.core.extensions import ExtensionPoint
from tests.test_extensions import Kind, clean_registry  # noqa: F401  (fixture)
from tests.test_plugin_activation import _desc, _plugin, fresh  # noqa: F401  (fixture)


@pytest.fixture
def kinds(clean_registry, qapp):  # noqa: F811
    ep = extensions.declare(ExtensionPoint("test.kinds", Kind))
    extensions.declare(ExtensionPoint("vdfp.methods", Kind, owner="vdfp"))
    ep.contribute(Kind("vdfp.slice"), owner="vdfp")
    return ep


def test_registered_by_lists_contributions_and_declared_points(kinds):
    assert registered_by("vdfp") == {"test.kinds": ["vdfp.slice"], "extension_points": ["vdfp.methods"]}


def test_matching_provides_has_no_drift(kinds):
    assert provides_drift("vdfp", {"test.kinds": ["vdfp.slice"], "extension_points": ["vdfp.methods"]}) == []


def test_drift_names_both_directions(kinds):
    assert provides_drift("vdfp", {"test.kinds": ["vdfp.ghost"]}) == [
        "extension_points: registered but not declared in plugin.json: vdfp.methods",
        "test.kinds: declared in plugin.json but not registered: vdfp.ghost",
        "test.kinds: registered but not declared in plugin.json: vdfp.slice",
    ]


def test_assert_helper_fails_on_drift(kinds, tmp_path):
    from SciQLop.components.plugins.testing import assert_provides_matches
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps({"name": "V", "version": "1", "provides": {"test.kinds": ["vdfp.slice"]}}))
    with pytest.raises(AssertionError, match="extension_points: registered but not declared"):
        assert_provides_matches("vdfp", str(path))


ACTIVATE_CONTRIBUTING = """
def activate(ctx):
    ctx.extension_point("vdfp.kinds", str, key=str)
    ctx.contribute("vdfp.kinds", "vdfp.slice")
"""


@pytest.fixture
def plog(monkeypatch):
    """SciQLop's logger is not stdlib logging, so caplog cannot see it; spy on the loader's logger instead."""
    spy = MagicMock()
    monkeypatch.setattr(loader, "log", spy)
    return spy


def _warnings(plog) -> list[str]:
    return [c.args[0] for c in plog.warning.call_args_list]


def _drift_warnings(plog) -> list[str]:
    return [m for m in _warnings(plog) if "not declared in plugin.json" in m or "not registered" in m]


def test_activate_plugin_with_drifting_provides_warns_naming_it(tmp_path, fresh, plog):
    provides = {"vdfp.kinds": ["vdfp.ghost"], "extension_points": ["vdfp.kinds"]}
    plugins = [_plugin(tmp_path, "vdfp", ACTIVATE_CONTRIBUTING, _desc(provides=provides))]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert _drift_warnings(plog) == [
        "Plugin vdfp: vdfp.kinds: declared in plugin.json but not registered: vdfp.ghost",
        "Plugin vdfp: vdfp.kinds: registered but not declared in plugin.json: vdfp.slice",
    ]


def test_contribution_made_in_ready_is_not_flagged(tmp_path, fresh, plog):
    code = """
def activate(ctx):
    ctx.extension_point("vdfp.kinds", str, key=str)

def ready(ctx):
    ctx.contribute("vdfp.kinds", "vdfp.late")
"""
    provides = {"vdfp.kinds": ["vdfp.late"], "extension_points": ["vdfp.kinds"]}
    plugins = [_plugin(tmp_path, "vdfp", code, _desc(provides=provides))]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["vdfp"].status == "active"
    assert _drift_warnings(plog) == []


def test_legacy_load_plugin_is_not_checked(tmp_path, fresh, plog):
    code = "def load(main_window):\n    return None\n"
    plugins = [_plugin(tmp_path, "vdfp", code, _desc(provides={"vdfp.kinds": ["vdfp.slice"]}))]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["vdfp"].status == "active"
    assert _drift_warnings(plog) == []


def test_failing_drift_check_is_logged_and_does_not_abort_loading(tmp_path, fresh, plog, monkeypatch):
    def broken(plugin_id, provides):
        raise RuntimeError("boom")
    monkeypatch.setattr(loader, "provides_drift", broken)
    plugins = [_plugin(tmp_path, "vdfp", ACTIVATE_CONTRIBUTING, _desc(provides={}))]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["vdfp"].status == "active"
    errors = [c.args[0] for c in plog.error.call_args_list]
    assert any("Plugin vdfp" in e and "boom" in e for e in errors)
