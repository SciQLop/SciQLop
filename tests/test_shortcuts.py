import sys
from unittest.mock import patch

from PySide6.QtGui import QKeySequence

from SciQLop.core.ui.shortcuts import native_shortcut_text, modifier_key_name


def test_native_shortcut_text_renders_with_native_text_format():
    with patch.object(QKeySequence, "toString", return_value="mocked") as to_string:
        assert native_shortcut_text("Ctrl+K") == "mocked"
    to_string.assert_called_once_with(QKeySequence.SequenceFormat.NativeText)


def test_native_shortcut_text_matches_qt_on_this_platform():
    expected = QKeySequence("Ctrl+Shift+H").toString(QKeySequence.SequenceFormat.NativeText)
    assert native_shortcut_text("Ctrl+Shift+H") == expected


def test_modifier_key_name_is_cmd_on_macos():
    with patch.object(sys, "platform", "darwin"):
        assert modifier_key_name() == "Cmd"


def test_modifier_key_name_is_ctrl_elsewhere():
    with patch.object(sys, "platform", "linux"):
        assert modifier_key_name() == "Ctrl"
    with patch.object(sys, "platform", "win32"):
        assert modifier_key_name() == "Ctrl"
