"""The cocat-rs plugin as a built-in SciQLop plugin: found in the plugins folder, loaded under its
one module name, and on for a new installation."""
import os
from types import SimpleNamespace

import cocat_rs

from SciQLop.components.plugins.backend.loader import loader
from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc
from SciQLop.components.plugins.compat import sciqlop_specifier

NAME = "sciqlop_cocat"


def _descriptor() -> PluginDesc:
    return PluginDesc.from_json(os.path.join(loader._bundled_plugins_dir(), NAME, "plugin.json"))


def test_it_is_listed_among_the_built_in_plugins():
    assert NAME in loader.list_plugins(loader._bundled_plugins_dir())


def test_the_loader_imports_it_under_its_package_name(qapp):
    import SciQLop.plugins.sciqlop_cocat as canonical

    module = loader.load_module(loader._bundled_plugins_dir(), NAME)

    assert module is canonical and callable(module.load)


def test_it_asks_for_cocat_rs_and_not_for_sciqlop_itself():
    dependencies = _descriptor().python_dependencies

    assert any(d.startswith("cocat-rs") for d in dependencies)
    assert not sciqlop_specifier(dependencies)


def test_it_is_on_for_a_new_installation():
    assert not _descriptor().disabled
    enabled = loader._enabled_plugins(SimpleNamespace(plugins={}, extra_plugins_folders=[]), {})
    assert NAME in [name for _, name in enabled]


def test_the_tests_never_see_the_sign_in_of_the_person_running_them():
    """The shared test main window loads the plugin: with the system keyring it would connect to
    the real server as the developer."""
    import keyring
    from keyring.backends.null import Keyring

    assert isinstance(keyring.get_keyring(), Keyring)
    assert cocat_rs.Client("https://sciqlop.lpp.polytechnique.fr/cocat-dev").session is None


OLD_PLUGINS = ("tscat_catalogs", "collaborative_catalogs")


def test_the_old_catalogue_plugins_are_gone():
    """Whoever wants the tscat catalogues plugin downgrades SciQLop; its catalogues come into
    this plugin at its first start."""
    bundled = loader.list_plugins(loader._bundled_plugins_dir())
    assert not set(OLD_PLUGINS) & set(bundled)


def test_someone_who_had_them_on_starts_without_them():
    from SciQLop.components.plugins.backend.settings import PluginConfig
    settings = SimpleNamespace(plugins={name: PluginConfig(enabled=True) for name in OLD_PLUGINS},
                               extra_plugins_folders=[])
    enabled = [name for _, name in loader._enabled_plugins(settings, {})]
    assert NAME in enabled and not set(OLD_PLUGINS) & set(enabled)


def test_nothing_in_sciqlop_needs_tscat_gui():
    import pathlib
    import SciQLop
    root = pathlib.Path(SciQLop.__file__).parent
    assert [p for p in root.rglob("*.py") if "tscat_gui" in p.read_text(encoding="utf-8")] == []
