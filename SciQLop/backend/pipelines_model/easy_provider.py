import numpy as np
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis, VariableAxis
from PySide6.QtGui import QIcon
from typing import List
from SciQLop.backend import Product
from SciQLop.backend.unique_names import make_simple_incr_name
from SciQLop.backend.models import products
from SciQLop.backend.enums import ParameterType
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder
from SciQLop.backend.icons import register_icon

register_icon("Python-logo-notext", QIcon(":/icons/Python-logo-notext.svg"))


def ensure_dt64(x_data):
    if type(x_data) is np.ndarray:
        if x_data.dtype == np.dtype("datetime64[ns]"):
            return x_data
        elif x_data.dtype == np.float64:
            return (x_data * 1e9).astype("datetime64[ns]")
    raise ValueError(f"can't handle x axis type {type(x_data)}")


class EasyProvider(DataProvider):
    def __init__(self, path, callback, parameter_type: ParameterType, metadata: dict, data_order=DataOrder.Y_FIRST,
                 cacheable=False):
        super(EasyProvider, self).__init__(name=make_simple_incr_name(callback.__name__), data_order=data_order,
                                           cacheable=cacheable)
        product_name = path.split('/')[-1]
        product_path = path[:-len(product_name)]
        self._path = path
        metadata.update(
            {"description": f"Virtual {parameter_type.name} product built from Python function: {callback.__name__}"})
        products.add_product(
            path=product_path,
            product=Product(name=product_name, is_parameter=True, uid=product_name, provider=self.name,
                            parameter_type=parameter_type, metadata=metadata, icon="Python-logo-notext",
                            deletable=True), deletable_parent_nodes=True)
        self._user_get_data = callback

    def get_data(self, product, start, stop):
        return self._user_get_data(start, stop)

    @property
    def path(self):
        return self._path


class EasyScalar(EasyProvider):
    def __init__(self, path, get_data_callback, component_name: str, metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False):
        super(EasyScalar, self).__init__(path=path, callback=get_data_callback, parameter_type=ParameterType.SCALAR,
                                         metadata={**metadata, "components": component_name}, data_order=data_order,
                                         cacheable=cacheable)
        self._columns = [component_name]

    def get_data(self, product, start, stop):
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
    def __init__(self, path, get_data_callback, components_names: List[str], metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False):
        super(EasyVector, self).__init__(path=path, callback=get_data_callback, parameter_type=ParameterType.VECTOR,
                                         metadata={**metadata, "components": ';'.join(components_names)},
                                         data_order=data_order, cacheable=cacheable)
        self._columns = components_names

    def get_data(self, product, start, stop):
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


class EasyMultiComponent(EasyVector):
    def __init__(self, path, get_data_callback, components_names: List[str], metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False):
        super(EasyVector, self).__init__(path=path, callback=get_data_callback,
                                         parameter_type=ParameterType.MULTICOMPONENT,
                                         metadata={**metadata, "components": ';'.join(components_names)},
                                         data_order=data_order, cacheable=cacheable)
        self._columns = components_names


class EasySpectrogram(EasyProvider):
    def __init__(self, path, get_data_callback, metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST, cacheable=False):
        super(EasySpectrogram, self).__init__(path=path, callback=get_data_callback,
                                              parameter_type=ParameterType.SPECTROGRAM,
                                              metadata={**metadata},
                                              data_order=data_order,
                                              cacheable=cacheable)

    def get_data(self, product, start, stop):
        res = self._user_get_data(start, stop)
        if type(res) is SpeasyVariable:
            return res
        elif type(res) is tuple:
            x, y, z = res
            return SpeasyVariable(axes=[VariableTimeAxis(ensure_dt64(x)), VariableAxis(np.ascontiguousarray(y))],
                                  values=DataContainer(np.ascontiguousarray(z)))
        else:
            return None
