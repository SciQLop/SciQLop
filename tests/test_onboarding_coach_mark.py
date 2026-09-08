from PySide6.QtCore import Qt, QRect, QSize, QPoint
from PySide6.QtGui import QImage, QPalette, QColor
from PySide6.QtWidgets import QPushButton, QMainWindow, QLabel


def _host(qtbot, size=(800, 600), target_geometry=(100, 100, 40, 20)):
    host = QMainWindow()
    host.resize(*size)
    target = QPushButton("target", host)
    target.setGeometry(*target_geometry)
    qtbot.addWidget(host)
    host.show()
    return host, target


def _mark(qtbot, host):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark
    mark = CoachMark(host)
    qtbot.addWidget(mark)
    return mark


def test_show_step_covers_the_host_and_shows_the_bubble(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body text")

    assert mark.isVisible()
    assert mark.size() == host.size()
    assert mark.bubble.isVisible()


def test_bubble_sits_right_of_a_small_target(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body text")

    assert mark.bubble.geometry().left() > target.geometry().right()
    assert host.rect().contains(mark.bubble.geometry())


def test_bubble_stays_inside_a_near_full_window_target(qtbot):
    """A first plot in an otherwise-empty panel spans almost the whole
    window. With no room on any side the bubble must anchor inside the
    target, never drift onto unrelated UI at the window's edge."""
    host, target = _host(qtbot, size=(1820, 1068), target_geometry=(42, 56, 1778, 946))
    mark = _mark(qtbot, host)
    mark.show_step(target, "Adding more data", "x " * 60)

    bubble_rect = mark.bubble.geometry()
    assert bubble_rect.left() >= target.geometry().left()
    assert host.rect().contains(bubble_rect)


def test_bubble_goes_above_a_full_width_bar_at_the_bottom(qtbot):
    """The panel's chrome row is a full-width strip at the bottom of the
    window: beside it there is no room, and inside it the bubble would
    cover the very controls the tip is about."""
    host, target = _host(qtbot, size=(1820, 1068), target_geometry=(42, 1013, 1778, 30))
    mark = _mark(qtbot, host)
    mark.show_step(target, "Navigate", "Body text")

    assert mark.bubble.geometry().bottom() < target.geometry().top()


def test_bubble_is_centered_when_there_is_no_target(qtbot):
    host, _target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(None, "Welcome", "Body text")

    center = mark.bubble.geometry().center()
    assert abs(center.x() - host.width() // 2) <= 2
    assert abs(center.y() - host.height() // 2) <= 2
    assert mark._cutout_rect() is None


def test_bubble_width_scales_with_metrics_not_a_hardcoded_pixel_value(qtbot):
    from SciQLop.core.ui import Metrics
    host, _target = _host(qtbot)
    mark = _mark(qtbot, host)
    assert mark.bubble.width() == Metrics.em(28)


def test_bubble_style_is_scoped_to_its_object_name_with_border_and_distinct_background(qtbot):
    """An unscoped rule cascades to every plain-QWidget child (title,
    body, buttons); palette(tooltip-base) keeps the card visibly distinct
    from ordinary chrome in both themes."""
    host, _target = _host(qtbot)
    mark = _mark(qtbot, host)
    style = mark.bubble.styleSheet()
    assert mark.bubble.objectName()
    assert f"#{mark.bubble.objectName()}" in style
    assert "border:" in style and "palette(highlight)" in style
    assert "palette(tooltip-base)" in style


def test_bubble_border_does_not_leak_onto_child_widgets(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body text")

    image = QImage(mark.bubble.size(), QImage.Format.Format_ARGB32)
    mark.bubble.render(image)
    accent = mark.palette().color(QPalette.ColorRole.Highlight)
    title_rect = mark.bubble._title_label.geometry()
    edge = image.pixelColor(title_rect.center().x(), title_rect.top())
    assert max(abs(edge.red() - accent.red()), abs(edge.green() - accent.green()),
               abs(edge.blue() - accent.blue())) >= 60


def test_bubble_grows_tall_enough_to_fit_wrapped_body_text(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    body = ("Drop another product in the middle of a plot to overlay it, or "
            "near the top or bottom edge (a blue highlight appears) to stack "
            "it as a new plot. Right-clicking a product offers the same choices.")
    mark.show_step(target, "Add more data", body)

    label = mark.bubble._body_label
    assert label.height() >= label.heightForWidth(label.width())


def test_bubble_reserves_descent_slack_below_the_wrapped_body_text(qtbot):
    """Exact-fit sizing leaves zero slack at fractional DPI scale factors
    and shaves off descenders (g/y/p/q/j)."""
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    body = "Some wrapped body text that goes on for a while and then wraps again and again."
    mark.show_step(target, "Title", body)

    label = mark.bubble._body_label
    margins = mark.bubble.layout().contentsMargins()
    body_width = mark.bubble.width() - margins.left() - margins.right()
    reference = QLabel()
    reference.setWordWrap(True)
    reference.setFont(label.font())
    reference.setText(body)
    assert label.height() >= reference.heightForWidth(body_width) + reference.fontMetrics().descent()


def test_descent_slack_does_not_carry_over_from_a_previous_taller_step(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Long", "word " * 80)
    tall = mark.bubble._body_label.height()
    mark.show_step(target, "Short", "Short tip.")
    assert mark.bubble._body_label.height() < tall


def test_bubble_shows_progress_back_and_next_label(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body", progress="3 / 14", can_go_back=True, next_label="Done")

    assert mark.bubble._progress_label.text() == "3 / 14"
    assert mark.bubble._back_button.isVisible()
    assert mark.bubble._next_button.text() == "Done"

    mark.show_step(target, "Title", "Body", progress="1 / 14", can_go_back=False)
    assert not mark.bubble._back_button.isVisible()
    assert mark.bubble._next_button.text() == "Next"


def test_next_button_is_styled_as_the_primary_action(qtbot):
    host, _target = _host(qtbot)
    mark = _mark(qtbot, host)
    button = mark.bubble._next_button
    assert button.objectName()
    assert f"#{button.objectName()}" in button.styleSheet()
    assert "palette(highlight)" in button.styleSheet()


def test_buttons_and_keys_emit_the_navigation_signals(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body", can_go_back=True)

    with qtbot.waitSignal(mark.next_clicked, timeout=1000):
        mark.bubble._next_button.click()
    with qtbot.waitSignal(mark.back_clicked, timeout=1000):
        mark.bubble._back_button.click()
    with qtbot.waitSignal(mark.skip_requested, timeout=1000):
        mark.bubble._skip_button.click()
    with qtbot.waitSignal(mark.skip_requested, timeout=1000):
        qtbot.keyClick(mark.bubble, Qt.Key.Key_Escape)
    with qtbot.waitSignal(mark.next_clicked, timeout=1000):
        qtbot.keyClick(mark.bubble, Qt.Key.Key_Return)


def test_show_step_with_rect_highlights_subregion(qtbot):
    host, target = _host(qtbot, target_geometry=(0, 0, 200, 200))
    mark = _mark(qtbot, host)
    sub_rect = QRect(10, 10, 20, 20)
    mark.show_step(target, "Title", "Body", rect=sub_rect)

    assert mark._target_rect().size() == sub_rect.size()
    assert mark._cutout_rect() == mark._target_rect().adjusted(-4, -4, 4, 4)


def test_target_destroyed_emits_signal_and_hides_everything(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body")

    with qtbot.waitSignal(mark.target_destroyed, timeout=1000):
        target.deleteLater()

    assert not mark.isVisible()
    assert not mark.bubble.isVisible()


def test_stale_target_destroyed_does_not_emit(qtbot):
    host, first = _host(qtbot)
    second = QPushButton("second", host)
    second.show()
    mark = _mark(qtbot, host)
    mark.show_step(first, "Title", "Body")
    mark.show_step(second, "Title 2", "Body 2")
    fired = []
    mark.target_destroyed.connect(lambda: fired.append(True))

    first.deleteLater()
    qtbot.wait(50)

    assert fired == []
    assert mark._target is second
    assert mark.isVisible()


def test_paint_draws_a_highlight_ring_around_the_cutout(qtbot):
    host, target = _host(qtbot, target_geometry=(300, 300, 40, 20))
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body")

    image = QImage(mark.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    mark.render(image)
    cutout = mark._cutout_rect()
    pixel = image.pixelColor(cutout.left() - 1, cutout.center().y())
    highlight = mark.palette().highlight().color()
    assert (pixel.red(), pixel.green(), pixel.blue()) == (highlight.red(), highlight.green(), highlight.blue())


def test_overlay_never_intercepts_mouse_input(qtbot):
    """The dimming only guides the eye: a click or a drop anywhere in the
    window, spotlighted or dimmed, must reach the widget underneath, so
    every tip can be acted on while it is displayed."""
    host, target = _host(qtbot)
    elsewhere = QPushButton("elsewhere", host)
    elsewhere.setGeometry(400, 400, 40, 20)
    elsewhere.show()
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body")

    assert host.childAt(target.mapTo(host, target.rect().center())) is target
    assert host.childAt(elsewhere.mapTo(host, elsewhere.rect().center())) is elsewhere


def test_bubble_itself_still_receives_mouse_input(qtbot):
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body")

    hit = host.childAt(mark.bubble.mapTo(host, mark.bubble._next_button.rect().center()
                                         + mark.bubble._next_button.pos()))
    assert hit is mark.bubble._next_button


def test_dispose_deletes_the_bubble_too(qtbot):
    import shiboken6
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body")
    bubble = mark.bubble

    mark.dispose()
    qtbot.waitUntil(lambda: not shiboken6.isValid(bubble), timeout=1000)
    assert not mark.isVisible()


def test_bubble_actually_paints_its_background_and_border(qtbot):
    """Live report: the card rendered as free-floating text over the
    welcome page. A QWidget *subclass* only paints its style-sheet
    background/border with WA_StyledBackground set; a plain QWidget
    instance gets that for free, a subclass does not."""
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body text")

    bubble = mark.bubble
    image = QImage(bubble.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor(255, 0, 255))
    bubble.render(image)

    def _close(a, b, tolerance=40):
        return max(abs(a.red() - b.red()), abs(a.green() - b.green()),
                   abs(a.blue() - b.blue())) <= tolerance

    mid_y = bubble.height() // 2
    border_pixel = image.pixelColor(1, mid_y)
    inside_pixel = image.pixelColor(bubble.layout().contentsMargins().left() // 2, mid_y)
    assert _close(border_pixel, bubble.palette().color(QPalette.ColorRole.Highlight)), border_pixel
    assert _close(inside_pixel, bubble.palette().color(QPalette.ColorRole.ToolTipBase)), inside_pixel
