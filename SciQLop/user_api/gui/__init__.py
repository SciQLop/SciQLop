from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from SciQLop.user_api._annotations import experimental_api
from SciQLop.user_api.threading import on_main_thread


def get_main_window() -> SciQLopMainWindow:
    from SciQLop.core.sciqlop_application import sciqlop_app
    return sciqlop_app().main_window


def _show_side_dock(title: str) -> None:
    mw = get_main_window()
    dw = mw.dock_manager.findDockWidget(title)
    if dw is not None:
        dw.toggleView(True)
        dw.raise_()


@experimental_api()
@on_main_thread
def show_product_tree() -> None:
    """Raise or show the Products side dock."""
    _show_side_dock("Products")


@experimental_api()
@on_main_thread
def show_inspector() -> None:
    """Raise or show the Properties/Inspector side dock."""
    _show_side_dock("Properties")
