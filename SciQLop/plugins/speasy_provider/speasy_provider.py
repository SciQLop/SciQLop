import os
from typing import List, Optional
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
from SciQLop.core import tracing
from SciQLop.core.plot_hints import PlotHints
from SciQLop.core.istp_hints import istp_metadata_to_hints
from SciQLop.core.speasy_hints import variable_as_istp_meta
from SciQLop import __version__ as sciqlop_version
from SciQLopPlots import ProductsModel, ProductsModelNode, ProductsModelNodeType

log = sciqlop_logging.getLogger(__name__)

__here__ = os.path.dirname(__file__)

def _register_icons():
    register_icon("speasy", QIcon(":/icons/logo_speasy.png"))
    register_icon("nasa", QIcon(":/icons/NASA.jpg"))
    register_icon("amda", QIcon(":/icons/amda.png"))
    register_icon("cluster", QIcon(":/icons/Cluster_mission_logo_pillars.jpg"))
    register_icon("archive", QIcon(":/icons/theme/dataSourceRoot.png"))
    register_icon("uiowaephtool", QIcon(f"{__here__}/../../resources/icons/Iowa_Hawkeyes_logo.svg"))
    register_icon("cloud", lambda: QIcon(f"{__here__}/../../resources/icons/cloud.png"))


def _is_ssc_index(index) -> bool:
    provider = getattr(index, "spz_provider", None)
    return bool(provider) and provider() == "ssc"


def _speasy_id_is_ssc(speasy_id) -> bool:
    return isinstance(speasy_id, str) and speasy_id.split("/", 1)[0] == "ssc"


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
    """Drop-in replacement for threading.local() that survives thread death.

    Works around https://github.com/grantjenks/python-diskcache/issues/295:
    diskcache stores per-thread SQLite connections on `_cache._data._local`,
    and recycled pool threads (same native id, fresh threading.local state)
    cause connection thrash and SQLite lock races. Keying off
    threading.get_native_id() in a process-global dict lets the connection
    persist across thread death and be reused.

    diskcache only sets `pid` and `con` here — that's all the surface needed.
    """

    def __init__(self):
        object.__setattr__(self, "_storage", {})

    def __getattr__(self, item):
        return self._storage.get(_current_thread_id(), {}).get(item)

    def __setattr__(self, key, value):
        self._storage.setdefault(_current_thread_id(), {})[key] = value

    def __delattr__(self, key):
        self._storage.get(_current_thread_id(), {}).pop(key, None)


def get_components(param: ParameterIndex) -> Optional[List[str]]:
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


def _resolve_iso_range(graph) -> tuple:
    """Return (start_iso, stop_iso) for the snippet. Reads the live time-
    axis range from the graph's parent plot when available, falling back
    to "now − 1d → now" UTC.
    """
    from datetime import datetime, timedelta, timezone
    rng = None
    if graph is not None:
        try:
            from SciQLop.core.graph_context import graph_time_range
            rng = graph_time_range(graph)
        except Exception:
            rng = None
    if rng is not None:
        t0, t1 = rng
        start = datetime.fromtimestamp(t0, tz=timezone.utc).replace(microsecond=0).isoformat()
        stop = datetime.fromtimestamp(t1, tz=timezone.utc).replace(microsecond=0).isoformat()
        return start, stop
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return (now - timedelta(days=1)).isoformat(), now.isoformat()


def _speasy_sciqlop_snippet(ctx, graph=None) -> str:
    """Snippet that recreates the panel + plot inside SciQLop using the
    live panel time range when available."""
    from SciQLop.core.snippets import render_snippet, format_product_path
    start_iso, stop_iso = _resolve_iso_range(graph)
    product_path = format_product_path(ctx.product_path) or ctx.speasy_id
    return render_snippet(
        "sciqlop_reproducer.j2",
        start_iso=start_iso,
        stop_iso=stop_iso,
        product_path=product_path,
        knobs=repr(ctx.knobs) if ctx.knobs else None,
    )


def _speasy_matplotlib_snippet(ctx, graph=None) -> str:
    """Standalone notebook snippet: speasy.get_data + matplotlib plot."""
    from SciQLop.core.snippets import render_snippet
    start_iso, stop_iso = _resolve_iso_range(graph)
    return render_snippet(
        "notebook_matplotlib.j2",
        start_iso=start_iso,
        stop_iso=stop_iso,
        speasy_id=ctx.speasy_id,
        knobs=repr(ctx.knobs) if ctx.knobs else None,
    )


