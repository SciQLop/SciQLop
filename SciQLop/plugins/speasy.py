from SciQLopBindings import DataProvider, Product, ScalarTimeSerie, VectorTimeSerie, MultiComponentTimeSerie
from SciQLopBindings import SciQLopCore, MainWindow, TimeSyncPanel, ProductsTree, DataSeriesType
import numpy as np

from SciQLop.backend.products_model import ProductNode
from SciQLop.backend import products

from typing import Dict
import speasy as spz
from speasy.products import SpeasyVariable
from speasy.core.inventory.indexes import ParameterIndex, ComponentIndex, SpeasyIndex
from datetime import datetime


def count_components(param: ParameterIndex):
    if hasattr(param, "size"):
        return int(param.size)
    if hasattr(param, 'LABL_PTR_1'):
        return len(param.LABL_PTR_1.split(','))
    if hasattr(param, 'LABLAXIS'):
        return len(param.LABLAXIS.split(','))
    if hasattr(param, 'array_dimension') and param.array_dimension != "":
        return int(param.array_dimension.split(':')[-1])
    if param.spz_provider() == 'ssc':
        return 3
    return 0


def data_serie_type(param: ParameterIndex):
    if hasattr(param, "display_type"):
        display_type = param.display_type
    elif hasattr(param, "DISPLAY_TYPE"):
        display_type = param.DISPLAY_TYPE
    elif param.spz_provider() == 'ssc':
        display_type = 'timeseries'
    else:
        display_type = None
    components_cnt = count_components(param)
    if display_type is not None or components_cnt != 0:
        if display_type == 'spectrogram':
            return DataSeriesType.SPECTROGRAM
        else:
            if components_cnt == 0 or components_cnt == 1:
                return DataSeriesType.SCALAR
            if components_cnt == 3:
                return DataSeriesType.VECTOR
            return DataSeriesType.MULTICOMPONENT

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


def make_product(name, node: ParameterIndex):
    p_type = data_serie_type(node)
    comp = count_components(node)
    meta = get_node_meta(node)
    meta["uid"] = node.spz_uid()
    meta["components"] = str(comp)
    meta["type"] = type_str[p_type]
    meta["provider"] = node.spz_provider()
    return ProductNode(name, meta, is_parameter=True)


def explore_nodes(inventory_node, product_node: ProductNode):
    for name, child in inventory_node.__dict__.items():
        if name and child:
            if isinstance(child, ParameterIndex):
                product_node.append_child(make_product(name, child))
            elif hasattr(child, "__dict__"):
                cur_prod = ProductNode(name, {})
                product_node.append_child(cur_prod)
                explore_nodes(child, cur_prod)


class SpeasyPlugin(DataProvider):
    def __init__(self, parent=None):
        super(SpeasyPlugin, self).__init__(parent)
        root_node = ProductNode(name="speasy", metadata={})
        explore_nodes(spz.inventories.tree, root_node)
        products.add_products(root_node)

    def get_data(self, metadata, start, stop):
        print(metadata)
        p = self.products[metadata["uid"]]
        print(p, metadata["uid"], metadata["provider"], datetime.utcfromtimestamp(start),
              datetime.utcfromtimestamp(stop))
        try:
            v: SpeasyVariable = spz.get_data(metadata["provider"] + "/" + metadata["uid"],
                                             datetime.utcfromtimestamp(start),
                                             datetime.utcfromtimestamp(stop))
            print(f"got data: {v}")
            if v:
                v.replace_fillval_by_nan(inplace=True)
        except Exception as e:
            print(e)
            return None
        if p.ds_type == DataSeriesType.SCALAR:
            return ScalarTimeSerie(
                v.time.astype(np.timedelta64) / np.timedelta64(1, 's'), v.values.astype(np.float)
            ) if v else ScalarTimeSerie(np.array([]), np.array([]))
        if p.ds_type == DataSeriesType.VECTOR:
            return VectorTimeSerie(
                v.time.astype(np.timedelta64) / np.timedelta64(1, 's'), v.values.astype(np.float)
            ) if v else VectorTimeSerie(np.array([]), np.array([]))
        if p.ds_type == DataSeriesType.MULTICOMPONENT:
            return MultiComponentTimeSerie(
                v.time.astype(np.timedelta64) / np.timedelta64(1, 's'), v.values.astype(np.float)
            ) if v else MultiComponentTimeSerie(np.array([]), np.array([]))


def load(main_window):
    return SpeasyPlugin(main_window)
