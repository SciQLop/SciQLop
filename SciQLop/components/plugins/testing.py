"""Helpers for plugin authors' own test suites."""
from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc
from SciQLop.components.plugins.backend.loader.provides import provides_drift


def assert_provides_matches(plugin_id: str, plugin_json_path: str) -> None:
    """Fail when plugin.json `provides` differs from what the activated plugin registered."""
    problems = provides_drift(plugin_id, PluginDesc.from_json(plugin_json_path).provides)
    assert not problems, "\n".join(problems)
