from typing import List
from PySide6.QtGui import QIcon
import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex, ComponentIndex
from speasy.products import SpeasyVariable

from SciQLop.backend import Product, register_icon
from SciQLop.backend.enums import ParameterType
from SciQLop.backend.models import products
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder

register_icon("speasy", QIcon(":/icons/logo_speasy.svg"))
register_icon("nasa", QIcon(":/icons/NASA.jpg"))
register_icon("amda", QIcon(":/icons/amda.png"))
register_icon("cluster", QIcon(":/icons/Cluster_mission_logo_pillars.jpg"))
register_icon("archive", QIcon(":/icons/theme/dataSourceRoot.png"))


def get_components(param: ParameterIndex) -> List[str] or None:
    if param.spz_provider() == 'amda':
        components = list(
            map(lambda p: p.spz_name(), filter(lambda n: type(n) is ComponentIndex, param.__dict__.values())))
        if len(components) > 0:
            return components
    if hasattr(param, 'LABL_PTR_1') and type(param.LABL_PTR_1) is str:
        return param.LABL_PTR_1.split(',')
    if hasattr(param, 'LABLAXIS') and type(param.LABLAXIS) is str:
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
    if 'amda' in param.spz_provider().lower():
        return ParameterType.MULTICOMPONENT  # should be a safe backup
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
            if hasattr(child, "name") and child.name != "AMDA":
                name = child.name
            if isinstance(child, ParameterIndex):
                product_node.merge(make_product(name, child, provider=provider))
            elif hasattr(child, "__dict__"):
                meta = {}
                if hasattr(child, "desc"):
                    meta = {"description": child.desc}
                elif hasattr(child, "description"):
                    meta = {"description": child.description}
                cur_prod = Product(name, metadata=meta, uid=name, provider=provider)
                product_node.merge(cur_prod)
                explore_nodes(child, cur_prod, provider=provider)


def build_product_tree(root_node: Product, provider):
    ws_icons = {
        "amda": "amda",
        "ssc": "nasa",
        "cdaweb": "nasa",
        "cda": "nasa",
        "csa": "cluster",
        "archive": "archive"
    }
    for name, child in spz.inventories.tree.__dict__.items():
        node = root_node.merge(Product(name=name, metadata={}, provider=name, uid=name, icon=ws_icons.get(name)))
        explore_nodes(child, node, provider=provider)

    return root_node


class SpeasyPlugin(DataProvider):
    def __init__(self):
        super(SpeasyPlugin, self).__init__(name="Speasy", data_order=DataOrder.Y_FIRST, cacheable=True)
        root_node = Product(name="speasy", metadata={}, provider=self.name, uid=self.name, icon="speasy")
        build_product_tree(root_node, provider=self.name)
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
