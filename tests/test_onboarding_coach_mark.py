from PySide6.QtWidgets import QPushButton, QMainWindow
from PySide6.QtCore import Qt


def test_show_for_positions_bubble_near_target(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    target = QPushButton("target", host)
    target.setGeometry(100, 100, 40, 20)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body text")

    assert mark.isVisible()
    assert mark.geometry() == host.geometry() or mark.size() == host.size()


def test_bubble_stays_within_a_near_full_width_target_instead_of_the_window_edge(qtbot):
    """Reproduces a real report: the onboarding tour's overlay_vs_new_subplot
    step targets the newly created plot, which (for a first plot in an
    otherwise-empty panel) can span almost the entire window. When neither
    the right nor the left side of that target leaves room for the bubble,
    the old fallback clamped to the window's absolute left edge (x=0) --
    which, in the real app, is where the still-open Products side panel
    lives, so the bubble rendered underneath/behind it ("half hidden").
    The bubble must anchor inside the target's own bounds instead, never
    to the left of where the target starts."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    host.resize(1820, 1068)
    # A target spanning nearly the whole window, offset from the left edge
    # by a "side panel" -- the exact shape that broke this.
    target = QPushButton("target", host)
    target.setGeometry(42, 56, 1778, 946)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Adding more data", (
        "Adding more data: drop a product in the middle of a graph to "
        "overlay it there, or near its top/bottom edge (watch for the "
        "blue highlight) to stack it as a new plot in this panel."))

    bubble_rect = mark._bubble.geometry()
    assert bubble_rect.left() >= target.geometry().left(), (
        "bubble drifted left of the target into unrelated screen real "
        f"estate: bubble={bubble_rect}, target={target.geometry()}")


def test_bubble_width_scales_with_metrics_not_a_hardcoded_pixel_value(qtbot):
    """Real report: the bubble was "still hard to read" after the
    text-clipping fix -- a hardcoded pixel width stays fixed while the
    rest of the app's text scales with the system font/DPI (Metrics),
    making the bubble look disproportionately cramped on a scaled
    display. The bubble's width must be derived from Metrics, not a
    magic number, so it scales along with everything else."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark
    from SciQLop.core.ui import Metrics

    host = QMainWindow()
    target = QPushButton("target", host)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)

    assert mark._bubble.width() == Metrics.em(28)


def test_bubble_has_a_visible_border_for_contrast_against_its_surroundings(qtbot):
    """Real report: the bubble can "take a bit of time to find" -- its
    background is palette(window), which can be close in tone to whatever
    sits behind or beside it, and the only other visual anchor on screen
    (the 2px highlight ring) is drawn around the TARGET's cutout, not the
    bubble itself. An explicit, high-contrast border around the bubble
    gives it its own boundary. palette(highlight) (the same accent used
    for the target's spotlight ring) was chosen over palette(mid) because
    a follow-up screenshot showed the latter too washed-out to actually
    stand out."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    qtbot.addWidget(host)

    mark = CoachMark(host)
    qtbot.addWidget(mark)

    style = mark._bubble.styleSheet()
    assert "border:" in style
    assert "palette(highlight)" in style


def test_bubble_border_selector_is_scoped_to_the_bubble_object_name(qtbot):
    """Regression: the first fix set the border via an unscoped QSS
    declaration (no selector) on the bubble container. Qt's style-sheet
    cascade treats an unscoped rule as an implicit universal selector, so
    it painted the same box around every plain-QWidget child too (title,
    body text, "Skip tour", "Got it / Next") -- not just the bubble's own
    outer edge, exactly what a follow-up screenshot showed ("weird").
    Scoping the rule to the bubble's own object name is what keeps it off
    the children."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    qtbot.addWidget(host)

    mark = CoachMark(host)
    qtbot.addWidget(mark)

    assert mark._bubble.objectName()
    assert f"#{mark._bubble.objectName()}" in mark._bubble.styleSheet()


