import asyncio
from types import SimpleNamespace

import pytest

from SciQLop.components.catalogs import CatalogRegistry
from SciQLop.plugins.sciqlop_cocat import plugin as plugin_module
from SciQLop.plugins.sciqlop_cocat.plugin import builtin_plugin_enabled


def _plugins(**entries):
    return SimpleNamespace(plugins={k: SimpleNamespace(enabled=v) for k, v in entries.items()})


def test_builtin_plugin_enabled():
    assert builtin_plugin_enabled(_plugins()) is False
    assert builtin_plugin_enabled(_plugins(collaborative_catalogs=False)) is False
    assert builtin_plugin_enabled(_plugins(collaborative_catalogs=True)) is True


@pytest.fixture
def loaded(qapp, monkeypatch, tmp_path):
    def load(builtin_enabled):
        monkeypatch.setattr(plugin_module, "CocatRsSettings", lambda: SimpleNamespace(server_url="https://h/"))
        monkeypatch.setattr(plugin_module, "SciQLopPluginsSettings",
                            lambda: _plugins(collaborative_catalogs=builtin_enabled))
        monkeypatch.setattr(plugin_module, "user_data_dir", lambda name: tmp_path / name)
        plugin = plugin_module.load(None)
        made.append(plugin)
        return plugin

    # start() needs SciQLop's loop; a test that checks it patches it again after this
    monkeypatch.setattr(plugin_module.CocatRsProvider, "start", lambda self: None)
    made = []
    yield load
    for plugin in made:
        CatalogRegistry.instance()._forget_for_tests(plugin.provider)


def test_load_registers_provider_by_name(loaded):
    plugin = loaded(False)
    assert CatalogRegistry.instance().provider_by_name("Catalogs (cocat-rs)") is plugin.provider
    assert plugin.provider._author == "SciQLop"
    assert plugin.provider._session.url == "https://h"


@pytest.fixture
def warnings(monkeypatch):
    seen = []
    monkeypatch.setattr(plugin_module, "log", SimpleNamespace(warning=lambda msg, *a: seen.append(msg % a)))
    return seen


def test_warns_when_builtin_enabled(loaded, warnings):
    loaded(True)
    assert len(warnings) == 1 and "Collaborative Catalogs" in warnings[0]


def test_no_warning_when_builtin_disabled(loaded, warnings):
    loaded(False)
    assert warnings == []


def test_close_leaves_joined_rooms(loaded, room):
    plugin = loaded(False)
    plugin.provider.attach_room("r", room)
    asyncio.run(plugin.close())
    assert plugin.provider.catalogs() == [] and plugin.provider._rooms == {}


def test_load_starts_the_provider_once_sciqlop_runs(loaded, monkeypatch, qtbot):
    started = []
    monkeypatch.setattr(plugin_module.CocatRsProvider, "start", lambda self: started.append(self))
    plugin = loaded(False)
    assert started == []  # not during load: SciQLop's loop runs only afterwards
    qtbot.waitUntil(lambda: started == [plugin.provider])


def test_one_provider_keeps_local_projects_apart_from_the_account_caches(loaded, tmp_path):
    provider = loaded(False).provider
    assert provider._cache_dir == tmp_path / "cocat_rs" and provider._local_dir == tmp_path / "cocat_rs_local"