def _index_to_dict(index) -> dict:
    """Best-effort flatten of a speasy ParameterIndex into a JSON-friendly dict.

    Walks public attributes; skips callables and underscore-prefixed names.
    Falls back to `{"__repr__": repr(index)}` if attribute access raises.
    """
    out = {}
    try:
        for attr in dir(index):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(index, attr)
            except Exception:
                continue
            if callable(value):
                continue
            if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                out[attr] = value
    except Exception:
        out["__repr__"] = repr(index)
    return out


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
            provider, uid = speasy_id.split("/", 1)
            provider_fi = getattr(spz.inventories.flat_inventories, provider, None)
            if provider_fi is None:
                return None
            return provider_fi.parameters.get(uid)
        except Exception:
            return None

    def get_knobs(self, product) -> list:
        index = self._resolve_index(product)
        if index is None:
            return []
        out = []
        # SSC products take a top-level `coordinate_system` kwarg in
        # `spz.get_data` (default 'gse'); speasy doesn't model it as an
        # ArgumentListIndex, so we synthesize the knob ourselves.
        if _is_ssc_index(index):
            out.append(ChoiceKnob(
                name="coordinate_system", label="Coordinate system",
                default="gse",
                choices=(("GSE", "gse"), ("GSM", "gsm"), ("SM", "sm"),
                         ("GEO", "geo"), ("GM", "gm"),
                         ("GEI_TOD", "gei_tod"), ("GEI_J_2000", "gei_j_2000")),
            ))
        args_node = _find_argument_list(index)
        if args_node is not None:
            for arg in args_node:
                spec = _argument_to_knob(arg)
                if spec is not None:
                    out.append(spec)
        return out

    def get_data(self, product, start, stop, knobs=None):
        try:
            speasy_id = product.metadata("speasy_id") if hasattr(product, "metadata") else product
            kwargs = {}
            knob_values = dict(knobs) if knobs else {}
            # Pull top-level speasy kwargs (currently only SSC's
            # coordinate_system) out of the knob dict so they're not
            # smuggled into product_inputs (AMDA template parameters).
            coord = knob_values.pop("coordinate_system", None)
            if coord is not None and _speasy_id_is_ssc(speasy_id):
                kwargs["coordinate_system"] = coord
            if knob_values:
                kwargs["product_inputs"] = knob_values
            with tracing.zone("speasy.get_data", cat="speasy",
                              speasy_id=str(speasy_id),
                              start=float(start), stop=float(stop),
                              n_seconds=float(stop) - float(start)):
                v: SpeasyVariable = spz.get_data(speasy_id, start, stop, **kwargs)
            n_points = int(len(v)) if v is not None else 0
            n_bytes = int(v.values.nbytes) if v is not None else 0
            tracing.counter("speasy.points", n_points, cat="speasy")
            tracing.counter("speasy.bytes", n_bytes, cat="speasy")
            if v:
                with tracing.zone("speasy.fill_nan", cat="speasy",
                                  speasy_id=str(speasy_id),
                                  n_points=n_points, n_bytes=n_bytes):
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

    def python_snippets(self, ctx, graph=None) -> dict:
        if ctx.kind != "speasy" or not ctx.speasy_id:
            return {}
        return {
            "Reproduce in SciQLop": _speasy_sciqlop_snippet(ctx, graph),
            "Notebook (matplotlib)": _speasy_matplotlib_snippet(ctx, graph),
        }

    def extended_metadata(self, ctx) -> dict:
        if ctx.kind != "speasy" or not ctx.speasy_id:
            return {}
        index = self._resolve_index(ctx.speasy_id)
        if index is None:
            return {}
        return {
            "speasy_id": ctx.speasy_id,
            "inventory": _index_to_dict(index),
            "parameter_type": (str(getattr(index, "parameter_type", ""))
                                or None),
        }


def load(*args):
    from speasy.core.cache import _cache
    from .speasy_catalog_provider import SpeasyCatalogProvider
    _cache._data._local = ThreadStorage()
    _register_icons()
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
