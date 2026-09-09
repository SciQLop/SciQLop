from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QImage, QPalette, QColor
from PySide6.QtWidgets import QPushButton, QMainWindow, QLabel, QWidget


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


def test_target_destroyed_keeps_the_tip_and_drops_the_spotlight(qtbot):
    """Live report: selecting a product from the empty-panel search box
    destroys that search box (the spotlighted target) and the tour
    vanished. A dying target must not end anything: the card stays, only
    the spotlight goes."""
    host, target = _host(qtbot)
    mark = _mark(qtbot, host)
    mark.show_step(target, "Title", "Body")

    target.deleteLater()
    qtbot.waitUntil(lambda: mark._target is None, timeout=1000)

    assert mark.isVisible()
    assert mark.bubble.isVisible()
    assert mark._cutout_rect() is None


def test_stale_target_destroyed_does_not_touch_the_current_step(qtbot):
    host, first = _host(qtbot)
    second = QPushButton("second", host)
    second.show()
    mark = _mark(qtbot, host)
    mark.show_step(first, "Title", "Body")
    mark.show_step(second, "Title 2", "Body 2")

    first.deleteLater()
    qtbot.wait(50)

    assert mark._target is second
    assert mark._cutout_rect() is not None
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


def test_hiding_the_target_reports_it_and_a_stale_target_does_not(qtbot):
    """Live report: QtAds auto-hide docks close on their own (a click on a
    hover-opened tab toggles it, leaving the tab closes it after 500 ms),
    so a spotlighted product row can vanish mid-step. The mark must tell
    its controller which target went away."""
    host, first = _host(qtbot)
    second = QPushButton("second", host)
    second.show()
    mark = _mark(qtbot, host)
    hidden = []
    mark.target_hidden.connect(hidden.append)

    mark.show_step(first, "Title", "Body")
    first.hide()
    assert hidden == [first]

    mark.show_step(second, "Title 2", "Body 2")
    first.show()
    first.hide()
    assert hidden == [first], "a previous step's target is not ours any more"
    second.hide()
    assert hidden == [first, second]


def test_show_step_does_not_steal_focus_from_a_target_that_has_it(qtbot):
    from PySide6.QtWidgets import QLineEdit
    host, target = _host(qtbot)
    box = QLineEdit(host)
    box.setGeometry(300, 300, 200, 24)
    box.show()
    qtbot.waitUntil(host.isVisible, timeout=1000)
    mark = _mark(qtbot, host)

    mark.show_step(target, "Title", "Body")
    assert host.focusWidget() is mark.bubble

    box.setFocus()
    mark.show_step(box, "Type here", "Body")
    assert host.focusWidget() is box


class _FakeDock(QWidget):
    """The slice of QtAds' CDockWidget the coach mark relies on: an
    auto-hide flyout by default, with the visibility signal it watches."""
    visibilityChanged = Signal(bool)

    def __init__(self, parent, auto_hide=True):
        super().__init__(parent)
        self._auto_hide = auto_hide

    def isAutoHide(self):
        return self._auto_hide


class _FakeDockManager:
    """Stands in for QtAds' CDockManager: `_visible_dock_obstacles` only
    ever calls `.dockWidgetsMap()` on it."""

    def __init__(self, widgets: dict):
        self._widgets = widgets

    def dockWidgetsMap(self):
        return self._widgets


def test_bubble_position_prefers_a_candidate_that_avoids_an_obstacle(qtbot):
    """Live report 2026-09-09: the bubble landed right on top of the
    still-open Products dock -- `_bubble_position` picked the first
    candidate that fit the window without checking whether something
    else was already visible there. Put an obstacle exactly where the
    first candidate (right of the target) would land: a clear
    candidate (left of the target) exists and must be preferred."""
    from SciQLop.components.onboarding.ui.coach_mark import _bubble_position
    from PySide6.QtCore import QSize

    target = QRect(450, 275, 100, 50)
    window = QRect(0, 0, 1000, 600)
    bubble = QSize(200, 100)
    obstacle = QRect(561, 275, 200, 100)  # exactly the "right of target" candidate

    position = _bubble_position(target, bubble, window, obstacles=[obstacle])

    assert not QRect(position, bubble).intersects(obstacle)
    assert window.contains(QRect(position, bubble))


def test_bubble_position_falls_back_to_the_target_corner_when_nothing_clears_every_obstacle(qtbot):
    """Obstacle-avoidance must not break the pre-existing guarantee: if no
    candidate clears every obstacle, still land somewhere inside the
    window rather than give up."""
    from SciQLop.components.onboarding.ui.coach_mark import _bubble_position
    from PySide6.QtCore import QSize

    target = QRect(450, 275, 100, 50)
    window = QRect(0, 0, 1000, 600)
    bubble = QSize(200, 100)
    # One obstacle per candidate direction: nothing can clear all of them.
    obstacles = [
        QRect(561, 275, 200, 100),   # right
        QRect(150, 275, 200, 100),   # left
        QRect(450, 63, 100, 100),    # above
        QRect(450, 387, 100, 100),   # below
    ]

    position = _bubble_position(target, bubble, window, obstacles=obstacles)

    assert window.contains(QRect(position, bubble))


def test_bubble_position_picks_a_clear_corner_inside_a_target_that_fills_the_window(qtbot):
    """Second live report 2026-09-09: an auto-hide flyout is drawn over the
    central area, so a whole-panel target extends under it. No beside
    candidate fits the window; the fallback must then try the target's
    other corners instead of blindly taking the top-left one, which is
    exactly where the flyout sits."""
    from SciQLop.components.onboarding.ui.coach_mark import _bubble_position
    from PySide6.QtCore import QSize

    window = QRect(0, 0, 1820, 1068)
    target = QRect(42, 51, 1778, 962)
    bubble = QSize(336, 218)
    flyout = QRect(42, 46, 270, 998)

    position = _bubble_position(target, bubble, window, obstacles=[flyout])

    assert not QRect(position, bubble).intersects(flyout)
    assert target.contains(QRect(position, bubble))


