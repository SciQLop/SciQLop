from SciQLop.widgets.mainwindow import SciQLopMainWindow


def get_main_window() -> SciQLopMainWindow:
    from SciQLop.backend.sciqlop_application import sciqlop_app
    return sciqlop_app().main_window
