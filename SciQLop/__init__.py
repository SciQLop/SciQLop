from PySide6 import QtCore, QtWidgets
from SciQLopBindings import DataProvider, Product, ScalarTimeSerie, VectorTimeSerie
from SciQLopBindings import SciQLopCore, MainWindow, TimeSyncPanel, ProductsTree, DataSeriesType
import numpy as np
import speasy as spz

app = QtWidgets.QApplication([])


class MyProvider(DataProvider):
    def __init__(self, path="/tests/scalar"):
        super(MyProvider, self).__init__()
        self.register_products([Product(path, [], DataSeriesType.SCALAR, {"type": "scalar"})])

    def get_data(self, metadata, start, stop):
        t = np.arange(start, stop,.1)
        return ScalarTimeSerie(
            t, np.cos(t)
        )

class MyProvider2(DataProvider):
    def __init__(self, path="/speasy/tha_bs_tot"):
        super(MyProvider2, self).__init__()
        self.register_products([Product("/speasy/tha_bs_tot", [], DataSeriesType.SCALAR, {"type": "scalar", "xmlid":"tha_bs_tot"}),
                                Product("/speasy/the_bs", [], DataSeriesType.VECTOR, {"type": "vector", "xmlid":"the_bs"})])

    def get_data(self, metadata, start, stop):
        v = spz.get_data("amda/"+metadata["xmlid"], start, stop)
        if metadata["type"] == "scalar":
                return ScalarTimeSerie(
                    v.time, v.data
                ) if v else ScalarTimeSerie(np.array([]), np.array([]))
        if metadata["type"] == "vector":
                return VectorTimeSerie(
                    v.time, v.data
                )if v else VectorTimeSerie(np.array([]), np.array([]))


t = MyProvider()
u = MyProvider2()
w = MainWindow()
w.addTimeSyncPannel(TimeSyncPanel())
w.addTimeSyncPannel(TimeSyncPanel())
w.addWidgetIntoDock(QtCore.Qt.LeftDockWidgetArea, ProductsTree())

w.show()
app.exec()
