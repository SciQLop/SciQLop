import os

import numpy as np
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis

from SciQLop.backend.enums import ParameterType
from SciQLop.backend import sciqlop_logging
from SciQLopPlots import ProductsModel, ProductsModelNode, ProductsModelNodeType
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder

log = sciqlop_logging.getLogger(__name__)


class TestPlugin(DataProvider):
    def __init__(self, parent=None):
        super(TestPlugin, self).__init__(name="TestPlugin", data_order=DataOrder.Y_FIRST, cacheable=True)
        root_node = ProductsModelNode("TestPlugin")
        root_node.add_child(
            ProductsModelNode("TestMultiComponent", self.name, {'components': ['x', 'y', 'z']},
                              ProductsModelNodeType.PARAMETER, ParameterType.Vector))
        ProductsModel.instance().add_node([], root_node)

    def get_data(self, product, start, stop):
        log.debug(f"get_data {product} {start} {stop}")
        x = np.arange(start, stop, 0.1) * 1.
        y = np.empty((len(x), 3))
        y[:, 0] = np.cos(x / 100.) * 10.
        y[:, 1] = np.cos((x + 100) / 100.) * 10.
        y[:, 2] = np.cos((x + 200) / 100.) * 10.
        if len(x):
            for _ in range(5):
                random_index = np.random.randint(0, len(x))
                y[random_index, :] = np.nan
        return SpeasyVariable(axes=[VariableTimeAxis((x * 1e9).astype("datetime64[ns]"))], values=DataContainer(y),
                              columns=["x", "y", "z"])

    def labels(self, product):
        return product.metadata("components")


def load(main_window):
    if os.environ.get("SCIQLOP_DEBUG", False):
        return TestPlugin(main_window)
    return None