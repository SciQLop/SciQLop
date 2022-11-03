import numpy as np

from SciQLop.backend.products_model import ProductNode, ParameterType
from SciQLop.backend import products
from SciQLop.backend.data_provider import DataProvider, DataOrder
from typing import Dict
import speasy as spz
from speasy.products import SpeasyVariable
from speasy.core.inventory.indexes import ParameterIndex, ComponentIndex, SpeasyIndex
from datetime import datetime
from enum import Enum


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
            return ParameterType.SPECTROGRAM
        else:
            if components_cnt == 0 or components_cnt == 1:
                return ParameterType.SCALAR
            if components_cnt == 3:
                return ParameterType.VECTOR
            return ParameterType.MULTICOMPONENT

    return ParameterType.NONE


def get_node_meta(node):
    meta = {}
    for name, child in node.__dict__.items():
        if isinstance(child, str):
            meta[name] = child
    return meta


def make_product(name, node: ParameterIndex, provider):
    p_type = data_serie_type(node)
    comp = count_components(node)
    meta = get_node_meta(node)
    meta["uid"] = node.spz_uid()
    meta["components"] = str(comp)
    meta["provider"] = node.spz_provider()
    return ProductNode(name, metadata=meta, is_parameter=True, provider=provider,
                       uid=f"{node.spz_provider()}/{node.spz_uid()}", parameter_type=p_type)


def explore_nodes(inventory_node, product_node: ProductNode, provider):
    for name, child in inventory_node.__dict__.items():
        if name and child:
            if isinstance(child, ParameterIndex):
                product_node.append_child(make_product(name, child, provider=provider))
            elif hasattr(child, "__dict__"):
                cur_prod = ProductNode(name, metadata={}, uid=name, provider=provider)
                product_node.append_child(cur_prod)
                explore_nodes(child, cur_prod, provider=provider)


class SpeasyPlugin(DataProvider):
    def __init__(self, parent=None):
        super(SpeasyPlugin, self).__init__(name="Speasy", parent=parent, data_order=DataOrder.ROW_MAJOR)
        root_node = ProductNode(name="speasy", metadata={}, provider=self.name, uid=self.name)
        explore_nodes(spz.inventories.tree, root_node, provider=self.name)
        products.add_products(root_node)

    def get_data(self, product, start, stop):
        try:
            v: SpeasyVariable = spz.get_data(product, start, stop)
            # print(f"got data: {v}")
            if v:
                v.replace_fillval_by_nan(inplace=True)
        except Exception as e:
            print(e)
            return None
        if v:
            t = v.time.astype(np.timedelta64) / np.timedelta64(1, 's')
            values = v.values.astype(np.float)
            return t, values


def load(main_window):
    return SpeasyPlugin(main_window)
