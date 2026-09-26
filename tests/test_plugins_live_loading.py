"""Adding a plugin folder or enabling a plugin loads it without a restart.

Its python dependencies are installed live first (guarded install). Only a
removal (folder removed, plugin disabled) still needs a restart: running code
can't be unloaded.
"""
import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

from tests.test_appstore_install import tmp_config_dir  # noqa: F401  (fixture)


def _plugin_folder(tmp_path, name, deps=()):
    folder = tmp_path / f"extra_{name}"
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("def load(main_window):\n    return 'LOADED'\n")
    (pkg / "plugin.json").write_text(json.dumps({
        "name": name, "version": "1.0", "description": "test plugin", "authors": [],
        "license": "MIT", "python_dependencies": list(deps)}))
    return folder


def _ok(specs):
    return SimpleNamespace(returncode=0, stdout="", stderr="")


def _live_loader(install):
    from SciQLop.components.plugins.backend.loader import loader as L
    from SciQLop.components.plugins.backend.live_loader import PluginsLiveLoader
    L._attempted.update(name for _, name in L.new_enabled_plugins())
    return PluginsLiveLoader(main_window=object(), install=install)


def _add_folder(folder):
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    with SciQLopPluginsSettings() as s:
        s.extra_plugins_folders = list(s.extra_plugins_folders) + [str(folder)]


def _loaded(name):
    from SciQLop.components.plugins.backend.loader import loaded_plugins
    return getattr(loaded_plugins, name, None) == "LOADED"


def test_missing_requirements_ignores_sciqlop_and_installed_packages():
    from SciQLop.components.plugins.backend.loader.loader import missing_requirements
    reqs = ["numpy>=1", "numpy>=9999", "SciQLop>=0.1", "definitely-not-installed-xyz"]
    assert missing_requirements(reqs) == ["numpy>=9999", "definitely-not-installed-xyz"]


def test_adding_a_folder_loads_its_new_plugin_live(tmp_config_dir, tmp_path, qtbot):  # noqa: F811
    installs = []
    live = _live_loader(lambda specs: installs.append(specs) or _ok(specs))
    _add_folder(_plugin_folder(tmp_path, "live_plug_a"))
    qtbot.waitUntil(lambda: _loaded("live_plug_a"), timeout=5000)
    assert installs == []
    del live


def test_missing_dependencies_are_installed_before_loading(tmp_config_dir, tmp_path, qtbot):  # noqa: F811
    installs = []
    live = _live_loader(lambda specs: installs.append(specs) or _ok(specs))
    _add_folder(_plugin_folder(tmp_path, "live_plug_b", deps=["definitely-not-installed-xyz"]))
    qtbot.waitUntil(lambda: _loaded("live_plug_b"), timeout=5000)
    assert installs == [["definitely-not-installed-xyz"]]
    del live


def test_a_failed_dependency_install_does_not_load_the_plugin(tmp_config_dir, tmp_path, qtbot):  # noqa: F811
    installs = []

    def failing(specs):
        installs.append(specs)
        return SimpleNamespace(returncode=1, stdout="", stderr="no such package")

    live = _live_loader(failing)
    _add_folder(_plugin_folder(tmp_path, "live_plug_c", deps=["definitely-not-installed-xyz"]))
    qtbot.waitUntil(lambda: bool(installs), timeout=5000)
    qtbot.wait(200)
    assert not _loaded("live_plug_c")
    del live


class _Model(BaseModel):
    folders: list[str] = Field([], json_schema_extra={"restart_required": "on_removal"})


def _folders_row(start):
    from SciQLop.components.settings.ui.setting_panel import SettingRow
    instance = SimpleNamespace(folders=list(start), save=lambda: None)
    return SettingRow("folders", _Model.model_fields["folders"], instance)


def test_adding_a_folder_offers_no_restart(qtbot):
    row = _folders_row(["/a"])
    qtbot.addWidget(row)
    row._on_value_changed(["/a", "/b"])
    assert row.restart_notice.isHidden()


def test_removing_a_folder_offers_a_restart(qtbot):
    row = _folders_row(["/a", "/b"])
    qtbot.addWidget(row)
    row._on_value_changed(["/a"])
    assert not row.restart_notice.isHidden()


@pytest.mark.parametrize("old, new, restart", [
    ({"p": True}, {"p": False}, True),
    ({"p": False}, {"p": True}, False),
    ({"p": True, "q": True}, {"p": True}, True),
])
def test_disabling_a_plugin_offers_a_restart_enabling_does_not(old, new, restart):
    from SciQLop.components.plugins.backend.settings import PluginConfig
    from SciQLop.components.settings.ui.setting_panel import needs_restart
    as_cfg = lambda d: {k: PluginConfig(enabled=v) for k, v in d.items()}
    assert needs_restart("on_removal", as_cfg(old), as_cfg(new)) is restart
