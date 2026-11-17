import asyncio
from types import SimpleNamespace

import pytest

from SciQLop.components.catalogs import CatalogRegistry
from SciQLop.plugins.sciqlop_cocat import plugin as plugin_module


@pytest.fixture
def loaded(qapp, monkeypatch, tmp_path):
    def load():
        monkeypatch.setattr(plugin_module, "CocatRsSettings", lambda: SimpleNamespace(server_url="https://h/"))
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
    plugin = loaded()
    # not provider_by_name: the shared test main window loads the plugin too, under the same name
    assert plugin.provider in CatalogRegistry.instance().providers()
    assert plugin.provider.name == "Catalogs (cocat-rs)"
    assert plugin.provider._author == "SciQLop"
    assert plugin.provider._session.url == "https://h"


def test_close_leaves_joined_rooms(loaded, room):
    plugin = loaded()
    plugin.provider.attach_room("r", room)
    asyncio.run(plugin.close())
    assert plugin.provider.catalogs() == [] and plugin.provider._rooms == {}


def test_load_starts_the_provider_once_sciqlop_runs(loaded, monkeypatch, qtbot):
    started = []
    monkeypatch.setattr(plugin_module.CocatRsProvider, "start", lambda self: started.append(self))
    plugin = loaded()
    assert started == []  # not during load: SciQLop's loop runs only afterwards
    qtbot.waitUntil(lambda: started == [plugin.provider])


def test_one_provider_keeps_local_projects_apart_from_the_account_caches(loaded, tmp_path):
    provider = loaded().provider
    assert provider._cache_dir == tmp_path / "cocat_rs" and provider._local_dir == tmp_path / "cocat_rs_local"


def test_the_provider_is_given_the_reader_of_the_tscat_database(loaded):
    from SciQLop.plugins.sciqlop_cocat.tscat_import import read_tscat_database
    assert loaded().provider._read_tscat is read_tscat_database


def test_closing_stops_a_tscat_read_at_once_even_when_nothing_awaits_the_close(loaded, monkeypatch):
    """Without a running loop, SciQLop closes the coroutine a plugin's close() returns, unrun."""
    stopped = []
    monkeypatch.setattr(plugin_module, "stop_reading", lambda: stopped.append(True))
    plugin = loaded()

    closing = plugin.close()

    assert stopped == [True]
    asyncio.run(closing)
