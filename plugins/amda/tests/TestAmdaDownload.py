import sys
import os
if not hasattr(sys, 'argv'):
    sys.argv  = ['']
current_script_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_script_path)

import pytestamda
import pysciqlopcore

import sciqlopqt
import amda

import numpy as np
import datetime
import time
import unittest
import ddt

@ddt.ddt
class FunctionalTests(unittest.TestCase):
    def setUp(self):
        pass

    @ddt.data(
        (datetime.datetime(2012,10,20,8,10,00),datetime.datetime(2012,10,20,12,0,0)),
        (datetime.datetime(2025,1,1,15,0,0),datetime.datetime(2025,1,1,16,0,0)),
        (datetime.datetime(2000,1,1,0,0,0),datetime.datetime(2000,1,1,12,0,0))
    )
    def test_simple_download(self, case):
        tstart = case[0]
        tstop = case[1]
        pytestamda.TimeController.setTime(pysciqlopcore.SqpRange(tstart, tstop))
        variable = pytestamda.VariableController.createVariable("bx_gse",pytestamda.amda_provider(), pysciqlopcore.SqpRange(tstart, tstop))
        pytestamda.VariableController.wait_for_downloads()
        t_ref, x_ref, y_ref, z_ref = amda.generate_data(np.datetime64(tstart), np.datetime64(tstop), 4)
        self.assertTrue( amda.compare_with_ref(variable,(t_ref, x_ref, y_ref, z_ref) ) )


if __name__ == '__main__':
    unittest.main(exit=False)
