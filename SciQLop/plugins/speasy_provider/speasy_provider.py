import os
from typing import List, Dict, Any, Optional
from PySide6.QtGui import QIcon
import threading
import traceback
import speasy as spz
from speasy.core.inventory.indexes import ParameterIndex, ComponentIndex, CatalogIndex, TimetableIndex, ArgumentListIndex
from speasy.products import SpeasyVariable

from SciQLop.user_api.knobs import KnobSpec, ChoiceKnob, IntKnob, FloatKnob, BoolKnob, StringKnob
from SciQLop.components.theming import register_icon, get_icon
from SciQLop.components import sciqlop_logging
from SciQLop.core.enums import ParameterType, GraphType
from SciQLop.components.plotting.backend.data_provider import DataProvider, DataOrder
from SciQLop.core.plot_hints import PlotHints
from SciQLop.core.istp_hints import istp_metadata_to_hints
from SciQLop.core.speasy_hints import variable_as_istp_meta
from SciQLop import __version__ as sciqlop_version
from SciQLopPlots import ProductsModel, ProductsModelNode, ProductsModelNodeType

log = sciqlop_logging.getLogger(__name__)

__here__ = os.path.dirname(__file__)

register_icon("speasy", QIcon(":/icons/logo_speasy.png"))
register_icon("nasa", QIcon(":/icons/NASA.jpg"))
register_icon("amda", QIcon(":/icons/amda.png"))
register_icon("cluster", QIcon(":/icons/Cluster_mission_logo_pillars.jpg"))
register_icon("archive", QIcon(":/icons/theme/dataSourceRoot.png"))
register_icon("uiowaephtool", QIcon(f"{__here__}/../../resources/icons/Iowa_Hawkeyes_logo.svg"))
register_icon("cloud", lambda: QIcon(f"{__here__}/../../resources/icons/cloud.png"))


def _find_argument_list(index) -> Optional[ArgumentListIndex]:
    if isinstance(index, ArgumentListIndex):
        return index
    for child in getattr(index, "__dict__", {}).values():
        if isinstance(child, ArgumentListIndex):
            return child
    return None


def _argument_to_knob(arg) -> Optional[KnobSpec]:
    key = getattr(arg, "key", None) or getattr(arg, "name", None) \
        or getattr(arg, "spz_name", lambda: "")()
    if not key:
        return None
    label = getattr(arg, "name", "") or key
    arg_type = (getattr(arg, "type", "") or "").lower()
    default = getattr(arg, "default", None)

    if arg_type in ("list", "generated-list"):
        raw_choices = getattr(arg, "choices", []) or []
        choices = []
        for c in raw_choices:
            if isinstance(c, tuple) and len(c) == 2:
                choices.append((str(c[0]), c[1]))
            else:
                choices.append((str(c), c))
        return ChoiceKnob(name=key, label=label, default=default,
                          choices=tuple(choices))

    if arg_type == "bool":
        return BoolKnob(name=key, label=label,
                        default=bool(default) if default is not None else False)
    if arg_type in ("int", "integer"):
        return IntKnob(name=key, label=label,
                       default=int(default) if default is not None else 0)
    if arg_type in ("float", "double"):
        return FloatKnob(name=key, label=label,
                         default=float(default) if default is not None else 0.0)
    if arg_type in ("string", "str", ""):
        return StringKnob(name=key, label=label,
                          default=str(default) if default is not None else "")
    return None


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
            except (ValueError, SyntaxError):
                return param.LABL_PTR_1.split(',')
        elif type(param.LABL_PTR_1) is list:
            return param.LABL_PTR_1
    if hasattr(param, 'LABLAXIS') and type(param.LABLAXIS) is str:
        if param.LABLAXIS.startswith('['):
            return param.LABLAXIS.split(',')
        return [param.LABLAXIS]
    if param.spz_provider() in ('ssc', 'UiowaEphTool'):
        return ['x', 'y', 'z']
    return [param.spz_name()]


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
    elif param.spz_provider() in ('ssc', 'UiowaEphTool'):
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
        if name.startswith("_"):
            continue
        if isinstance(child, (str, int, float)):
            meta[name] = child
        elif isinstance(child, (list, tuple)) and all(
            isinstance(v, (str, int, float)) for v in child
        ):
            meta[name] = list(child)
    return meta


def make_product(name, node: ParameterIndex, provider):
    p_type = data_serie_type(node)
    meta = get_node_meta(node)
    meta["uid"] = node.spz_uid()
    meta["components"] = get_components(node)
    meta["provider"] = node.spz_provider()
    meta["speasy_id"] = f"{node.spz_provider()}/{node.spz_uid()}"
    meta["stable_id"] = meta["speasy_id"]
    return ProductsModelNode(name, provider, meta, ProductsModelNodeType.PARAMETER, p_type)