def test_bubble_border_does_not_leak_onto_child_widgets(qtbot):
    """Same regression as above, verified by actually rendering the
    bubble: a leaked border paints the container's own accent-colored
    border line at each child's edge too, not just the bubble's outer
    edge. Compares against the widget's own resolved highlight color
    (rather than a hardcoded RGB triple) so this holds across themes."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark
    from PySide6.QtGui import QImage
    from PySide6.QtGui import QPalette

    host = QMainWindow()
    target = QPushButton("target", host)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body text")

    image = QImage(mark._bubble.size(), QImage.Format.Format_ARGB32)
    mark._bubble.render(image)

    accent = mark.palette().color(QPalette.ColorRole.Highlight)

    def _close_to_accent(color, tolerance=60):
        return (abs(color.red() - accent.red()) < tolerance
                and abs(color.green() - accent.green()) < tolerance
                and abs(color.blue() - accent.blue()) < tolerance)

    title_rect = mark._title_label.geometry()
    edge_pixel = image.pixelColor(title_rect.center().x(), title_rect.top())
    assert not _close_to_accent(edge_pixel)


def test_bubble_stays_outside_the_click_through_cutout_for_a_near_full_window_target(qtbot):
    """Reproduces a real report: for overlay_vs_new_subplot, whose target
    (the panel) spans nearly the whole window, the user saw only the
    panel highlighted -- no info bubble at all, so they assumed the tour
    was stuck and quit. The previous fix (8c01f282) anchored the bubble
    "inside the target's own left edge" when neither side has room, which
    IS within target.geometry() (test_bubble_stays_within_a_near_full_...
    above already covers that geometric property) -- but that position
    also falls inside _cutout_rect(), the region excluded from setMask()
    to let clicks/painting pass through to the target underneath. Per
    QWidget::setMask's documented behavior ("only the parts of the widget
    which overlap region [are] visible... masked widgets receive mouse
    events only on their visible portions"), a child positioned inside
    the excluded region is not just badly placed -- it's invisible and
    unclickable. The bubble's own rect must never be part of the
    click-through hole, regardless of where it lands relative to the
    target."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    host.resize(1820, 1068)
    target = QPushButton("target", host)
    target.setGeometry(42, 56, 1778, 946)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Adding more data", (
        "Adding more data: drop a product in the middle of a graph to "
        "overlay it there, or near its top/bottom edge (watch for the "
        "blue highlight) to stack it as a new plot in this panel."))

    bubble_center = mark._bubble.geometry().center()
    assert mark.mask().contains(bubble_center), (
        "bubble sits inside the click-through cutout -- invisible and "
        f"unclickable; bubble={mark._bubble.geometry()}, "
        f"cutout={mark._cutout_rect()}")


def test_bubble_grows_tall_enough_to_fit_wrapped_body_text(qtbot):
    """Reproduces a real report: the bubble was too short for its own body
    text once it needed several wrapped lines, clipping the last line or
    so. Root cause: _reposition_bubble relied on QWidget.adjustSize(),
    which uses sizeHint() -- and sizeHint() for a layout containing a
    word-wrapped QLabel computes height for the layout's UNCONSTRAINED
    preferred width, not the bubble's actual setFixedWidth(280). Verified
    empirically: for this body text, QLabel.heightForWidth(262) (the
    label's real, narrower content width) returns more than the label's
    actual rendered height was under the old code -- the label was
    genuinely too short for its own wrapped text, not just visually
    cramped."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    host.resize(1820, 1068)
    target = QPushButton("target", host)
    target.setGeometry(42, 56, 1778, 946)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    body = ("Adding more data: drop a product in the middle of a graph to "
            "overlay it there, or near its top/bottom edge (watch for the "
            "blue highlight) to stack it as a new plot in this panel.")
    mark.show_for(target, "Adding more data", body)

    needed = mark._body_label.heightForWidth(mark._body_label.width())
    assert mark._body_label.height() >= needed, (
        f"body label clipped: rendered height={mark._body_label.height()}, "
        f"needed={needed}")


def test_esc_emits_skip_requested(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    target = QPushButton("target", host)
    host.resize(400, 300)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body")

    with qtbot.waitSignal(mark.skip_requested, timeout=1000):
        qtbot.keyClick(mark, Qt.Key.Key_Escape)


def test_dismiss_button_emits_dismiss_clicked(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    target = QPushButton("target", host)
    host.resize(400, 300)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body")

    with qtbot.waitSignal(mark.dismiss_clicked, timeout=1000):
        mark._dismiss_button.click()


def test_show_dismiss_false_hides_dismiss_button(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    target = QPushButton("target", host)
    host.resize(400, 300)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body", show_dismiss=False)

    assert not mark._dismiss_button.isVisible()


def test_show_for_with_rect_highlights_subregion(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark
    from PySide6.QtCore import QRect

    host = QMainWindow()
    target = QPushButton("target", host)
    target.setGeometry(0, 0, 200, 200)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    sub_rect = QRect(10, 10, 20, 20)
    mark.show_for(target, "Title", "Body", rect=sub_rect)

    assert mark._target_rect().size() == sub_rect.size()


def test_target_destroyed_emits_signal_and_hides(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    target = QPushButton("target", host)
    host.resize(400, 300)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body")

    with qtbot.waitSignal(mark.target_destroyed, timeout=1000):
        target.deleteLater()

    assert not mark.isVisible()


def test_cutout_rect_is_padded_target_rect(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark
    from PySide6.QtCore import QRect

    host = QMainWindow()
    target = QPushButton("target", host)
    target.setGeometry(100, 100, 40, 20)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body")

    assert mark._cutout_rect() == mark._target_rect().adjusted(-4, -4, 4, 4)


def test_cutout_rect_follows_partial_highlight_rect(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark
    from PySide6.QtCore import QRect

    host = QMainWindow()
    target = QPushButton("target", host)
    target.setGeometry(0, 0, 200, 200)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    sub_rect = QRect(10, 10, 20, 20)
    mark.show_for(target, "Title", "Body", rect=sub_rect)

    assert mark._cutout_rect() == mark._target_rect().adjusted(-4, -4, 4, 4)


def test_paint_draws_a_highlight_ring_around_the_cutout(qtbot):
    """Real pixel check, not just geometry: the ring must actually be
    painted in the palette's highlight color, not just computed."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark
    from PySide6.QtGui import QImage

    host = QMainWindow()
    target = QPushButton("target", host)
    target.setGeometry(300, 300, 40, 20)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body")

    image = QImage(mark.size(), QImage.Format.Format_ARGB32)
    image.fill(0)
    mark.render(image)

    cutout = mark._cutout_rect()
    # The ring is drawn 1px outside cutout_rect (see paintEvent) so its
    # full width stays clear of the click-through mask -- sample there,
    # not on cutout_rect's own boundary.
    ring_point = (cutout.left() - 1, cutout.center().y())
    highlight = mark.palette().highlight().color()

    pixel = image.pixelColor(*ring_point)
    assert (pixel.red(), pixel.green(), pixel.blue()) == \
        (highlight.red(), highlight.green(), highlight.blue())


