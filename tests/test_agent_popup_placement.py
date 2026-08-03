"""Popups anchored to widgets near a screen edge must stay on screen."""
from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures

SCREEN = (0, 0, 1920, 1080)


def _origin(anchor, size, screen=SCREEN):
    from PySide6.QtCore import QRect, QSize
    from SciQLop.components.agents.chat.popup_placement import popup_origin

    return popup_origin(QRect(*anchor), QSize(*size), QRect(*screen))


def test_opens_below_the_anchor_when_there_is_room():
    origin = _origin(anchor=(100, 200, 20, 20), size=(300, 400))
    assert (origin.x(), origin.y()) == (100, 220)


def test_flips_above_the_anchor_when_below_would_be_cropped():
    origin = _origin(anchor=(100, 1000, 20, 20), size=(300, 400))
    assert (origin.x(), origin.y()) == (100, 600)


def test_clamps_to_the_screen_when_neither_side_fits():
    origin = _origin(anchor=(100, 500, 20, 20), size=(300, 2000))
    assert origin.y() == 0


def test_clamps_horizontally_at_the_right_edge():
    origin = _origin(anchor=(1800, 200, 20, 20), size=(300, 400))
    assert origin.x() == 1619  # last x where a 300-wide popup still ends at 1919


def test_respects_a_screen_that_does_not_start_at_the_origin():
    origin = _origin(anchor=(2000, 1900, 20, 20), size=(300, 400),
                     screen=(1920, 1080, 1920, 1080))
    assert (origin.x(), origin.y()) == (2000, 1500)


def test_placed_popup_fits_the_screen_from_a_bottom_anchor(qtbot):
    from PySide6.QtWidgets import QLabel, QPushButton
    from SciQLop.components.agents.chat.popup_placement import place_popup

    anchor = QPushButton("anchor")
    qtbot.addWidget(anchor)
    anchor.show()
    qtbot.waitExposed(anchor)
    available = anchor.screen().availableGeometry()
    anchor.move(available.left() + 10, available.bottom() - anchor.height())

    popup = QLabel("\n".join(f"line {i}" for i in range(40)), None)
    qtbot.addWidget(popup)
    place_popup(popup, anchor)

    assert available.contains(popup.frameGeometry())
