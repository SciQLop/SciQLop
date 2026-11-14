"""The cocat-rs plugin as a built-in SciQLop plugin: found in the plugins folder, loaded under its
one module name, and off until the user enables it."""
import os

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


def test_it_is_off_until_enabled():
    """Moving it in must not give every user a second catalogue root, nor change the default provider."""
    assert _descriptor().disabled