def test_clicking_the_spotlighted_target_reaches_the_target(qtbot):
    """Real mouse clicks are hit-tested by position (QWidget.childAt), unlike
    calling .click() directly on the target which bypasses the overlay
    entirely. The coach mark dims everything except a spotlight cutout
    around the target -- a click inside that cutout must actually reach the
    target, not the coach mark sitting on top of it."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    target = QPushButton("target", host)
    target.setGeometry(100, 100, 40, 20)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body")

    center = target.mapTo(host, target.rect().center())
    assert host.childAt(center) is target


def test_clicking_outside_the_spotlight_still_hits_the_coach_mark(qtbot):
    """The dimmed area (outside the spotlight) must still block interaction
    with whatever's behind it -- only the cutout should pass clicks
    through."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    target = QPushButton("target", host)
    target.setGeometry(100, 100, 40, 20)
    decoy = QPushButton("decoy", host)
    decoy.setGeometry(400, 400, 40, 20)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body")

    decoy_center = decoy.mapTo(host, decoy.rect().center())
    assert host.childAt(decoy_center) is mark


def test_block_input_false_lets_input_reach_widgets_outside_the_cutout(qtbot):
    """A step whose completion requires a cross-widget drag (pick up the
    spotlighted target, drop it somewhere else in the window) needs the
    coach mark out of the way everywhere, not just inside its cutout --
    otherwise the drop point, wherever it is, stays covered by the coach
    mark and the drag can never complete. block_input=False must let
    childAt() -- the same hit-testing Qt's own drag-and-drop target
    resolution uses -- resolve past the coach mark anywhere in the
    window, not just the cutout."""
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    target = QPushButton("target", host)
    target.setGeometry(100, 100, 40, 20)
    drop_target = QPushButton("drop target", host)
    drop_target.setGeometry(400, 400, 40, 20)
    host.resize(800, 600)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(target, "Title", "Body", block_input=False)

    drop_target_center = drop_target.mapTo(host, drop_target.rect().center())
    assert host.childAt(drop_target_center) is drop_target


def test_stale_target_destroyed_does_not_abort_current_step(qtbot):
    from SciQLop.components.onboarding.ui.coach_mark import CoachMark

    host = QMainWindow()
    first_target = QPushButton("first", host)
    second_target = QPushButton("second", host)
    host.resize(400, 300)
    qtbot.addWidget(host)
    host.show()

    mark = CoachMark(host)
    qtbot.addWidget(mark)
    mark.show_for(first_target, "Title", "Body")
    mark.show_for(second_target, "Title 2", "Body 2")

    target_destroyed_spy = []
    mark.target_destroyed.connect(lambda: target_destroyed_spy.append(True))

    first_target.deleteLater()
    qtbot.wait(50)

    assert target_destroyed_spy == []
    assert mark._target is second_target
    assert mark.isVisible()
