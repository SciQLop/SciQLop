"""The Logs pane takes its colours from the theme and shows lines a user can
read; the session log file keeps every detail."""
import logging

import pytest

from SciQLop.components.sciqlop_logging.formatter import SciQlopFormatter
from SciQLop.components.sciqlop_logging.logs_widget import LogsWidget, for_display


def _line(level, message="Loaded 3 plugins"):
    record = logging.makeLogRecord({
        "msg": message, "levelno": level, "levelname": logging.getLevelName(level),
        "module": "SciQLop.demo", "filename": "/home/someone/src/demo.py", "lineno": 12})
    return SciQlopFormatter().format(record) + "\n"


def test_no_dark_band_behind_the_text():
    assert "48;5;236" in _line(logging.WARNING)
    assert "48;5;236" not in for_display(_line(logging.WARNING), debug=False)


def test_ordinary_lines_use_the_theme_text_colour():
    assert "\x1b[" not in for_display(_line(logging.INFO), debug=False)


def test_warnings_and_errors_keep_a_colour():
    assert "\x1b[38;5;" in for_display(_line(logging.WARNING), debug=False)
    assert "\x1b[" in for_display(_line(logging.ERROR), debug=False)


def test_the_level_is_written_once():
    assert for_display(_line(logging.INFO), debug=False).count("INFO") == 1


def test_the_source_file_shows_only_in_debug_mode():
    assert "demo.py:12" not in for_display(_line(logging.INFO), debug=False)
    assert "demo.py:12" in for_display(_line(logging.INFO), debug=True)
    assert for_display(_line(logging.INFO), debug=False).rstrip().endswith("Loaded 3 plugins")


def test_a_message_ending_with_parentheses_is_kept():
    shown = for_display(_line(logging.INFO, "Fetched amda/imf (3 components)"), debug=False)
    assert shown.rstrip().endswith("(3 components)")


def test_text_that_is_not_a_log_line_is_left_alone():
    assert for_display("plain output (see notes:3)\n", debug=False) == "plain output (see notes:3)\n"


def test_the_pane_is_coloured_by_the_theme(qtbot):
    pane = LogsWidget(None)
    qtbot.addWidget(pane)
    assert "palette(base)" in pane.styleSheet() and "palette(text)" in pane.styleSheet()
    assert "white" not in pane.styleSheet()
