import pytest


@pytest.fixture
def chrome(qtbot):
    from SciQLop.components.plotting.ui.catalog_chrome import CatalogChrome
    w = CatalogChrome()
    qtbot.addWidget(w)
    return w


def test_default_mode_is_view(chrome):
    assert chrome.mode == "view"


def test_mode_setter_does_not_emit(chrome):
    signals = []
    chrome.mode_changed.connect(signals.append)
    chrome.mode = "edit"
    assert chrome.mode == "edit"
    assert signals == []


def test_mode_combo_emits_signal_on_user_change(chrome, qtbot):
    with qtbot.waitSignal(chrome.mode_changed, timeout=1000) as blocker:
        chrome._mode_combo.setCurrentIndex(2)
    assert blocker.args == ["edit"]


def test_target_combo_hidden_by_default(chrome):
    assert chrome._target_combo.isHidden() is True


def test_set_targets_shows_combo(chrome):
    chrome.set_targets([("MyCatalog", "uuid-1")])
    assert chrome._target_combo.isHidden() is False
    assert chrome._target_combo.count() == 1
    assert chrome._target_combo.currentText() == "MyCatalog"


def test_set_targets_auto_selects_first(chrome):
    chrome.set_targets([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    assert chrome.selected_target() == "uuid-a"


def test_selected_target_returns_item_data(chrome):
    chrome.set_targets([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    chrome._target_combo.setCurrentIndex(1)
    assert chrome.selected_target() == "uuid-b"


def test_selected_target_none_when_empty(chrome):
    assert chrome.selected_target() is None


def test_clear_targets_hides_combo(chrome):
    chrome.set_targets([("MyCatalog", "uuid-1")])
    chrome.clear_targets()
    assert chrome._target_combo.isHidden() is True
    assert chrome._target_combo.count() == 0
    assert chrome.selected_target() is None


def test_target_changed_signal(chrome, qtbot):
    chrome.set_targets([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    with qtbot.waitSignal(chrome.target_changed, timeout=1000) as blocker:
        chrome._target_combo.setCurrentIndex(1)
    assert blocker.args == ["uuid-b"]


def test_mode_combo_tooltip_documents_the_edit_gesture(chrome):
    """It's not Shift+drag -- it's NeoQCP's click-anchor/move/click-commit
    state machine (item-creation-state.cpp: state==Drawing alone satisfies
    creationActive, so only the *first* click needs the modifier). The
    onboarding tour already describes this correctly; the tooltip didn't
    (2026-09-06 review)."""
    tooltip = chrome._mode_combo.toolTip()
    assert "Shift" in tooltip
    assert "click again" in tooltip


def test_cycle_mode_advances_view_jump_edit_view(chrome, qtbot):
    for expected in ("jump", "edit", "view"):
        with qtbot.waitSignal(chrome.mode_changed, timeout=1000) as blocker:
            chrome.cycle_mode()
        assert chrome.mode == expected
        assert blocker.args == [expected]


def test_mode_combo_tooltip_advertises_shortcut(chrome):
    assert "Ctrl+Shift+M" in chrome._mode_combo.toolTip()
