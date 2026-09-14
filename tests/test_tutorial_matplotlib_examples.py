import json
from pathlib import Path


TUTORIALS = Path(__file__).parents[1] / "SciQLop/examples/tutorials"


def test_matplotlib_tutorial_plot_cells_show_figures():
    expected = {
        "Speasy/2-SpeasyFirstSteps.ipynb": (9, 11, 18),
        "Speasy/4-SpeasyDataManipulation.ipynb": (6, 11),
    }

    for notebook, cell_indexes in expected.items():
        cells = json.loads((TUTORIALS / notebook).read_text())["cells"]
        for index in cell_indexes:
            source = "".join(cells[index]["source"])
            assert "plt.show()" in source, f"{notebook} cell {index} needs plt.show()"
