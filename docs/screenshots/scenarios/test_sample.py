"""Sample screenshot scenario to verify the pipeline works."""
import numpy as np

from tests.fuzzing.panel_actions import create_panel
from tests.fuzzing.plot_data_actions import plot_static_data, plot_static_spectro
from tests.fuzzing.screenshot_actions import take_screenshot


def test_sample_timeseries(screenshot_runner):
    panel = screenshot_runner.run(create_panel)
    x = np.linspace(0, 100, 1000)
    y = np.sin(x * 0.1) * np.cos(x * 0.03)
    screenshot_runner.run(plot_static_data, panel=panel, x=x, y=y)
    screenshot_runner.run(take_screenshot, name="sample/timeseries")


def test_sample_spectrogram(screenshot_runner):
    panel = screenshot_runner.run(create_panel)
    x = np.linspace(0, 100, 200)
    y = np.linspace(0, 50, 100)
    z = np.random.default_rng(42).standard_normal((len(x), len(y)))
    screenshot_runner.run(plot_static_spectro, panel=panel, x=x, y=y, z=z)
    screenshot_runner.run(take_screenshot, name="sample/spectrogram")


def test_sample_panel_crop(screenshot_runner):
    panel = screenshot_runner.run(create_panel)
    x = np.linspace(0, 100, 1000)
    y = np.sin(x * 0.2)
    screenshot_runner.run(plot_static_data, panel=panel, x=x, y=y)
    screenshot_runner.run(
        take_screenshot, name="sample/panel-crop", target=f"panel:{panel}",
    )
