"""The tscat catalogues plugin is the old catalogue system: kept as a fallback, off for a new user,
and the Plugins settings say so."""
import os
from types import SimpleNamespace

from SciQLop.components.plugins.backend.loader import loader
from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc
from SciQLop.components.plugins.backend.settings import PluginConfig

NAME = "tscat_catalogs"


def _enabled(plugins: dict) -> list[str]:
    settings = SimpleNamespace(plugins=plugins, extra_plugins_folders=[])
    return [name for _, name in loader._enabled_plugins(settings, {})]


def test_it_still_ships():
    assert NAME in loader.list_plugins(loader._bundled_plugins_dir())


def test_it_is_off_for_someone_who_never_had_it():
    plugins = {}
    assert NAME not in _enabled(plugins)
    assert plugins[NAME].enabled is False


def test_it_stays_on_for_someone_who_had_it_on():
    assert NAME in _enabled({NAME: PluginConfig(enabled=True)})


def test_the_settings_say_it_is_the_old_system_and_does_not_sync():
    described = PluginDesc.from_json(os.path.join(loader._bundled_plugins_dir(), NAME, "plugin.json")).description
    assert described.startswith("Old catalogue system, kept only as a fallback")
    assert "not synced with the new catalogues" in described


def test_that_warning_is_what_the_plugins_settings_show(qtbot):
    from SciQLop.components.settings.ui.settings_delegates import PluginsDictDelegate
    PluginsDictDelegate._DESCRIPTIONS_CACHE = None
    rows = PluginsDictDelegate()
    qtbot.addWidget(rows)
    rows.set_value({NAME: PluginConfig(enabled=False)})
    assert "Old catalogue system, kept only as a fallback" in rows._rows[NAME].text()
