from typing import List, Optional
from enum import Enum

from SciQLop.components.plotting.backend.easy_provider import EasyVector as _EasyVector, EasyScalar as _EasyScalar, \
    EasySpectrogram as _EasySpectrogram, EasyMultiComponent as _EasyMultiComponent, VirtualProductCallback
from SciQLop.components.plotting.backend.dependencies import Depends


class VirtualProductType(Enum):
    Vector = 0
    Scalar = 1
    MultiComponent = 2
    Spectrogram = 3


def _validate_path(path) -> None:
    if not isinstance(path, str):
        raise TypeError(
            f"virtual product path must be a str, got {type(path).__name__}")
    if not path.strip() or not all(seg.strip() for seg in path.replace('//', '/').split('/')):
        raise ValueError(
            f"virtual product path must be a non-empty product-tree path "
            f"(e.g. 'my_products//density'), got {path!r}")


def _validate_callback(callback) -> None:
    if not callable(callback):
        raise TypeError(f"{callback!r} is not a callable object")


class VirtualProduct:
    def __init__(self, path: str, callback: VirtualProductCallback, product_type: VirtualProductType):
        _validate_path(path)
        _validate_callback(callback)
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
                 debug: Optional[bool] = False, cachable: Optional[bool] = False,
                 knobs_model=None, knobs_kwarg_name="knobs", out_of_process: bool = False):
        super(VirtualScalar, self).__init__(path, callback, VirtualProductType.Scalar)
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Scalar virtual products need exactly one non-empty label")
        self._impl = _EasyScalar(path, callback, component_name=label, metadata={},
                                 debug=debug, cacheable=cachable,
                                 knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name,
                                 out_of_process=out_of_process)


class VirtualVector(VirtualProduct):
    def __init__(self, path: str, callback: VirtualProductCallback, labels: List[str],
                 debug: Optional[bool] = False, cachable: Optional[bool] = False,
                 knobs_model=None, knobs_kwarg_name="knobs", out_of_process: bool = False):
        super(VirtualVector, self).__init__(path, callback, VirtualProductType.Vector)
        if not isinstance(labels, (list, tuple)) or len(labels) != 3:
            raise ValueError("Vector virtual products need exactly three labels")
        self._impl = _EasyVector(path, callback, components_names=labels, metadata={},
                                 debug=debug, cacheable=cachable,
                                 knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name,
                                 out_of_process=out_of_process)


class VirtualMultiComponent(VirtualProduct):
    def __init__(self, path: str, callback: VirtualProductCallback, labels: List[str],
                 debug: Optional[bool] = False, cachable: Optional[bool] = False,
                 knobs_model=None, knobs_kwarg_name="knobs", out_of_process: bool = False):
        super(VirtualMultiComponent, self).__init__(path, callback, VirtualProductType.MultiComponent)
        if not isinstance(labels, (list, tuple)) or not labels:
            raise ValueError("MultiComponent virtual products need a non-empty list of labels")
        self._impl = _EasyMultiComponent(path, callback, components_names=labels, metadata={},
                                         debug=debug, cacheable=cachable,
                                         knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name,
                                         out_of_process=out_of_process)


class VirtualSpectrogram(VirtualProduct):
    def __init__(self, path: str, callback: VirtualProductCallback, debug: Optional[bool] = False,
                 cachable: Optional[bool] = False,
                 knobs_model=None, knobs_kwarg_name="knobs", out_of_process: bool = False,
                 display_name: Optional[str] = None):
        super(VirtualSpectrogram, self).__init__(path, callback, VirtualProductType.Spectrogram)
        self._impl = _EasySpectrogram(path, callback, metadata={}, debug=debug, cacheable=cachable,
                                      knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name,
                                      out_of_process=out_of_process,
                                      display_name=display_name)


def create_virtual_product(path: str, callback: VirtualProductCallback,
                           product_type: VirtualProductType, labels: Optional[List[str]] = None,
                           debug: Optional[bool] = False, cachable: Optional[bool] = False,
                           knobs_model=None, knobs_kwarg_name="knobs",
                           display_name: Optional[str] = None) -> Optional[VirtualProduct]:
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
    knobs_model : Optional[type]
        A Pydantic BaseModel class whose fields define the knobs for this product. When provided, the model instance is passed to the callback under knobs_kwarg_name.
    knobs_kwarg_name : str
        Name of the keyword argument used to pass the knobs model instance to the callback (default: "knobs").
    display_name : Optional[str]
        Name shown in the product tree and used as the plot label. Defaults to
        the last segment of `path`.
    Returns
    -------
    VirtualProduct
        The virtual product object.
    Raises
    ------
    TypeError
        If *path* is not a str, *callback* is not callable, or *product_type*
        is not a :class:`VirtualProductType`.
    ValueError
        If *path* is empty or the labels do not match the product type.
    Notes
    -----
        - The callback can be a function, a partial function, a lambda, or a callable object. It must take two arguments, the start and stop times with type annotations. It can return a SpeasyVariable, a tuple of numpy arrays, or None.
        - SciQLop will inspect the callback function to determine the input and output types to ensure it is called with the correct arguments.
        - The callback function must be deterministic if the cachable flag is set to True. This means that it must always return the same result for the same input.
        - If a virtual product already exists at the given path, it will be replaced with the new one.
        - A callback parameter annotated ``Annotated[SpeasyVariable, Depends("a//b", pad=...)]`` declares a dependency: SciQLop resolves that product over the (optionally padded) time range and injects the result as that argument. The target may be a product path, a VirtualProduct, or a callable(start, stop).
    """
    _validate_path(path)
    _validate_callback(callback)
    if not isinstance(product_type, VirtualProductType):
        raise TypeError(
            f"product_type must be a VirtualProductType "
            f"(e.g. VirtualProductType.Scalar), got {product_type!r}")
    if product_type == VirtualProductType.Scalar:
        if labels is None or len(labels) != 1:
            raise ValueError("Scalar virtual products need exactly one label")
        return VirtualScalar(path, callback, label=labels[0], debug=debug, cachable=cachable,
                             knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name)
    elif product_type == VirtualProductType.Vector:
        if labels is None or len(labels) != 3:
            raise ValueError("Vector virtual products need exactly three labels")
        return VirtualVector(path, callback, labels=labels, debug=debug, cachable=cachable,
                             knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name)
    elif product_type == VirtualProductType.MultiComponent:
        if labels is None:
            raise ValueError("MultiComponent virtual products need a list of labels")
        return VirtualMultiComponent(path, callback, labels=labels, debug=debug, cachable=cachable,
                                     knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name)
    return VirtualSpectrogram(path, callback, debug=debug, cachable=cachable,
                              knobs_model=knobs_model, knobs_kwarg_name=knobs_kwarg_name,
                              display_name=display_name)


from SciQLop.user_api.virtual_products.types import Scalar, Vector, MultiComponent, Spectrogram
