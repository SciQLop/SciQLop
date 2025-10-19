from SciQLop.core.ui.mainwindow import SciQLopMainWindow


def get_main_window() -> SciQLopMainWindow:
    from SciQLop.core.sciqlop_application import sciqlop_app
    return sciqlop_app().main_window
