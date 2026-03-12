from .fixtures import *
import pytest


def test_plot_backend_settings_defaults():
    from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings
    settings = PlotBackendSettings()
    assert settings.default_speasy_backend == "matplotlib"
