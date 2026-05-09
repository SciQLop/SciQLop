import pytest


@pytest.fixture
def toggle(qtbot):
    from SciQLop.components.plotting.ui.crosshair_toggle import CrosshairToggle
    w = CrosshairToggle()
    qtbot.addWidget(w)
    return w


def test_default_state_is_on(toggle):
    assert toggle.isChecked() is True


def test_click_emits_toggled(toggle, qtbot):
    with qtbot.waitSignal(toggle.toggled, timeout=1000) as blocker:
        toggle.click()
    assert blocker.args == [False]


def test_tooltip_reflects_state(toggle):
    assert "on" in toggle.toolTip().lower()
    toggle.toggle()
    assert "off" in toggle.toolTip().lower()


def test_icon_swaps_on_toggle(toggle):
    on_icon_key = toggle.icon().cacheKey()
    toggle.toggle()
    off_icon_key = toggle.icon().cacheKey()
    assert on_icon_key != off_icon_key
