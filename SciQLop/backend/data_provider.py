from PySide6.QtCore import QObject, QThread
import numpy as np
from typing import Tuple, Optional
from enum import Enum

providers = {}


class DataOrder(Enum):
    ROW_MAJOR = 0
    COLUMN_MAJOR = 1


class DataProvider:
    def __init__(self, name: str, parent=None, data_order: DataOrder = DataOrder.ROW_MAJOR):
        providers[name] = self
        self._name = name
        self._data_order = data_order

    def __del__(self):
        providers.pop(self._name)

    @property
    def name(self) -> str:
        return self._name

    @property
    def data_order(self) -> DataOrder:
        return self._data_order

    def get_data(self, node, start, stop) -> Optional[Tuple[np.array, np.array]]:
        pass
