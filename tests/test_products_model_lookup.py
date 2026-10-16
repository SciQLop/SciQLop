"""core.models reaches the products model through ProductsModel.instance() on every call.

The model's shared Python wrapper can be marked deleted while the C++ model lives on: a Python-side proxy given the
model with setSourceModel takes the wrapper down when the proxy dies. A wrapper kept from import time then raised
"Internal C++ object (ProductsModel) already deleted" from a %%vp cell (macOS), while ProductsModel.instance() at
the same C++ address was valid.
"""
from SciQLop.core import models


class _Model:
    def __init__(self):
        self.added, self.removed = [], []

    def add_node(self, path, node):
        self.added.append((path, node))
        return True

    def remove_node(self, path):
        self.removed.append(path)


def test_add_and_remove_reach_the_current_model(qapp, monkeypatch):
    current = _Model()
    monkeypatch.setattr(models.ProductsModel, "instance", staticmethod(lambda: current))
    from SciQLopPlots import ParameterType
    models.add_product_node(["pm_lookup"], "leaf", "provider", {}, models.ProductsModelNodeType.PARAMETER,
                            ParameterType.Scalar)
    models.remove_product_node(["pm_lookup", "leaf"])
    assert [path for path, _ in current.added] == [["pm_lookup"]]
    assert current.removed == [["pm_lookup", "leaf"]]


def test_products_still_names_the_current_model(qapp, monkeypatch):
    current = _Model()
    monkeypatch.setattr(models.ProductsModel, "instance", staticmethod(lambda: current))
    from SciQLop.core.models import products
    assert products is current
