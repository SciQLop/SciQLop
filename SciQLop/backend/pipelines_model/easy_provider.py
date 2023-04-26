import numpy as np
from speasy.products import SpeasyVariable, DataContainer, VariableTimeAxis
from typing import List
from SciQLop.backend import Product
from SciQLop.backend.unique_names import make_simple_incr_name
from SciQLop.backend.models import products
from SciQLop.backend.enums import ParameterType
from SciQLop.backend.pipelines_model.data_provider import DataProvider, DataOrder


def build_product_hierarchy(path: str, provider: DataProvider, parameter_type: ParameterType, metadata: dict):
    if path.startswith('/'):
        path = path[1:]
    elements = path.split('/')
    root_node = Product(name=f"{elements[0]}", metadata={}, provider=provider.name, uid=provider.name)
    current_node = root_node
    for e in elements[1:-1]:
        new_node = Product(name=f"{e}", metadata={}, provider=provider.name, uid=provider.name)
        current_node.append_child(new_node)
        current_node = new_node

    current_node.append_child(Product(name=elements[-1], metadata=metadata,
                                      provider=provider.name,
                                      uid=elements[-1],
                                      is_parameter=True,
                                      parameter_type=parameter_type))
    return root_node


class EasyProvider(DataProvider):
    def __init__(self, path, callback, parameter_type: ParameterType, metadata: dict, data_order=DataOrder.Y_FIRST):
        super(EasyProvider, self).__init__(name=make_simple_incr_name(callback.__name__), data_order=data_order)
        products.add_products(
            build_product_hierarchy(path=path, provider=self, parameter_type=parameter_type, metadata=metadata))
        self._user_get_data = callback

    def get_data(self, product, start, stop):
        return self._user_get_data(start, stop)


class EasyScalar(EasyProvider):
    def __init__(self, path, get_data_callback, component_name: str, metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST):
        super(EasyScalar, self).__init__(path=path, callback=get_data_callback, parameter_type=ParameterType.SCALAR,
                                         metadata={**metadata, "components": component_name}, data_order=data_order)
        self._columns = [component_name]

    def get_data(self, product, start, stop):
        x, y = self._user_get_data(start, stop)

        return SpeasyVariable(axes=[VariableTimeAxis((x * 1e9).astype("datetime64[ns]"))], values=DataContainer(y),
                              columns=self._columns)


class EasyVector(EasyProvider):
    def __init__(self, path, get_data_callback, components_names: List[str], metadata: dict,
                 data_order: DataOrder = DataOrder.Y_FIRST):
        super(EasyVector, self).__init__(path=path, callback=get_data_callback, parameter_type=ParameterType.VECTOR,
                                         metadata={**metadata, "components": ';'.join(components_names)},
                                         data_order=data_order)
        self._columns = components_names

    def get_data(self, product, start, stop):
        x, y = self._user_get_data(start, stop)

        return SpeasyVariable(axes=[VariableTimeAxis((x * 1e9).astype("datetime64[ns]"))], values=DataContainer(y),
                              columns=self._columns)
