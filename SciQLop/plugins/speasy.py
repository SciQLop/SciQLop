from webbrowser import get

from SciQLopBindings import DataProvider, Product, ScalarTimeSerie, VectorTimeSerie, MultiComponentTimeSerie
from SciQLopBindings import SciQLopCore, MainWindow, TimeSyncPanel, ProductsTree, DataSeriesType
import numpy as np

import speasy as spz
from speasy.inventory.indexes import ParameterIndex, ComponentIndex
from speasy.inventory.data_tree import amda


def explore_nodes(node, path, leaves):
    for name, child in node.__dict__.items():
        cur_path = path + "/" + name
        if isinstance(child, ParameterIndex):
            leaves[cur_path] = child
        elif hasattr(child, "__dict__"):
            explore_nodes(child, cur_path, leaves)


def count_components(param: ParameterIndex):
    if hasattr(param, "size"):
        return int(param.size)
    return 0


def data_serie_type(param: ParameterIndex):
    if hasattr(param, "display_type"):
        if param.display_type == 'timeseries':
            components_cnt = count_components(param)
            if components_cnt == 0:
                return DataSeriesType.SCALAR
            if components_cnt == 3:
                return DataSeriesType.VECTOR
            return DataSeriesType.MULTICOMPONENT
        if param.display_type == 'spectrogram':
            return DataSeriesType.SPECTROGRAM
    return DataSeriesType.NONE


def get_node_meta(node):
    meta = {}
    for name, child in node.__dict__.items():
        if isinstance(child, str):
            meta[name] = child
    return meta


type_str = {
    DataSeriesType.NONE: "NONE",
    DataSeriesType.SCALAR: "SCALAR",
    DataSeriesType.VECTOR: "VECTOR",
    DataSeriesType.SPECTROGRAM: "SPECTROGRAM",
    DataSeriesType.MULTICOMPONENT: "MULTICOMPONENT"
}


def make_product(path, node):
    p_type = data_serie_type(node)
    comp = count_components(node)
    meta = get_node_meta(node)
    meta["xmlid"] = node.xmlid
    meta["components"] = str(comp)
    meta["type"] = type_str[p_type]
    return Product(path, [], p_type, meta)


class SpeasyPlugin(DataProvider):
    def __init__(self, parent=None):
        super(SpeasyPlugin, self).__init__(parent)
        leaves = {}
        explore_nodes(amda, 'amda', leaves)
        self.products = {
            node.xmlid: make_product(path, node)
            for path, node in leaves.items()
        }
        self.register_products(list(self.products.values()))

    def get_data(self, metadata, start, stop):
        p = self.products[metadata["xmlid"]]
        v = spz.get_data("amda/" + metadata["xmlid"], start, stop)
        if p.ds_type == DataSeriesType.SCALAR:
            return ScalarTimeSerie(
                v.time, v.data
            ) if v else ScalarTimeSerie(np.array([]), np.array([]))
        if p.ds_type == DataSeriesType.VECTOR:
            return VectorTimeSerie(
                v.time, v.data
            ) if v else VectorTimeSerie(np.array([]), np.array([]))
        if p.ds_type == DataSeriesType.MULTICOMPONENT:
            return MultiComponentTimeSerie(
                v.time, v.data
            ) if v else MultiComponentTimeSerie(np.array([]), np.array([]))


def load(main_window):
    return SpeasyPlugin(main_window)
