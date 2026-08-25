from .fixtures import *


def test_picker_sizes_itself_to_fit_the_longest_tour_entry(main_window):
    """Reproduces a real report: the dialog opened at whatever default size
    QListWidget's own sizeHint gives (unrelated to the actual item text),
    so a normal tour entry's title+description got clipped/elided and the
    user had to resize the dialog by hand just to read it."""
    from SciQLop.components.onboarding.ui.tour_picker import TourPicker
    from SciQLop.components.onboarding.backend.registry import register_builtin_tours
    from PySide6.QtGui import QFontMetrics

    register_builtin_tours()
    picker = TourPicker(main_window)
    try:
        widest_item_text = max(
            (picker._list.item(i).text() for i in range(picker._list.count())),
            key=len)
        fm = QFontMetrics(picker._list.font())
        assert picker.width() >= fm.horizontalAdvance(widest_item_text)
    finally:
        picker.close()


def test_picker_lists_all_registered_tours(main_window):
    from SciQLop.components.onboarding.ui.tour_picker import TourPicker
    from SciQLop.components.onboarding.backend.registry import register_builtin_tours, all_tours

    register_builtin_tours()
    picker = TourPicker(main_window)
    try:
        registered_ids = {tour.id for tour in all_tours()}
        assert set(picker._items_by_tour_id.keys()) == registered_ids
        assert registered_ids == {"getting_started"}
    finally:
        picker.close()


def test_picker_marks_completed_tours(main_window):
    from SciQLop.components.onboarding.ui.tour_picker import TourPicker
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {"getting_started": True}

    picker = TourPicker(main_window)
    try:
        assert "Completed" in picker._items_by_tour_id["getting_started"].text()
    finally:
        picker.close()
        with OnboardingSettings() as s:
            s.completed_tours = {}


def test_start_selected_starts_the_selected_tour(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_picker import TourPicker
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {}
    main_window._onboarding_controller = None

    picker = TourPicker(main_window)
    picker._list.setCurrentItem(picker._items_by_tour_id["getting_started"])
    picker._start_selected()

    try:
        qtbot.waitUntil(
            lambda: main_window._onboarding_controller is not None
            and main_window._onboarding_controller._tour.id == "getting_started",
            timeout=1000)
    finally:
        main_window._onboarding_controller.abort()


def test_start_selected_with_no_selection_does_nothing(main_window):
    from SciQLop.components.onboarding.ui.tour_picker import TourPicker

    main_window._onboarding_controller = None
    picker = TourPicker(main_window)
    try:
        picker._list.setCurrentItem(None)
        picker._start_selected()
        assert main_window._onboarding_controller is None
    finally:
        picker.close()
