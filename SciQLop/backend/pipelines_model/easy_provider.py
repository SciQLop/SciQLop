import warnings

import numpy as np
from enum import Enum
from typing import Callable, List, Optional, Union, Tuple
from datetime import datetime, timezone
from expression import compose
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis, VariableAxis
from PySide6.QtGui import QIcon
from SciQLop.backend.unique_names import make_simple_incr_name
from SciQLop.backend.models import products, ProductsModelNode, ProductsModelNodeType
from SciQLop.backend.enums import ParameterType
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder, DataProviderReturnType
from SciQLop.backend.icons import register_icon
from SciQLop.backend import sciqlop_logging
from inspect import signature

log = sciqlop_logging.getLogger(__name__)

register_icon("Python-logo-notext", QIcon(":/icons/Python-logo-notext.png"))

VirtualProductCallback = Callable[
    [Union[float, datetime, np.datetime64], Union[float, datetime, np.datetime64]], DataProviderReturnType]


def ensure_dt64(x_data):
    if type(x_data) is np.ndarray:
        if x_data.dtype == np.dtype("datetime64[ns]"):
            return x_data
        elif x_data.dtype == np.float64:
            return (x_data * 1e9).astype("datetime64[ns]")
    raise ValueError(f"can't handle x axis type {type(x_data)}")


class ArgumentsType(Enum):
    Float = 0
    Datetime = 1
    Datetime64 = 2
    Unknown = 3


def _positional_args_types(callback: VirtualProductCallback) -> List[type]:
    """
    Get the annotations of the callback function.
    :param callback: The callback function
    :return: A dictionary of annotations
    """

    sig = signature(callback, eval_str=True)
    return [
        v.annotation for v in sig.parameters.values() if v.default == v.empty
    ]


def _arguments_type(callback: VirtualProductCallback) -> ArgumentsType:
    pos_arg_types = _positional_args_types(callback)
    all_are = lambda types, expected: all(map(lambda x: x is expected, pos_arg_types))
    if len(pos_arg_types) >= 2:
        if all_are(pos_arg_types[:2], float):
            return ArgumentsType.Float
        if all_are(pos_arg_types[:2], datetime):
            return ArgumentsType.Datetime
        if all_are(pos_arg_types[:2], np.datetime64):
            return ArgumentsType.Datetime64
    return ArgumentsType.Unknown


def _name_callable(callback: VirtualProductCallback) -> str:
    # simple function
    if hasattr(callback, "__name__"):
        return callback.__name__
    # callable object
    elif hasattr(callback, "__class__") and hasattr(callback.__class__, "__name__"):
        return callback.__class__.__name__
    # lambda function
    elif hasattr(callback, "__code__") and hasattr(callback.__code__, "co_name"):
        return f"{callback.__code__.co_name} from {callback.__module__} at {callback.__code__.co_firstlineno}"
    # unknown
    return f"unknown callable {callback}"


def _returns_speasy_variable(callback: VirtualProductCallback):
    return callback.__annotations__.get("return") == SpeasyVariable


def _to_datetime(start: float, stop: float) -> Tuple[datetime, datetime]:
    return datetime.fromtimestamp(start, tz=timezone.utc), datetime.fromtimestamp(stop, tz=timezone.utc)


def _to_datetime64(start: float, stop: float) -> Tuple[np.datetime64, np.datetime64]:
    return np.datetime64(int(start * 1e9), "ns"), np.datetime64(int(stop * 1e9), "ns")


