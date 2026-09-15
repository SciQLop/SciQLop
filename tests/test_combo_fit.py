"""Every combobox must be wide enough for its widest item, even after repopulation."""
from PySide6.QtWidgets import QComboBox

from .fixtures import *


def _widest_text(combo: QComboBox) -> int:
    fm = combo.fontMetrics()
    return max((fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())), default=0)


def _fits(combo: QComboBox) -> bool:
    return combo.count() == 0 or combo.minimumWidth() > _widest_text(combo)


def test_fit_combo_refits_when_items_change_later(qtbot):
    from SciQLop.core.ui import fit_combo_to_content
    combo = QComboBox()
    qtbot.addWidget(combo)
    combo.addItems(["a"])
    fit_combo_to_content(combo)
    combo.clear()
    combo.addItems(["a much much much longer item text than before"])
    assert _fits(combo)


def test_agent_settings_popup_combos_fit(qtbot):
    from SciQLop.components.agents.chat.settings_popup import AgentSettingsPopup
    popup = AgentSettingsPopup()
    qtbot.addWidget(popup)
    popup.model_combo.addItem("OpenCode Go/DeepSeek V4.1 Flash Something Long", "x")
    popup.set_effort_values(["low", "medium", "a very verbose effort label"], None)
    for combo in (popup.model_combo, popup.effort_combo, popup.verbosity_combo, popup.writes_combo):
        assert _fits(combo), combo.toolTip()


def test_add_attribute_dialog_type_combo_fits(qtbot, qapp):
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog
    dialog = AddAttributeDialog()
    qtbot.addWidget(dialog)
    assert _fits(dialog._type)


def test_choice_knob_delegate_combo_fits(qtbot):
    from SciQLop.components.plotting.ui.knob_inspector.delegates import _ChoiceDelegate
    from SciQLop.core.knobs.specs import ChoiceKnob
    spec = ChoiceKnob(name="c", label="C", default="a",
                      choices=(("a", "a"), ("a considerably longer choice label", "b")))
    delegate = _ChoiceDelegate(spec)
    qtbot.addWidget(delegate)
    assert _fits(delegate._combo)
