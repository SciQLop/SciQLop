"""The plugin list shows why a plugin did not load (spec §8)."""
from .fixtures import *


def test_refused_plugin_row_carries_the_reason(qtbot, qapp, monkeypatch):
    from SciQLop.components.plugins.backend.loader.context import STATES, PluginState
    from SciQLop.components.plugins.backend.settings import PluginConfig
    from SciQLop.components.settings.ui.settings_delegates import PluginsDictDelegate

    monkeypatch.setattr(PluginsDictDelegate, "_DESCRIPTIONS_CACHE", {})
    monkeypatch.setitem(STATES, "tip_refused", PluginState("refused", "1.0", reason="needs plugin 'vdf'"))
    monkeypatch.setitem(STATES, "tip_active", PluginState("active", "1.0"))
    delegate = PluginsDictDelegate()
    qtbot.addWidget(delegate)
    delegate.set_value({"tip_refused": PluginConfig(), "tip_active": PluginConfig()})
    refused, active = delegate._rows["tip_refused"], delegate._rows["tip_active"]
    assert "needs plugin 'vdf'" in refused.toolTip() and "not loaded" in refused.text()
    assert active.toolTip() == "" and "not loaded" not in active.text()
