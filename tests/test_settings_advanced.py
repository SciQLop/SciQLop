"""Advanced settings stay out of sight until the user asks for them."""
from typing import ClassVar

import pytest
from pydantic import Field
from unittest.mock import patch

from .fixtures import *  # noqa: F401, F403
from SciQLop.components.settings.backend.entry import ConfigEntry


@pytest.fixture(scope="module", autouse=True)
def entries(tmp_path_factory):
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
               str(tmp_path_factory.mktemp("advanced"))):
        class AdvMixedEntry(ConfigEntry):
            category: ClassVar[str] = "adv_mixed"
            subcategory: ClassVar[str] = "general"
            basic_knob: int = 1
            expert_knob: int = Field(2, json_schema_extra={"advanced": True})

        class AdvOnlyEntry(ConfigEntry):
            category: ClassVar[str] = "adv_only"
            subcategory: ClassVar[str] = "general"
            advanced: ClassVar[bool] = True
            knob: int = 3

        yield


def _categories(proxy):
    return {proxy.index(r, 0).data() for r in range(proxy.rowCount())}


def test_a_category_holding_only_advanced_settings_is_hidden_until_asked(qapp):
    from SciQLop.components.settings.backend.model import SettingsFilterProxyModel
    proxy = SettingsFilterProxyModel()
    proxy.rebuild()
    assert "adv_mixed" in _categories(proxy)
    assert "adv_only" not in _categories(proxy)

    proxy.set_show_advanced(True)

    assert "adv_only" in _categories(proxy)


def test_the_filter_does_not_find_hidden_advanced_settings(qapp):
    from SciQLop.components.settings.backend.model import SettingsFilterProxyModel
    proxy = SettingsFilterProxyModel()
    proxy.rebuild()
    proxy.setFilterFixedString("expert_knob")
    assert _categories(proxy) == set()
    proxy.set_show_advanced(True)
    assert _categories(proxy) == {"adv_mixed"}


def _row_names(view):
    from SciQLop.components.settings.ui.setting_panel import SettingRow
    page = view._stack.currentWidget()
    return {row.field_name for row in page.findChildren(SettingRow)}


def test_advanced_rows_appear_only_when_asked(qtbot):
    from SciQLop.components.settings.ui.setting_panel import CategoryView
    view = CategoryView()
    qtbot.addWidget(view)
    view.show_category("adv_mixed")
    assert _row_names(view) == {"basic_knob"}

    view.set_show_advanced(True)

    assert _row_names(view) == {"basic_knob", "expert_knob"}


def test_the_panel_remembers_the_show_advanced_choice(qtbot):
    from SciQLop.components.settings.backend import SciQLopConfigEntry
    from SciQLop.components.settings.ui.setting_panel import SettingsPanel
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.show()
    try:
        panel.show_advanced.setChecked(True)
        assert SciQLopConfigEntry().show_advanced_settings is True
    finally:
        panel.show_advanced.setChecked(False)
    assert SciQLopConfigEntry().show_advanced_settings is False


def test_expert_settings_are_marked_advanced():
    from SciQLop.components.settings.backend.entry import is_advanced
    from SciQLop.components.profiling.settings import ProfilingSettings
    from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings
    from SciQLop.components.theming.settings import SciQLopStyle
    fields = PlotBackendSettings.model_fields
    assert is_advanced(PlotBackendSettings, fields["graph_autoscale_percentile_low"])
    assert not is_advanced(PlotBackendSettings, fields["default_zoom_limit"])
    assert is_advanced(ProfilingSettings, ProfilingSettings.model_fields["sampler_enabled"])
    assert not is_advanced(SciQLopStyle, SciQLopStyle.model_fields["color_palette"])
