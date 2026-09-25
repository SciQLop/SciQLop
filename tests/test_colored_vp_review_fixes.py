"""Reproducers for the final-review findings on colour-axis virtual products."""
import numpy as np
import pytest

from SciQLop.user_api.data_types import Colored


def _colored(n=4, columns=3):
    t = np.linspace(0.0, 1.0, n)
    return Colored((t, np.zeros((n, columns))), color=np.arange(float(n)))


def test_a_callable_dependency_returning_colored_gives_its_data():
    from SciQLop.components.plotting.backend.dependencies import _resolve_target
    c = _colored()
    assert _resolve_target(lambda start, stop: c, 0.0, 1.0) is c.data


def test_a_path_dependency_on_a_coloured_vp_gives_its_data(monkeypatch):
    from SciQLop.components.plotting.backend import dependencies, data_provider
    from SciQLop.core.models import products
    c = _colored()

    class _Provider:
        def get_data(self, node, start, stop):
            return c

    class _Node:
        def provider(self):
            return "colored-fake"

    monkeypatch.setattr(products, "node", lambda path: _Node())
    monkeypatch.setattr(data_provider, "providers", {"colored-fake": _Provider()})
    assert dependencies.resolve_product_path("a//b", 0.0, 1.0) is c.data


def test_an_unannotated_coloured_multicomponent_cell_gets_one_label_per_column():
    from SciQLop.user_api.virtual_products.registry import _infer_multicomponent_labels
    assert _infer_multicomponent_labels(_colored(columns=5)) == ["C0", "C1", "C2", "C3", "C4"]


@pytest.mark.parametrize("color", [np.array([5.0]), np.array([[5.0]])])
def test_a_single_sample_batch_keeps_its_colour(color):
    t = np.array([1.0])
    checked = Colored((t, np.zeros((1, 3))), color=color).checked()
    assert np.array_equal(checked.color, [5.0])
