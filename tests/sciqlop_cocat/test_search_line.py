"""The one-line CoCat search field: coloured as the web app colours a search, completes the word at
the cursor from the project's vocabulary, underlines a wrong part, never takes a second line."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCharFormat

VOCABULARY = {"tags": ["sheath", "shock"], "authors": ["me"], "catalogues": ["plain"], "attributes": ["density"]}


def _line(qtbot, text=""):
    from SciQLop.plugins.sciqlop_cocat.search_line import SearchLine
    line = SearchLine()
    line.set_vocabulary(VOCABULARY)
    qtbot.addWidget(line)
    line.show()
    line.setPlainText(text)
    line.moveCursor(line.textCursor().MoveOperation.End)
    return line


def _tone_at(line, position):
    for piece in line.document().firstBlock().layout().formats():
        if piece.start <= position < piece.start + piece.length:
            return piece.format.foreground().color()
    return None


def test_a_search_is_coloured_by_parts(qtbot):
    from SciQLop.plugins.sciqlop_cocat.search_line import TONES
    line = _line(qtbot, "tag:shock OR confidence:>=0.7")
    assert _tone_at(line, 0) == TONES["field"]        # tag
    assert _tone_at(line, 3) == TONES["op"]           # :
    assert _tone_at(line, 5) == TONES["value"]        # shock
    assert _tone_at(line, 10) == TONES["keyword"]     # OR
    assert _tone_at(line, 24) == TONES["op"]          # :>=


def test_completion_offers_the_project_s_words_and_takes_one(qtbot):
    line = _line(qtbot, "tag:sh")
    line.complete_now()
    assert line.completion_words() == ["tag:sheath ", "tag:shock "]
    line.accept_completion("tag:shock ")
    assert line.toPlainText() == "tag:shock " and line.textCursor().position() == len("tag:shock ")


def test_typing_a_space_opens_no_list(qtbot):
    line = _line(qtbot, "tag:shock")
    qtbot.keyClick(line, Qt.Key.Key_Space)
    assert line.toPlainText() == "tag:shock " and not line.completer.popup().isVisible()


def test_a_wrong_part_is_underlined_with_a_wave_and_can_be_cleared(qtbot):
    line = _line(qtbot, "auhtor:bob tag:s")
    line.underline(0, 6)
    [wrong] = line.extraSelections()
    assert (wrong.cursor.selectionStart(), wrong.cursor.selectionEnd()) == (0, 6)
    assert wrong.format.underlineStyle() == QTextCharFormat.UnderlineStyle.WaveUnderline
    line.underline(None)
    assert line.extraSelections() == []


def test_return_does_not_add_a_line(qtbot):
    line = _line(qtbot, "tag:s")
    qtbot.keyClick(line, Qt.Key.Key_Return)
    assert line.toPlainText() == "tag:s"
