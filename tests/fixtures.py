import pytest
from typing import Tuple
import os
from SciQLop.sciqlop_app import start_sciqlop

@pytest.fixture(scope="session")
def qapp_cls():
    from SciQLop.core.sciqlop_application import SciQLopApp
    return SciQLopApp


@pytest.fixture(scope="function")
def main_window(qtbot, qapp):
    os.environ["SCIQLOP_DEBUG"] = "1"
    qtbot.wait(1)
    main_window=start_sciqlop()
    qtbot.wait(1)
    qtbot.addWidget(main_window)
    return main_window



@pytest.fixture(scope="function")
def simple_vp_callback():
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