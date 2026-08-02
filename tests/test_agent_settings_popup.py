"""The settings popup owns every control that used to crowd the chat header."""
import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


def test_popup_owns_the_relocated_controls(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    for name in ("model_combo", "effort_combo", "verbosity_combo",
                 "writes_toggle", "export_button"):
        widget = getattr(popup, name)
        assert widget is not None
        assert widget.parent() is popup


def test_effort_row_hidden_when_backend_reports_no_values(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    popup.set_effort_values((), None)
    assert not popup.is_effort_row_visible()


def test_effort_row_lists_exactly_the_models_values(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    popup.set_effort_values(("minimal", "low", "medium", "high"), None)
    assert popup.is_effort_row_visible()
    labels = [popup.effort_combo.itemText(i)
              for i in range(popup.effort_combo.count())]
    assert labels == ["Default", "minimal", "low", "medium", "high"]
    assert popup.current_effort() is None      # "Default" means no override


def test_selecting_an_effort_emits_and_reports_it(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    popup.set_effort_values(("low", "medium", "high"), None)
    with qtbot.waitSignal(popup.effort_changed, timeout=1000) as sig:
        popup.effort_combo.setCurrentIndex(3)   # 0=Default, so 3 == "high"
    assert sig.args == ["high"]
    assert popup.current_effort() == "high"


def test_restoring_a_value_absent_from_this_model_falls_back_to_default(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    # "xhigh" is valid for Claude but not for this Gemini-style model.
    popup.set_effort_values(("minimal", "low", "medium", "high"), "xhigh")
    assert popup.current_effort() is None


def test_export_button_emits_export_requested(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup

    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    with qtbot.waitSignal(popup.export_requested, timeout=1000):
        popup.export_button.click()


def test_effort_setting_is_per_backend():
    from SciQLop.components.agents.settings import AgentChatSettings

    settings = AgentChatSettings()
    assert settings.effort == {}
    settings.effort = {"Claude": "high", "GitHub Copilot": "minimal"}
    assert settings.effort["Claude"] == "high"
    assert settings.effort["GitHub Copilot"] == "minimal"
