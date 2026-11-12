"""Templates say what went wrong: products not found, a file that is not a template."""
import pytest

from .fixtures import *  # noqa: F401,F403
from SciQLop.components.plotting.panel_template import (
    PanelTemplate, PlotModel, ProductModel, import_template_file, missing_products_message)


def test_loading_a_template_remembers_the_products_it_did_not_find(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    panel = TimeSyncPanel("missing", time_range=TimeRange(0.0, 1.0))
    qtbot.addWidget(panel)
    template = PanelTemplate(name="t", plots=[PlotModel(products=[
        ProductModel(path="nowhere//gone_product", label="gone")])])
    template.apply(panel)
    assert template.not_found == ["nowhere//gone_product"]


@pytest.mark.parametrize("missing, expected", [
    (["a//b"], 'Template "t": 1 product was not found and is missing from the panel: a//b.'),
    (["a//b", "c//d"], 'Template "t": 2 products were not found and are missing from the panel: a//b, c//d.'),
])
def test_the_message_names_the_missing_products(missing, expected):
    assert missing_products_message("t", missing) == expected


def test_importing_a_file_that_is_not_a_template_is_refused_and_copies_nothing(tmp_path):
    source = tmp_path / "notes.json"
    source.write_text('{"hello": "world"}', encoding="utf-8")
    destination = tmp_path / "templates"
    destination.mkdir()
    with pytest.raises(Exception):
        import_template_file(source, destination)
    assert list(destination.iterdir()) == []


def test_importing_a_template_copies_it(tmp_path):
    source = tmp_path / "good.json"
    PanelTemplate(name="good", plots=[]).to_file(str(source))
    destination = tmp_path / "templates"
    destination.mkdir()
    assert import_template_file(source, destination) == destination / "good.json"
    assert PanelTemplate.from_file(str(destination / "good.json")).name == "good"