def explore_nodes(inventory_node, product_node: ProductsModelNode, provider):
    for name, child in inventory_node.__dict__.items():
        if name and child:
            if hasattr(child, "name") and child.name != "AMDA":
                name = child.name
            if isinstance(child, (CatalogIndex, TimetableIndex)):
                continue
            elif isinstance(child, ParameterIndex):
                product_node.add_child(make_product(name, child, provider=provider))
            elif hasattr(child, "__dict__"):
                meta = {}
                if hasattr(child, "desc"):
                    meta = {"description": child.desc}
                elif hasattr(child, "description"):
                    meta = {"description": child.description}
                cur_prod = ProductsModelNode(name, meta)
                explore_nodes(child, cur_prod, provider=provider)
                if cur_prod.children_count() > 0:
                    product_node.add_child(cur_prod)


def build_product_tree(root_node: ProductsModelNode, provider):
    ws_icons = {
        "amda": "amda",
        "ssc": "nasa",
        "cdaweb": "nasa",
        "cda": "nasa",
        "csa": "cluster",
        "archive": "archive",
        "uiowaephtool": "uiowaephtool",
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
        import speasy.core.http as http
        http.USER_AGENT = f"SciQLop/{sciqlop_version}/{http.USER_AGENT}"
        init_providers()
        root_node = ProductsModelNode("speasy", icon="speasy")
        build_product_tree(root_node, provider=self.name)
        ProductsModel.instance().add_node([], root_node)

    def _resolve_index(self, product):
        if hasattr(product, "metadata"):
            speasy_id = product.metadata("speasy_id")
        else:
            speasy_id = product
        if not speasy_id:
            return None
        try:
            return spz.inventories.flat_inventories.parameters.get(speasy_id)
        except Exception:
            return None

    def get_knobs(self, product) -> list:
        index = self._resolve_index(product)
        if index is None:
            return []
        args_node = _find_argument_list(index)
        if args_node is None:
            return []
        out = []
        for arg in args_node:
            spec = _argument_to_knob(arg)
            if spec is not None:
                out.append(spec)
        return out

    def get_data(self, product, start, stop, knobs=None):
        try:
            speasy_id = product.metadata("speasy_id") if hasattr(product, "metadata") else product
            kwargs = {"product_inputs": dict(knobs)} if knobs else {}
            v: SpeasyVariable = spz.get_data(speasy_id, start, stop, **kwargs)
            if v:
                return v.replace_fillval_by_nan(inplace=True, convert_to_float=True)
        except Exception:
            log.error(f"Error getting data for {product} between {start} and {stop}: {traceback.format_exc()}")
            return None

    def labels(self, node: ProductsModelNode) -> List[str]:
        return node.metadata("components")

    def graph_type(self, node: ProductsModelNode) -> GraphType:
        param_type: ParameterType = node.parameter_type()
        if param_type == ParameterType.Scalar:
            return GraphType.SingleLine
        if param_type == ParameterType.Vector:
            return GraphType.MultiLines
        if param_type == ParameterType.Spectrogram:
            return GraphType.ColorMap
        return GraphType.Unknown

    def plot_hints(self, node: ProductsModelNode) -> PlotHints:
        try:
            return istp_metadata_to_hints(node.metadata())
        except Exception:
            log.debug("plot_hints failed for %s", node, exc_info=True)
            return PlotHints()

    def plot_hints_from_variable(self, node: ProductsModelNode, variable: SpeasyVariable) -> PlotHints:
        try:
            meta = variable_as_istp_meta(variable)
            if self.graph_type(node) == GraphType.ColorMap:
                meta.setdefault("DISPLAY_TYPE", "spectrogram")
            return istp_metadata_to_hints(meta)
        except Exception:
            log.debug("plot_hints_from_variable failed for %s", node, exc_info=True)
            return PlotHints()


def load(*args):
    from speasy.core.cache import _cache
    from .speasy_catalog_provider import SpeasyCatalogProvider
    _cache._data._local = ThreadStorage()
    plugin = SpeasyPlugin()
    plugin._catalog_provider = SpeasyCatalogProvider()
    _register_plot_backend()
    return plugin


def _register_plot_backend():
    try:
        import speasy.plotting as splt
        from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
        from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings

        splt.__backends__["sciqlop"] = SciQLopBackend
        if PlotBackendSettings().default_speasy_backend == "sciqlop":
            splt.__backends__[None] = SciQLopBackend
    except Exception as e:
        from SciQLop.components.sciqlop_logging import getLogger
        getLogger(__name__).debug(f"Could not register SciQLop plot backend: {e}")
