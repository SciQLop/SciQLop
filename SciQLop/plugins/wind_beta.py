from SciQLopBindings import DataProvider, Product, ScalarTimeSerie, VectorTimeSerie, MultiComponentTimeSerie
from SciQLopBindings import SciQLopCore, MainWindow, TimeSyncPanel, ProductsTree, DataSeriesType
import numpy as np

import speasy as spz
from speasy.inventory.data_tree import amda
import pandas as pds

b_ = amda.Parameters.Wind.MFI.wnd_mfi_kp.wnd_bmag
n_ = amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_n
vth_ = amda.Parameters.Wind.SWE.wnd_swe_kp.wnd_swe_vth



class WindBeta(DataProvider):
    def __init__(self, parent=None):
        super(WindBeta, self).__init__(parent)
        self.register_products(
            [Product("/amda/Parameters/Wind/Beta", [], DataSeriesType.SCALAR, {})])

    def get_data(self, metadata, start, stop):
        b = spz.get_data(b_, start, stop)
        n = spz.get_data(n_, start, stop)
        vth = spz.get_data(vth_, start, stop)
        if n is None or b is None or vth is None:
            return ScalarTimeSerie(np.array([]), np.array([]))

        bnt = pds.concat([b.to_dataframe(datetime_index=True), n.to_dataframe(datetime_index=True), vth.to_dataframe(datetime_index=True)])
        bnt = bnt.resample('60S').mean().interpolate()
        time = np.array([d.timestamp() for d in bnt.index])
        b=bnt.wnd_bmag.values
        n=bnt.wnd_swe_n.values
        vth=bnt.wnd_swe_vth.values
        T=vth*vth*1.67262e-27/1.380649e-23
        beta = np.array(n*T*1.380649e-23 / (b*b*1.2566e-6*2e-18), dtype=np.float64)
        return ScalarTimeSerie(time, beta)


def load(main_window):
    return WindBeta(main_window)
