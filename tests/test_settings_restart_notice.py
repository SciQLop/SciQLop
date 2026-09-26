"""A setting marked restart_required offers a restart once it is changed."""
from types import SimpleNamespace

from pydantic import BaseModel, Field


class _Model(BaseModel):
    needs_restart: str = Field("", json_schema_extra={"restart_required": True})
    live: str = ""


def _row(field_name):
    from SciQLop.components.settings.ui.setting_panel import SettingRow
    instance = SimpleNamespace(needs_restart="", live="", save=lambda: None)
    return SettingRow(field_name, _Model.model_fields[field_name], instance)


def test_the_notice_appears_only_after_a_restart_bound_change(qtbot):
    row = _row("needs_restart")
    qtbot.addWidget(row)
    assert row.restart_notice.isHidden()
    row._on_value_changed("new")
    assert not row.restart_notice.isHidden()


def test_a_live_setting_never_offers_a_restart(qtbot):
    row = _row("live")
    qtbot.addWidget(row)
    row._on_value_changed("new")
    assert row.restart_notice is None


def test_the_notice_button_restarts_sciqlop(qtbot, monkeypatch):
    calls = []
    monkeypatch.setattr("SciQLop.sciqlop_app.restart_sciqlop", lambda: calls.append(True))
    row = _row("needs_restart")
    qtbot.addWidget(row)
    row._on_value_changed("new")
    row.restart_notice.button.click()
    assert calls == [True]


def test_plugin_settings_are_marked_restart_required():
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    for name in ("plugins", "extra_plugins_folders"):
        extra = SciQLopPluginsSettings.model_fields[name].json_schema_extra
        assert extra.get("restart_required") == "on_removal", name