class EasyProvider(DataProvider):
    def __init__(self, path, callback: VirtualProductCallback, parameter_type: ParameterType, metadata: dict,
                 data_order=DataOrder.Y_FIRST,
                 cacheable=False, debug=False):
        super(EasyProvider, self).__init__(name=make_simple_incr_name(_name_callable(callback)), data_order=data_order,
                                           cacheable=cacheable)
        self._path = path.split('/')
        product_name = self._path[-1]
        product_path = self._path[:-1]
        metadata.update(
            {"description": f"Virtual {parameter_type.name} product built from Python function: {self.name}"})
        products.add_node(
            product_path,
            ProductsModelNode(product_name, self.name, metadata, ProductsModelNodeType.PARAMETER, parameter_type, "",
                              None)
        )
        stack = []
        arguments_type = _arguments_type(callback)
        match arguments_type:
            case ArgumentsType.Datetime:
                stack.append(lambda rng: _to_datetime(*rng))
            case ArgumentsType.Datetime64:
                stack.append(lambda rng: _to_datetime64(*rng))
            case ArgumentsType.Float:
                pass
            case ArgumentsType.Unknown:
                warnings.warn(f"""Can't determine arguments type for {self.name}, missing type hints, assuming float by default.
Please add type hints to the callback function to avoid this warning:
def {self.name}(start: float, stop: float) -> Optional[SpeasyVariable]:
    ...
Or:
def {self.name}(start: datetime, stop: datetime) -> Optional[SpeasyVariable]:
    ...
Or:
def {self.name}(start: np.datetime64, stop: np.datetime64) -> Optional[SpeasyVariable]:
    ...
            """)
        if debug:
            stack.append(lambda rng: self._debug_get_data(callback, *rng))
        else:
            stack.append(lambda rng: callback(*rng))
        self._user_get_data = lambda start, stop: compose(*stack)((start, stop))

    def get_data(self, product, start: float, stop: float) -> DataProviderReturnType:
        return self._user_get_data(start, stop)

    def _debug_get_data(self, callback, start, stop):
        try:
            return callback(start, stop)
        except Exception as e:
            log.error(f"Error in {self.name}: {e}")

    @property
    def path(self):
        return self._path

    def labels(self, node) -> List[str]:
        return node.metadata().get("components", "").split(';')


class EasyScalar(EasyProvider):
    def __init__(self, path, get_data_callback: VirtualProductCallback, component_name: str, metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False, debug=False):
        super(EasyScalar, self).__init__(path=path, callback=get_data_callback, parameter_type=ParameterType.Scalar,
                                         metadata={**metadata, "components": component_name}, data_order=data_order,
                                         cacheable=cacheable, debug=debug)
        self._columns = [component_name]

    def get_data(self, product, start: float, stop: float) -> DataProviderReturnType:
        res = self._user_get_data(start, stop)
        if type(res) is SpeasyVariable:
            return res
        elif type(res) is tuple:
            x, y = res
            return SpeasyVariable(axes=[VariableTimeAxis(ensure_dt64(x))],
                                  values=DataContainer(np.ascontiguousarray(y)),
                                  columns=self._columns)
        else:
            return None


class EasyVector(EasyProvider):
    def __init__(self, path, get_data_callback: VirtualProductCallback, components_names: List[str], metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False, debug=False):
        super(EasyVector, self).__init__(path=path, callback=get_data_callback, parameter_type=ParameterType.Vector,
                                         metadata={**metadata, "components": ';'.join(components_names)},
                                         data_order=data_order, cacheable=cacheable, debug=debug)
        self._columns = components_names

    def get_data(self, product, start: float, stop: float) -> Optional[DataProviderReturnType]:
        res = self._user_get_data(start, stop)
        if type(res) is SpeasyVariable:
            return res
        elif type(res) in (tuple, list) and len(res) == 2:
            x, y = res
            return SpeasyVariable(axes=[VariableTimeAxis(ensure_dt64(x))],
                                  values=DataContainer(np.ascontiguousarray(y)),
                                  columns=self._columns)
        elif type(res) in (tuple, list) and len(res) >= 3:
            return res
        else:
            return None


class EasyMultiComponent(EasyVector):
    def __init__(self, path, get_data_callback: VirtualProductCallback, components_names: List[str], metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False, debug=False):
        super(EasyVector, self).__init__(path=path, callback=get_data_callback,
                                         parameter_type=ParameterType.Multicomponents,
                                         metadata={**metadata, "components": ';'.join(components_names)},
                                         data_order=data_order, cacheable=cacheable, debug=debug)
        self._columns = components_names


class EasySpectrogram(EasyProvider):
    def __init__(self, path, get_data_callback: VirtualProductCallback, metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False, debug=False):
        super(EasySpectrogram, self).__init__(path=path, callback=get_data_callback,
                                              parameter_type=ParameterType.Spectrogram,
                                              metadata={**metadata},
                                              data_order=data_order,
                                              cacheable=cacheable,
                                              debug=debug)

    def get_data(self, product, start: float, stop: float) -> Optional[DataProviderReturnType]:
        res = self._user_get_data(start, stop)
        if type(res) is SpeasyVariable:
            return res
        elif type(res) is tuple:
            x, y, z = res
            return SpeasyVariable(axes=[VariableTimeAxis(ensure_dt64(x)), VariableAxis(np.ascontiguousarray(y))],
                                  values=DataContainer(np.ascontiguousarray(z)))
        else:
            return None
