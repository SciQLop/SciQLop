import pyspedas
from pytplot import get_data

from SciQLopBindings import DataProvider, Product, ScalarTimeSerie, VectorTimeSerie, MultiComponentTimeSerie
from SciQLopBindings import SciQLopCore, MainWindow, TimeSyncPanel, ProductsTree, DataSeriesType
import numpy as np
from datetime import datetime


def time_format(t):
    return datetime.utcfromtimestamp(t).strftime('%Y-%m-%d/%H:%M:%S')


class SpedasPlugin(DataProvider):
    def __init__(self, parent=None):
        super(SpedasPlugin, self).__init__(parent)
        self.register_products(
            [Product("/spedas/mms/mms1_fgm_b_gse_srvy_l2", [], DataSeriesType.VECTOR, {"type": "vector"})])

    def get_data(self, metadata, start, stop):
        try:
            mag_data = pyspedas.mms.fgm(trange=[time_format(start), time_format(stop)], probe=1,
                             varnames='mms1_fgm_b_gse_srvy_l2',
                             notplot=True,
                             time_clip=True)['mms1_fgm_b_gse_srvy_l2']
            return VectorTimeSerie(np.array(mag_data['x']), np.array(mag_data['y'][:,:-1], dtype=np.float64))
        except Exception:
            return VectorTimeSerie(np.array([]), np.array([]))


def load(main_window):
    return SpedasPlugin(main_window)
