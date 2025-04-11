import pytest
from typing import Tuple
from pytestqt import qt_compat
from pytestqt.qt_compat import qt_api
import os
os.environ["SCIQLOP_DEBUG"] = "1"


@pytest.fixture(scope="session")
def qapp_cls():
    from SciQLop.backend.sciqlop_application import SciQLopApp
    return SciQLopApp


@pytest.fixture(scope="function")
def main_window(qtbot, qapp):
    from SciQLop.sciqlop_app import start_sciqlop
    main_window=start_sciqlop()
    qtbot.addWidget(main_window)
    return main_window



@pytest.fixture(scope="function")
def simple_vp_callback(qapp, main_window):
    import numpy as np
    def callback(start:float, end:float)-> Tuple[np.ndarray, np.ndarray]:
        x = np.linspace(start, end, int(end-start))
        y = np.sin(x)
        return x, y
    return callback

@pytest.fixture(scope="function")
def plot_panel(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel
    return create_plot_panel()