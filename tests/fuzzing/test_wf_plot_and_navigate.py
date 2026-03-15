import numpy as np

from tests.fuzzing.panel_actions import create_panel
from tests.fuzzing.plot_data_actions import plot_static_data, plot_static_spectro


def test_create_panel_and_plot_static_data(story_runner):
    panel = story_runner.run(create_panel)
    result = story_runner.run(plot_static_data, panel=panel, x=[1, 2, 3], y=[1, 2, 3])
    graph = result["graph"]
    assert len(graph.data[0])
    assert np.allclose(graph.data[0], [1, 2, 3])
    assert np.allclose(graph.data[1], [1, 2, 3])


def test_create_panel_and_plot_spectro(story_runner):
    panel = story_runner.run(create_panel)
    x = [1, 2, 3]
    y = [1, 2, 3]
    z = [[1, 2, 3], [1, 2, 3], [1, 2, 3]]
    result = story_runner.run(plot_static_spectro, panel=panel, x=x, y=y, z=z)
    graph = result["graph"]
    assert len(graph.data[0])
