from tests.fuzzing.model import AppModel


def test_fresh_model_is_empty():
    model = AppModel()
    assert model.panel_count == 0
    assert not model.has_panels
    assert model.products_on == {}


def test_add_panel():
    model = AppModel()
    model.panels.append("Panel-0")
    assert model.panel_count == 1
    assert model.has_panels


def test_products_on_defaults_to_empty_list():
    model = AppModel()
    model.products_on.setdefault("Panel-0", []).append("B_GSE")
    assert model.products_on["Panel-0"] == ["B_GSE"]


def test_remove_panel_cascades():
    model = AppModel()
    model.panels.append("Panel-0")
    model.products_on["Panel-0"] = ["B_GSE", "V_GSE"]
    model.remove_panel("Panel-0")
    assert model.panel_count == 0
    assert "Panel-0" not in model.products_on


def test_reset_clears_everything():
    model = AppModel()
    model.panels.extend(["A", "B"])
    model.products_on["A"] = ["x"]
    model.reset()
    assert model.panel_count == 0
    assert model.products_on == {}