def test_bubble_position_goes_beside_a_flyout_that_hugs_a_side_tab_target(qtbot):
    """Third live report 2026-09-09: the card sat beside the Properties side
    tab, the user hovered the tab, and the flyout opened on that very
    spot. Every beside-the-tab and inside-the-tab position collides with
    a flyout flush against the side bar; the card must go past it."""
    from SciQLop.components.onboarding.ui.coach_mark import _bubble_position
    from PySide6.QtCore import QSize

    window = QRect(0, 0, 1820, 1068)
    tab = QRect(0, 147, 42, 29)
    bubble = QSize(336, 197)
    flyout = QRect(42, 46, 288, 998)

    position = _bubble_position(tab, bubble, window, obstacles=[flyout])

    assert not QRect(position, bubble).intersects(flyout), position
    assert window.contains(QRect(position, bubble))
    assert position.x() > flyout.right()


def test_bubble_position_stays_above_a_bottom_bar_when_a_flyout_blocks_its_left_end(qtbot):
    """Fourth live report 2026-09-09: with the Products flyout open, the
    spot above the full-width chrome row collided with it and the card
    dropped onto the row itself. Sliding past the flyout must keep the
    "above" row, not fall back to the bar's own top."""
    from SciQLop.components.onboarding.ui.coach_mark import _bubble_position
    from PySide6.QtCore import QSize

    window = QRect(0, 0, 1820, 1068)
    bar = QRect(42, 1013, 1778, 30)
    bubble = QSize(336, 218)
    flyout = QRect(42, 46, 288, 998)

    position = _bubble_position(bar, bubble, window, obstacles=[flyout])

    placed = QRect(position, bubble)
    assert placed.bottom() < bar.top(), position
    assert not placed.intersects(flyout), position
    assert window.contains(placed)


def test_visible_dock_obstacles_keeps_only_open_flyouts_other_than_the_targets_own(qtbot):
    """Third live report 2026-09-09: the central dock (welcome page or plot
    area) fills the window, so counting it as an obstacle left no clear
    spot for a side-tab target and the card stayed on the flyout."""
    from SciQLop.components.onboarding.ui.coach_mark import _visible_dock_obstacles

    host = QMainWindow()
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    panel_dock = _FakeDock(host)
    panel_dock.setGeometry(200, 0, 600, 600)
    target = QPushButton("target", panel_dock)  # lives inside its own dock

    products_dock = _FakeDock(host)
    products_dock.setGeometry(0, 0, 200, 600)
    products_dock.show()

    hidden_dock = _FakeDock(host)
    hidden_dock.setGeometry(0, 0, 100, 100)
    hidden_dock.hide()

    central_dock = _FakeDock(host, auto_hide=False)
    central_dock.setGeometry(0, 0, 800, 600)
    central_dock.show()

    host.dock_manager = _FakeDockManager({
        "Panel": panel_dock, "Products": products_dock, "Hidden": hidden_dock,
        "Welcome": central_dock,
    })

    obstacles = _visible_dock_obstacles(host, target)

    assert obstacles == [QRect(products_dock.mapTo(host, products_dock.rect().topLeft()),
                                products_dock.size())]


def test_visible_dock_obstacles_is_empty_without_a_dock_manager(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import _visible_dock_obstacles
    host, target = _host(qtbot)

    assert _visible_dock_obstacles(host, target) == []


def test_bubble_avoids_a_currently_open_side_dock_next_to_a_near_full_window_target(qtbot):
    """End-to-end: CoachMark actually wires the real dock geometry into
    the positioning, not just the pure helper. The dock covers the whole
    right two-thirds of the window -- wide enough to catch the bubble
    regardless of its exact rendered size -- leaving only its left side
    free."""
    host, target = _host(qtbot, size=(1000, 600), target_geometry=(450, 275, 100, 50))
    products_dock = _FakeDock(host)
    products_dock.setGeometry(560, 0, 440, 600)
    products_dock.show()
    host.dock_manager = _FakeDockManager({"Products": products_dock, "Panel": target})
    mark = _mark(qtbot, host)

    mark.show_step(target, "Add more data", "Body text")

    assert not mark.bubble.geometry().intersects(products_dock.geometry())
    assert host.rect().contains(mark.bubble.geometry())


def test_resizing_the_target_repaints_the_spotlight(qtbot):
    """Live report 2026-09-09 (macOS): resizing a spotlighted side panel
    left the dimming/cutout stuck at the old geometry until something
    else forced a repaint (switching full-screen spaces). The bubble
    itself moved (widgets repaint on their own move/resize) but the
    overlay's own painted cutout doesn't -- it's redrawn only when
    something calls update() on the overlay, and the target-resize
    branch of eventFilter never did."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    class _SpyMark(CoachMark):
        def __init__(self, host):
            super().__init__(host)
            self.update_calls = 0

        def update(self):
            self.update_calls += 1
            super().update()

    host, target = _host(qtbot)
    mark = _SpyMark(host)
    qtbot.addWidget(mark)
    mark.show_step(target, "Title", "Body")
    calls_before_resize = mark.update_calls

    target.resize(target.width() + 40, target.height() + 10)

    assert mark.update_calls > calls_before_resize, \
        "the overlay must repaint itself when its target's geometry changes"
