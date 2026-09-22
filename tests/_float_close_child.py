"""Child process for test_floating_panel_close: create a plot panel, float it, close it.

Run in a subprocess because the bug is a use-after-free that kills the whole process.
argv[1] picks how the floating panel is closed: 'tab' (the tab's X button), 'window'
(closing the floating window itself) or 'forced' (CDockWidget.closeDockWidget()).
"""
import sys

import numpy as np
import PySide6QtAds as QtAds
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication


def pump(ms):
    until = QTimer()
    until.setSingleShot(True)
    until.start(ms)
    while until.isActive():
        QApplication.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def dock_of(widget):
    while widget is not None and not isinstance(widget, QtAds.CDockWidget):
        widget = widget.parentWidget()
    return widget


def main(close_mode: str) -> int:
    from SciQLop.core.sciqlop_application import sciqlop_app

    app = sciqlop_app()
    # Imported after the app exists: they touch application-static Qt singletons.
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.user_api.plot import create_plot_panel

    mw = SciQLopMainWindow()
    mw.show()
    pump(300)

    x = np.arange(1000, dtype=float) + 1.7e9
    create_plot_panel().plot(x, np.sin(x))
    pump(500)

    panel = next(w for w in app.allWidgets() if isinstance(w, TimeSyncPanel))
    dock = dock_of(panel)
    dock.setFloating()
    pump(500)

    close = {
        "tab": dock.requestCloseDockWidget,  # the tab's X button
        "window": dock.floatingDockContainer().close,
        "forced": dock.closeDockWidget,  # skips remove_panel
    }[close_mode]
    close()
    pump(1000)

    print("closed floating panel without crashing", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
