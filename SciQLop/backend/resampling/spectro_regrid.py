import numpy as np
from speasy.products import SpeasyVariable
from scipy.interpolate import griddata
from typing import Tuple


def regrid(v: SpeasyVariable) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    t: np.ndarray = v.time.astype(np.timedelta64) / np.timedelta64(1, 's')
    resampled_t = np.linspace(t[0], t[-1], num=min(10000, len(t)), endpoint=False)
    values = v.values
    invert_y = False

    if len(v.axes) == 1:
        new_y = np.arange(v.values.shape[1]) * 1.
        y = np.tile(new_y, len(t)).reshape((len(t), -1))
    elif len(v.axes[1].values.shape) == 1:
        new_y = np.nan_to_num(v.axes[1].values.astype(np.float64), nan=0., copy=False)
        if new_y[0] > new_y[1]:
            new_y = new_y[::-1].copy()
            values = values[:, ::-1].copy()
            invert_y = True
        y = np.tile(new_y, len(t)).reshape((len(t), -1))
    elif v.axes[1].values.shape[0] == 1:
        new_y = np.nan_to_num(v.axes[1].values.astype(np.float64), nan=0., copy=False)[0]
        if new_y[0] > new_y[1]:
            new_y = new_y[::-1].copy()
            values = values[:, ::-1].copy()
        y = np.tile(new_y, len(t)).reshape((len(t), -1))
    else:
        y = v.axes[1].values.astype(np.float64)
        if y[0, 0] > y[0, 1]:
            y = y[:, ::-1].copy()
            values = values[:, ::-1].copy()
        new_y = np.logspace(np.log10(np.nanmin(y)), np.log10(np.nanmax(y)), num=int(4 * y.shape[1]))
        y = np.nan_to_num(y, nan=0., copy=False)

    values = griddata((np.repeat(t, y.shape[1]), y.ravel()),
                      values.ravel(),
                      (np.repeat(resampled_t, len(new_y)), np.tile(new_y, len(resampled_t))),
                      method='nearest',
                      fill_value=np.nan, rescale=True)

    if values.dtype != np.float64:
        values = values.astype(np.float64)

    return resampled_t, new_y, values
