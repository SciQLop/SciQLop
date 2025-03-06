import os
from typing import List, Dict, Any
from PySide6.QtGui import QIcon
import threading
import traceback
import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex, ComponentIndex
from speasy.products import SpeasyVariable

from SciQLop.backend import register_icon
from SciQLop.backend import sciqlop_logging
from SciQLop.backend.enums import ParameterType, GraphType
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder
from SciQLopPlots import ProductsModel, ProductsModelNode, ProductsModelNodeType

log = sciqlop_logging.getLogger(__name__)

register_icon("speasy", QIcon(":/icons/logo_speasy.png"))
register_icon("nasa", QIcon(":/icons/NASA.jpg"))
register_icon("amda", QIcon(":/icons/amda.png"))
register_icon("cluster", QIcon(":/icons/Cluster_mission_logo_pillars.jpg"))
register_icon("archive", QIcon(":/icons/theme/dataSourceRoot.png"))


def _current_thread_id():
    return threading.get_native_id()


class ThreadStorage:
    _storage: Dict[int, Dict[str, Any]] = {}

    def __init__(self):
        self._storage = {}

    def __getattr__(self, item):
        return self._storage.get(_current_thread_id(), {}).get(item, None)

    def __setattr__(self, key, value):
        tid = _current_thread_id()
        storage = self._storage
        if tid not in storage:
            storage[tid] = {}
        storage[tid][key] = value


def get_components(param: ParameterIndex) -> List[str] or None:
    import ast
    if param.spz_provider() == 'amda':
        components = list(
            map(lambda p: p.spz_name(), filter(lambda n: type(n) is ComponentIndex, param.__dict__.values())))
        if len(components) > 0:
            return components
        elif hasattr(param, 'display_type') and param.display_type.lower() == 'timeseries':
            return [param.spz_name()]
    if hasattr(param, 'LABL_PTR_1'):
        if type(param.LABL_PTR_1) is str:
            try:
                return ast.literal_eval(param.LABL_PTR_1)
            except:
                return param.LABL_PTR_1.split(',')
        elif type(param.LABL_PTR_1) is list:
            return param.LABL_PTR_1
    if hasattr(param, 'LABLAXIS') and type(param.LABLAXIS) is str:
        if param.LABLAXIS.startswith('['):
            return param.LABLAXIS.split(',')
        return [param.LABLAXIS]
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
        if (display_type or '').lower().strip().startswith('spectrogram'):
            return ParameterType.Spectrogram
        else:
            if components_cnt == 0 or components_cnt == 1:
                return ParameterType.Scalar
            if components_cnt == 3:
                return ParameterType.Vector
            return ParameterType.Multicomponents
    if 'amda' in param.spz_provider().lower():
        return ParameterType.Multicomponents  # should be a safe backup
    return ParameterType.NotAParameter


def get_node_meta(node):
    meta = {}
    for name, child in node.__dict__.items():
        if isinstance(child, str):
            if not name.startswith("_"):
                meta[name] = child
    return meta


def make_product(name, node: ParameterIndex, provider):
    p_type = data_serie_type(node)
    meta = get_node_meta(node)
    meta["uid"] = node.spz_uid()
    meta["components"] = get_components(node)
    meta["provider"] = node.spz_provider()
    meta["speasy_id"] = f"{node.spz_provider()}/{node.spz_uid()}"
    return ProductsModelNode(name, provider, meta, ProductsModelNodeType.PARAMETER, p_type)


def explore_nodes(inventory_node, product_node: ProductsModelNode, provider):
    for name, child in inventory_node.__dict__.items():
        if name and child:
            if hasattr(child, "name") and child.name != "AMDA":
                name = child.name
            if isinstance(child, ParameterIndex):
                product_node.add_child(make_product(name, child, provider=provider))
            elif hasattr(child, "__dict__"):
                meta = {}
                if hasattr(child, "desc"):
                    meta = {"description": child.desc}
                elif hasattr(child, "description"):
                    meta = {"description": child.description}
                cur_prod = ProductsModelNode(name, meta)
                product_node.add_child(cur_prod)
                explore_nodes(child, cur_prod, provider=provider)


def build_product_tree(root_node: ProductsModelNode, provider):
    ws_icons = {
        "amda": "amda",
        "ssc": "nasa",
        "cdaweb": "nasa",
        "cda": "nasa",
        "csa": "cluster",
        "archive": "archive"
    }
    for name, child in spz.inventories.tree.__dict__.items():
        node = ProductsModelNode(name, icon=ws_icons.get(name))
        root_node.add_child(node)
        explore_nodes(child, node, provider=provider)
    return root_node


class SpeasyPlugin(DataProvider):
    def __init__(self):
        super(SpeasyPlugin, self).__init__(name="Speasy", data_order=DataOrder.Y_FIRST, cacheable=True)
        from speasy.core.requests_scheduling.request_dispatch import init_providers
        init_providers()
        root_node = ProductsModelNode("speasy", icon="speasy")
        build_product_tree(root_node, provider=self.name)
        ProductsModel.instance().add_node([], root_node)

    def get_data(self, product: ProductsModelNode, start, stop):
        try:
            speasy_id = product.metadata("speasy_id")
            v: SpeasyVariable = spz.get_data(speasy_id, start, stop)
            if v:
                return v.replace_fillval_by_nan(inplace=True)
        except Exception as e:
            log.error(f"Error getting data for {product} between {start} and {stop}: {traceback.format_exc()}")
            return None

    def labels(self, node:ProductsModelNode) -> List[str]:
        return node.metadata("components")

    def graph_type(self, node:ProductsModelNode) -> GraphType:
        param_type:ParameterType = node.parameter_type()
        if param_type == ParameterType.Scalar:
            return GraphType.SingleLine
        if param_type == ParameterType.Vector:
            return GraphType.MultiLines
        if param_type == ParameterType.Spectrogram:
            return GraphType.ColorMap
        return GraphType.Unknown


def load(*args):
    from speasy.core.cache import _cache
    _cache._data._local = ThreadStorage()
    return SpeasyPlugin()
