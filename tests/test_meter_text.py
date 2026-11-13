"""The text of a status meter is readable on the filled part and on the empty part of its bar.

One colour cannot do both: dark text vanished on the accent-coloured fill in the light themes.
"""
from .fixtures import *  # noqa: F401,F403

FILL, EMPTY, ON_FILL, ON_EMPTY = "#0000ff", "#ffffff", "#ffff00", "#ff0000"
TEXT_COLOURS = {ON_FILL, ON_EMPTY}


def _meter(value):
    from SciQLop.core.ui.meter import Meter
    meter = Meter()
    # The roles Meter reads, set the way the application stylesheet sets them on a real one.
    meter.setStyleSheet(f"QProgressBar {{ background: {EMPTY}; border: none; color: {ON_EMPTY};"
                        f" selection-color: {ON_FILL}; }}"
                        f"QProgressBar::chunk {{ background: {FILL}; }}")
    meter.setFormat("MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM")
    meter.resize(400, 30)
    meter.setValue(value)
    return meter


def _text_colours(meter, columns) -> set[str]:
    image = meter.grab().toImage()
    seen = {image.pixelColor(x, y).name() for x in columns for y in range(image.height())}
    return seen & TEXT_COLOURS


def test_text_is_drawn_in_one_colour_on_the_fill_and_another_on_the_rest(qapp, qtbot):
    meter = _meter(50)
    qtbot.addWidget(meter)

    assert _text_colours(meter, range(60, 190)) == {ON_FILL}
    assert _text_colours(meter, range(210, 340)) == {ON_EMPTY}


def test_an_empty_meter_has_no_text_in_the_fill_colour(qapp, qtbot):
    meter = _meter(0)
    qtbot.addWidget(meter)

    assert _text_colours(meter, range(60, 340)) == {ON_EMPTY}


def test_a_meter_is_wide_enough_for_its_longest_text(qapp, qtbot):
    from SciQLop.core.ui.meter import Meter
    meter = Meter()
    qtbot.addWidget(meter)
    meter.setMaximum(64211)
    meter.setFormat("System memory usage: %v / 64211.00 MB")

    longest = meter.fontMetrics().horizontalAdvance("System memory usage: 64211 / 64211.00 MB")
    assert meter.sizeHint().width() >= longest
    assert meter.minimumSizeHint().width() >= longest
