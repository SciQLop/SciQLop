import numpy as np
from speasy.products import SpeasyVariable
from scipy.interpolate import griddata
from typing import Tuple


def regrid(v: SpeasyVariable) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    t: np.ndarray = v.time.astype(np.timedelta64) / np.timedelta64(1, 's')
    new_t = np.linspace(t[0], t[-1], num=min(10000, len(t)), endpoint=False)
    if len(v.axes) == 1:
        y = np.arange(v.values.shape[1]) * 1.
    else:
        y = np.nan_to_num(v.axes[1].values.astype(np.float64), nan=0., copy=False)
    if len(y.shape) == 2:
        new_y = np.logspace(np.log10(np.nanmin(y)), np.log10(np.nanmax(y)), num=int(4 * y.shape[1]))
        values = v.values
        values = griddata((np.repeat(t, y.shape[1]), y.ravel()), values.ravel(),
                          (np.repeat(new_t, len(new_y)), np.tile(new_y, len(new_t))), method='nearest',
                          fill_value=np.nan)
    else:
        new_y = y
        values = v.values

    if values.dtype != np.float64:
        values = values.astype(np.float64)

    return new_t, new_y, values
