from typing import List

import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex, ComponentIndex
from speasy.products import SpeasyVariable

from SciQLop.backend import Product
from SciQLop.backend.enums import ParameterType
from SciQLop.backend.models import products
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder


def get_components(param: ParameterIndex) -> List[str] or None:
    if param.spz_provider() == 'amda':
        components = list(
            map(lambda p: p.spz_name(), filter(lambda n: type(n) is ComponentIndex, param.__dict__.values())))
        if len(components) > 0:
            return components
    if hasattr(param, 'LABL_PTR_1'):
        return param.LABL_PTR_1.split(',')
    if hasattr(param, 'LABLAXIS'):
        return param.LABLAXIS.split(',')
    if param.spz_provider() == 'ssc':
        return ['x', 'y', 'z']
    return None


def count_components(param: ParameterIndex):
    labels = get_components(param)
    if labels is not None:
        return len(labels)
    if hasattr(param, "size"):
        return int(param.size)
    if hasattr(param, 'array_dimension') and param.array_dimension != "":
        return int(param.array_dimension.split(':')[-1])
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
        if (display_type or '').lower().strip() == 'spectrogram':
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
    meta = get_node_meta(node)
    meta["uid"] = node.spz_uid()
    meta["components"] = get_components(node)
    meta["provider"] = node.spz_provider()
    return Product(name, metadata=meta, is_parameter=True, provider=provider,
                   uid=f"{node.spz_provider()}/{node.spz_uid()}", parameter_type=p_type)


def explore_nodes(inventory_node, product_node: Product, provider):
    for name, child in inventory_node.__dict__.items():
        if name and child:
            if isinstance(child, ParameterIndex):
                product_node.append_child(make_product(name, child, provider=provider))
            elif hasattr(child, "__dict__"):
                cur_prod = Product(name, metadata={}, uid=name, provider=provider)
                product_node.append_child(cur_prod)
                explore_nodes(child, cur_prod, provider=provider)


class SpeasyPlugin(DataProvider):
    def __init__(self):
        super(SpeasyPlugin, self).__init__(name="Speasy", data_order=DataOrder.Y_FIRST)
        root_node = Product(name="speasy", metadata={}, provider=self.name, uid=self.name)
        explore_nodes(spz.inventories.tree, root_node, provider=self.name)
        products.add_products(root_node)

    def get_data(self, product: Product, start, stop):
        try:
            v: SpeasyVariable = spz.get_data(product.uid, start, stop)
            if v:
                v.replace_fillval_by_nan(inplace=True)
                return v
        except Exception as e:
            print(e)
            return None


def load(*args):
    return SpeasyPlugin()
