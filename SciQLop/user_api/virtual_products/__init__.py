from speasy import SpeasyVariable
from typing import Callable, List, Optional, Union, Tuple
from enum import Enum

from SciQLop.backend.pipelines_model.easy_provider import EasyVector as _EasyVector, EasyScalar as _EasyScalar, \
    EasySpectrogram as _EasySpectrogram, EasyMultiComponent as _EasyMultiComponent, VirtualProductCallback


class VirtualProductType(Enum):
    Vector = 0
    Scalar = 1
    MultiComponent = 2
    Spectrogram = 3


class VirtualProduct:
    def __init__(self, path: str, callback: VirtualProductCallback, product_type: VirtualProductType):
        self._path = path
        self._callback = callback
        self._product_type = product_type

    @property
    def path(self) -> str:
        return self._path

    @property
    def product_type(self) -> VirtualProductType:
        return self._product_type


class VirtualScalar(VirtualProduct):
    def __init__(self, path: str, callback: VirtualProductCallback, label: str,
                 debug: Optional[bool] = False, cachable: Optional[bool] = False):
        super(VirtualScalar, self).__init__(path, callback, VirtualProductType.Scalar)
        self._impl = _EasyScalar(path, callback, component_name=label, metadata={}, debug=debug, cacheable=cachable)


class VirtualVector(VirtualProduct):
    def __init__(self, path: str, callback: VirtualProductCallback, labels: List[str],
                 debug: Optional[bool] = False, cachable: Optional[bool] = False):
        super(VirtualVector, self).__init__(path, callback, VirtualProductType.Vector)
        self._impl = _EasyVector(path, callback, components_names=labels, metadata={}, debug=debug, cacheable=cachable)


class VirtualMultiComponent(VirtualProduct):
    def __init__(self, path: str, callback: VirtualProductCallback, labels: List[str],
                 debug: Optional[bool] = False, cachable: Optional[bool] = False):
        super(VirtualMultiComponent, self).__init__(path, callback, VirtualProductType.MultiComponent)
        self._impl = _EasyMultiComponent(path, callback, components_names=labels, metadata={}, debug=debug,
                                         cacheable=cachable)


class VirtualSpectrogram(VirtualProduct):
    def __init__(self, path: str, callback: VirtualProductCallback, debug: Optional[bool] = False,
                 cachable: Optional[bool] = False):
        super(VirtualSpectrogram, self).__init__(path, callback, VirtualProductType.Spectrogram)
        self._impl = _EasySpectrogram(path, callback, metadata={}, debug=debug, cacheable=cachable)


def create_virtual_product(path: str, callback: VirtualProductCallback,
                           product_type: VirtualProductType, labels: Optional[List[str]] = None,
                           debug: Optional[bool] = False, cachable: Optional[bool] = False) -> Optional[VirtualProduct]:
    """
    Create a new virtual product that will be listed in the product tree.

    Parameters
    ----------
    path : str
        The path of the virtual product in the product tree.
    callback : VirtualProductCallback
        The callback function that computes the virtual product. The callback function takes two arguments, the start and stop times, and returns a SpeasyVariable or None.
    product_type : VirtualProductType
        The type of the virtual product, either Scalar, Vector, MultiComponent or Spectrogram.
    labels : Optional[List[str]]
        The labels of the virtual product, either one for Scalar, three for Vector, or any number for MultiComponent. The labels are the names of the components of the virtual product.
    debug : Optional[bool]
        The debug flag, prints stack traces of exceptions if True. Handy for debugging the callback function.
    cachable : Optional[bool]
        The cachable flag, when True, SciQLop will assume the callback function is deterministic and always return the same result for the same input.
    Returns
    -------
    Optional[VirtualProduct]
        The virtual product object. If the product type is not recognized, None is returned.
    Raises
    ------
    AssertionError
        If the labels are not provided or do not match the product type.
    Notes
    -----
        - The callback can be a function, a partial function, a lambda, or a callable object. It must take two arguments, the start and stop times with type annotations. It can return a SpeasyVariable, a tuple of numpy arrays, or None.
        - SciQLop will inspect the callback function to determine the input and output types to ensure it is called with the correct arguments.
        - The callback function must be deterministic if the cachable flag is set to True. This means that it must always return the same result for the same input.
        - If a virtual product already exists at the given path, it will be replaced with the new one.
    """
    if product_type == VirtualProductType.Scalar:
        assert labels is not None and len(labels) == 1
        return VirtualScalar(path, callback, label=labels[0], debug=debug, cachable=cachable)
    elif product_type == VirtualProductType.Vector:
        assert labels is not None and len(labels) == 3
        return VirtualVector(path, callback, labels=labels, debug=debug, cachable=cachable)
    elif product_type == VirtualProductType.MultiComponent:
        assert labels is not None
        return VirtualMultiComponent(path, callback, labels=labels, debug=debug, cachable=cachable)
    elif product_type == VirtualProductType.Spectrogram:
        return VirtualSpectrogram(path, callback, debug=debug, cachable=cachable)
    return None
