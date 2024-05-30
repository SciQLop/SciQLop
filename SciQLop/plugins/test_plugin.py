import os

import numpy as np
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis

from SciQLop.backend import Product
from SciQLop.backend.enums import ParameterType
from SciQLop.backend.models import products
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder


class TestPlugin(DataProvider):
    def __init__(self, parent=None):
        super(TestPlugin, self).__init__(name="TestPlugin", data_order=DataOrder.Y_FIRST, cacheable=True)
        root_node = Product(name="TestPlugin", metadata={}, provider=self.name, uid=self.name)
        root_node.merge(
            Product(name="TestMultiComponent", metadata={'components': "x;y;z"},
                    provider=self.name,
                    uid="TestMultiComponent",
                    is_parameter=True,
                    parameter_type=ParameterType.VECTOR))
        products.add_products(root_node)

    def get_data(self, product, start, stop):
        x = np.arange(start.timestamp(), stop.timestamp(), 0.1) * 1.
        y = np.empty((len(x), 3))
        y[:, 0] = np.cos(x / 100.) * 10.
        y[:, 1] = np.cos((x + 100) / 100.) * 10.
        y[:, 2] = np.cos((x + 200) / 100.) * 10.
        return SpeasyVariable(axes=[VariableTimeAxis((x * 1e9).astype("datetime64[ns]"))], values=DataContainer(y),
                              columns=["x", "y", "z"])


def load(main_window):
    if os.environ.get("SCIQLOP_DEBUG", False):
        return TestPlugin(main_window)
