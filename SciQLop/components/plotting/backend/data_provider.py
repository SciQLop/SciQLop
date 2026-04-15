from typing import Tuple, List, Union

import traceback
import numpy as np

from SciQLop.core.enums import DataOrder, GraphType
from SciQLop.core.plot_hints import PlotHints
from SciQLop.components import sciqlop_logging
from speasy.products import SpeasyVariable, VariableAxis
from speasy.core import datetime64_to_epoch

log = sciqlop_logging.getLogger(__name__)

DataProviderReturnType = Union[
    SpeasyVariable, Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, np.ndarray], List[np.ndarray]]

providers = {}


def _ensure_contiguous(v):
    return np.ascontiguousarray(v)


def _filter_axis_numeric_axes(axes: List[VariableAxis]) -> List[VariableAxis]:
    return [
        axis for axis in axes if np.issubdtype(axis.values.dtype, np.number)
    ]


def _sort_axis_by_time(axis: VariableAxis, sorted_indices) -> VariableAxis:
    if axis.is_time_dependent:
        axis.values[:] = axis.values[sorted_indices]
    return axis


def _sort_variable_by_time(variable: SpeasyVariable) -> SpeasyVariable:
    sorted_indices = np.argsort(variable.time)
    for i in range(len(variable.axes)):
        _sort_axis_by_time(variable.axes[i], sorted_indices)
    variable.values[:] = variable.values[sorted_indices]
    return variable


class DataProvider:
    def __init__(self, name: str, data_order: DataOrder = DataOrder.X_FIRST, cacheable: bool = False):
        global providers  # noqa: F824
        providers[name] = self
        self._name = name
        self._data_order = data_order
        self._cacheable = cacheable

    @property
    def name(self) -> str:
        return self._name

    @property
    def data_order(self) -> DataOrder:
        return self._data_order

    @property
    def cacheable(self) -> bool:
        return self._cacheable

    def labels(self, node) -> List[str]:
        pass

    def graph_type(self, node) -> GraphType:
        pass

    def plot_hints(self, node) -> PlotHints:
        return PlotHints()

    def plot_hints_from_variable(self, node, variable) -> PlotHints:
        """Compute extra hints from a successfully fetched data variable.

        Called at most once per plot, after the first fetch that returned
        non-empty data. Defaults to no extra hints.
        """
        return PlotHints()

    def _get_data(self, node, start, stop, on_variable=None) -> Union[
        List[np.ndarray], Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        try:
            v = self.get_data(node, start, stop)
            if v is not None and on_variable is not None:
                try:
                    on_variable(v)
                except Exception:
                    log.debug("on_variable callback failed", exc_info=True)
            if v is None:
                return []
            if isinstance(v, list) or isinstance(v, tuple):
                return v
            if not np.all(np.diff(v.time) >= 0):
                v = _sort_variable_by_time(v)
            time = datetime64_to_epoch(v.time)
            axes = _filter_axis_numeric_axes(v.axes[1:])
            if len(axes) == 0 or self.graph_type(node) in (GraphType.MultiLines, GraphType.SingleLine):
                return [time, _ensure_contiguous(v.values)]
            return [time, _ensure_contiguous(axes[0].values), _ensure_contiguous(v.values)]
        except Exception:
            log.error(
                f"Error getting data for {node} between {start} and {stop}: \n\nbacktrace: {traceback.format_exc()}")
            return []

    def get_data(self, node, start: float, stop: float) -> DataProviderReturnType:
        pass
