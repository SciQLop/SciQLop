"""The one-line CoCat search field: underlines a wrong part, completes the word at the cursor, never
takes a second line."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat


def _line(qtbot, words=("tag:", "confidence:", "#density:", "tag:shock")):
    from SciQLop.plugins.sciqlop_cocat.search_line import SearchLine
    line = SearchLine(list(words))
    qtbot.addWidget(line)
    line.show()
    return line


def test_a_wrong_part_is_underlined_with_a_wave_and_can_be_cleared(qtbot):
    line = _line(qtbot)
    line.setPlainText("auhtor:bob tag:s")
    line.underline(0, 6)
    [wrong] = line.extraSelections()
    assert (wrong.cursor.selectionStart(), wrong.cursor.selectionEnd()) == (0, 6)
    assert wrong.format.underlineStyle() == QTextCharFormat.UnderlineStyle.WaveUnderline
    line.underline(None)
    assert line.extraSelections() == []


def test_completion_replaces_the_word_at_the_cursor(qtbot):
    line = _line(qtbot)
    line.setPlainText("tag:s conf")
    line.moveCursor(line.textCursor().MoveOperation.End)
    line.complete_now()
    assert line.completer.completionPrefix() == "conf"
    line.accept_completion("confidence:")
    assert line.toPlainText() == "tag:s confidence:"
    assert set(line.completion_words()) >= {"tag:", "#density:"}


def test_return_does_not_add_a_line(qtbot):
    line = _line(qtbot)
    line.setPlainText("tag:s")
    line.moveCursor(line.textCursor().MoveOperation.End)
    qtbot.keyClick(line, Qt.Key.Key_Return)
    assert line.toPlainText() == "tag:s"
