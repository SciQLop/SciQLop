import numpy as np

from SciQLop.backend.products_model import ProductNode, ParameterType
from SciQLop.backend import products
from SciQLop.backend.data_provider import DataProvider, DataOrder
import humanize


class TestPlugin(DataProvider):
    def __init__(self, parent=None):
        super(TestPlugin, self).__init__(name="TestPlugin", parent=parent, data_order=DataOrder.ROW_MAJOR)
        root_node = ProductNode(name="TestPlugin", metadata={}, provider=self.name, uid=self.name)
        root_node.append_child(
            ProductNode(name="TestMultiComponent", metadata={'components': '3'},
                        provider=self.name,
                        uid="TestMultiComponent",
                        is_parameter=True,
                        parameter_type=ParameterType.VECTOR))
        products.add_products(root_node)

    def get_data(self, product, start, stop):
        x = np.arange(start.timestamp(), stop.timestamp(), 0.1) * 1.
        y = np.cos([(x + l * 100) / 100. for l in range(3)]) * 10.
        print(f"{humanize.intword(len(x))} points")
        return x, y.T


def load(main_window):
    return TestPlugin(main_window)
