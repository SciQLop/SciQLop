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


# ---- each suggestion's kind, beside it (cocat-rs 0.12.5's "detail") ----

def _completing(monkeypatch, suggestions):
    import cocat_rs
    monkeypatch.setattr(cocat_rs, "complete",
                        lambda text, cursor, vocabulary: {"from": 0, "to": len(text), "suggestions": suggestions})


def test_the_list_carries_each_suggestion_s_kind_and_inserts_the_text(qtbot, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat.search_line import DETAIL_ROLE
    _completing(monkeypatch, [{"insert": "#origin:", "detail": "attribute"},
                              {"insert": "OR ", "detail": "keyword"}])
    line = _line(qtbot, "o")
    line.complete_now()
    model = line.completer.model()
    rows = [(model.index(i, 0).data(), model.index(i, 0).data(DETAIL_ROLE)) for i in range(model.rowCount())]
    assert rows == [("#origin:", "attribute"), ("OR ", "keyword")]
    assert line.completion_words() == ["#origin:", "OR "]


def test_nothing_to_complete_leaves_no_old_suggestions(qtbot):
    line = _line(qtbot, "tag:sh")
    line.complete_now()
    line.setPlainText("tag:zz")                           # no tag begins so
    line.moveCursor(line.textCursor().MoveOperation.End)
    line.complete_now()
    assert line.completion_words() == []


def test_a_suggestion_without_a_kind_shows_none(qtbot, monkeypatch):
    """cocat-rs before 0.12.5 gives no detail."""
    from SciQLop.plugins.sciqlop_cocat.search_line import DETAIL_ROLE
    _completing(monkeypatch, [{"insert": "tag:"}])
    line = _line(qtbot, "t")
    line.complete_now()
    assert line.completer.model().index(0, 0).data(DETAIL_ROLE) is None
    assert line.completion_words() == ["tag:"]


def test_the_kind_widens_the_list(qtbot, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat.search_line import DETAIL_ROLE
    _completing(monkeypatch, [{"insert": "#origin:", "detail": "attribute"}])
    line = _line(qtbot, "o")
    line.complete_now()
    popup = line.completer.popup()
    delegate = popup.itemDelegate()
    index = line.completer.model().index(0, 0)
    without = popup.fontMetrics().horizontalAdvance("#origin:")
    assert delegate.sizeHint(_option(popup), index).width() > without + popup.fontMetrics().horizontalAdvance("attr")
    assert index.data(DETAIL_ROLE) == "attribute"


def _option(view):
    from PySide6.QtWidgets import QStyleOptionViewItem
    option = QStyleOptionViewItem()
    view.initViewItemOption(option)
    return option


# ---- positions: Qt counts UTF-16 units, cocat-rs characters (an emoji is two units, one character) ----

def _wave(line):
    [wrong] = line.extraSelections()
    return wrong.cursor.selectionStart(), wrong.cursor.selectionEnd()


def test_after_an_emoji_completion_takes_the_word_at_the_cursor(qtbot):
    line = _line(qtbot, "😀 tag:sh")
    line.complete_now()
    assert line.completion_words() == ["tag:sheath ", "tag:shock "]
    line.accept_completion("tag:shock ")
    assert line.toPlainText() == "😀 tag:shock "
    assert line.textCursor().position() == len("😀 tag:shock ".encode("utf-16-le")) // 2


def test_after_an_emoji_tab_takes_the_only_suggestion_for_the_word_at_the_cursor(qtbot):
    line = _line(qtbot, "😀 tag:she OR x")
    cursor = line.textCursor()
    cursor.setPosition(len("😀 tag:she".encode("utf-16-le")) // 2)
    line.setTextCursor(cursor)
    qtbot.keyClick(line, Qt.Key.Key_Tab)
    assert line.toPlainText() == "😀 tag:sheath OR x"


def test_after_an_emoji_the_wave_marks_the_wrong_part(qtbot):
    line = _line(qtbot, "😀 auhtor:me")
    line.underline(2, 6)                                  # characters, as cocat-rs gives them
    assert _wave(line) == (3, 9)                          # Qt's units: the emoji is two


def test_after_an_emoji_the_colours_fall_on_their_parts(qtbot):
    from SciQLop.plugins.sciqlop_cocat.search_line import TONES
    line = _line(qtbot, "😀 tag:shock")
    assert _tone_at(line, 3) == TONES["field"]            # t, after the two units of the emoji
    assert _tone_at(line, 6) == TONES["op"]
    assert _tone_at(line, 7) == TONES["value"]


# ---- the wave at the end of the text ----

def test_a_mistake_at_the_end_is_still_underlined(qtbot):
    line = _line(qtbot, "tag:")
    line.underline(4, 1)                                  # past the last character
    assert _wave(line) == (3, 4)
    line.underline(4, 0)
    assert _wave(line) == (3, 4)


def test_nothing_to_underline_in_an_empty_line(qtbot):
    line = _line(qtbot, "")
    line.underline(0, 1)
    assert line.extraSelections() == []
