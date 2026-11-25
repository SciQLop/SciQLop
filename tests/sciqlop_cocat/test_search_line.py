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


# ---- Tab ----

def _between(qtbot, text=""):
    """The line between two other fields, shown, with the focus and the cursor at the end."""
    from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget
    from SciQLop.plugins.sciqlop_cocat.search_line import SearchLine
    host = QWidget()
    layout = QVBoxLayout(host)
    before, line, after = QLineEdit(), SearchLine(), QLineEdit()
    for part in (before, line, after):
        layout.addWidget(part)
    line.set_vocabulary(VOCABULARY)
    qtbot.addWidget(host)
    line.host = host  # the test holds the line: the window must live as long
    host.show()
    qtbot.waitExposed(host)
    host.activateWindow()
    qtbot.waitUntil(host.isActiveWindow)
    line.setPlainText(text)
    line.moveCursor(line.textCursor().MoveOperation.End)
    line.setFocus()
    qtbot.waitUntil(line.hasFocus)
    return before, line, after


def test_tab_takes_the_highlighted_suggestion(qtbot):
    _, line, _ = _between(qtbot, "tag:sh")
    line.complete_now()
    popup = line.completer.popup()
    qtbot.waitUntil(popup.isVisible)
    popup.setCurrentIndex(popup.model().index(1, 0))
    qtbot.keyClick(popup, Qt.Key.Key_Tab)
    assert line.toPlainText() == "tag:shock " and not popup.isVisible() and line.hasFocus()


def test_tab_takes_the_first_suggestion_when_none_is_highlighted(qtbot):
    _, line, _ = _between(qtbot, "tag:sh")
    line.complete_now()
    popup = line.completer.popup()
    qtbot.waitUntil(popup.isVisible)
    popup.setCurrentIndex(popup.model().index(-1, -1))
    qtbot.keyClick(popup, Qt.Key.Key_Tab)
    assert line.toPlainText() == "tag:sheath " and not popup.isVisible()


def test_tab_takes_the_only_suggestion(qtbot):
    _, line, _ = _between(qtbot, "ta")
    qtbot.keyClick(line, Qt.Key.Key_Tab)
    assert line.toPlainText() == "tag:" and line.hasFocus()


def test_tab_opens_the_list_when_several_fit(qtbot):
    _, line, _ = _between(qtbot, "tag:sh")
    qtbot.keyClick(line, Qt.Key.Key_Tab)
    qtbot.waitUntil(line.completer.popup().isVisible)
    assert line.toPlainText() == "tag:sh" and line.completion_words() == ["tag:sheath ", "tag:shock "]


def test_tab_moves_on_when_there_is_nothing_to_complete(qtbot):
    for text in ("", "xyz", "tag:shock "):
        _, line, after = _between(qtbot, text)
        qtbot.keyClick(line, Qt.Key.Key_Tab)
        qtbot.waitUntil(after.hasFocus)
        assert line.toPlainText() == text, text


def test_shift_tab_always_moves_back(qtbot):
    before, line, _ = _between(qtbot, "tag:sh")
    qtbot.keyClick(line, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    qtbot.waitUntil(before.hasFocus)
    before, line, _ = _between(qtbot, "tag:sh")
    line.complete_now()
    qtbot.waitUntil(line.completer.popup().isVisible)
    qtbot.keyClick(line.completer.popup(), Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
    qtbot.waitUntil(before.hasFocus)
    assert line.toPlainText() == "tag:sh" and not line.completer.popup().isVisible()
