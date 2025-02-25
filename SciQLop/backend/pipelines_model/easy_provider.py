import warnings

import numpy as np
from enum import Enum
from typing import Callable, List, Optional, Union, Tuple
from datetime import datetime, timezone
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis, VariableAxis
from PySide6.QtGui import QIcon
from SciQLop.backend.unique_names import make_simple_incr_name
from SciQLop.backend.models import products, ProductsModelNode, ProductsModelNodeType
from SciQLop.backend.enums import ParameterType
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder, DataProviderReturnType
from SciQLop.backend.icons import register_icon
from SciQLop.backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)

register_icon("Python-logo-notext", QIcon(":/icons/Python-logo-notext.png"))

VirtualProductCallback = Callable[[Union[float, datetime], Union[float, datetime]], DataProviderReturnType]


def ensure_dt64(x_data):
    if type(x_data) is np.ndarray:
        if x_data.dtype == np.dtype("datetime64[ns]"):
            return x_data
        elif x_data.dtype == np.float64:
            return (x_data * 1e9).astype("datetime64[ns]")
    raise ValueError(f"can't handle x axis type {type(x_data)}")

ArgumentsType = Enum("ArgumentsType",["Float", "Datetime","Unknown"])

def _arguments_type(callback: VirtualProductCallback)->ArgumentsType:
    if len(callback.__annotations__) >=2:
        if all(map(lambda x: x is float, list(callback.__annotations__.values())[:2])):
            return ArgumentsType.Float
        if all(map(lambda x: x is datetime, list(callback.__annotations__.values())[:2])):
            return ArgumentsType.Datetime
    return ArgumentsType.Unknown


def _returns_speasy_variable(callback: VirtualProductCallback):
    return callback.__annotations__.get("return") == SpeasyVariable


def _to_datetime(start: float, stop: float) -> Tuple[datetime, datetime]:
    return datetime.fromtimestamp(start, tz=timezone.utc), datetime.fromtimestamp(stop, tz=timezone.utc)


class EasyProvider(DataProvider):
    def __init__(self, path, callback: VirtualProductCallback, parameter_type: ParameterType, metadata: dict,
                 data_order=DataOrder.Y_FIRST,
                 cacheable=False, debug=False):
        super(EasyProvider, self).__init__(name=make_simple_incr_name(callback.__name__), data_order=data_order,
                                           cacheable=cacheable)
        self._path = path.split('/')
        product_name = self._path[-1]
        product_path = self._path[:-1]
        metadata.update(
            {"description": f"Virtual {parameter_type.name} product built from Python function: {callback.__name__}"})
        products.add_node(
            product_path,
            ProductsModelNode(product_name, self.name, metadata, ProductsModelNodeType.PARAMETER, parameter_type, "",
                              None)
        )
        arguments_type = _arguments_type(callback)
        if arguments_type == ArgumentsType.Datetime:
            if debug:
                self._user_get_data = lambda start, stop: self._debug_get_data(callback, *_to_datetime(start, stop))
            else:
                self._user_get_data = lambda start, stop: callback(*_to_datetime(start, stop))
        else:
            if arguments_type == ArgumentsType.Unknown:
                warnings.warn(f"""Can't determine arguments type for {callback.__name__}, missing type hints, assuming float by default.
Please add type hints to the callback function to avoid this warning:
def {callback.__name__}(start: float, stop: float) -> Optional[SpeasyVariable]:
    ...
Or:
def {callback.__name__}(start: datetime, stop: datetime) -> Optional[SpeasyVariable]:
    ...
""")
            if debug:
                self._user_get_data = lambda start, stop: self._debug_get_data(callback, start, stop)
            else:
                self._user_get_data = callback

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
