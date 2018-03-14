import sys
import os
if not hasattr(sys, 'argv'):
    sys.argv  = ['']
current_script_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_script_path)
import amda
import pytestamda

import numpy as np
import datetime
import time
import unittest
import ddt

def wait_for_downloads():
    while pytestamda.VariableController.hasPendingDownloads():
        time.sleep(0.1)

def extract_vector(variable):
    return zip(*[(pt.x, pt.value(0), pt.value(1), pt.value(2)) for pt in variable])

def compare_with_ref(var, ref):
    t_ref, x_ref, y_ref, z_ref = ref
    t,x,y,z = extract_vector(var)
    return all([
             all([t_ref[i].astype(float)/1000000 == t[i] for i in range(len(t))]),
             all([x_ref[i] == x[i] for i in range(len(x))]),
             all([y_ref[i] == y[i] for i in range(len(y))]),
             all([z_ref[i] == z[i] for i in range(len(z))])
             ])

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
        pytestamda.TimeController.setTime(pytestamda.SqpRange(tstart, tstop))
        variable = pytestamda.VariableController.createVariable("bx_gse",pytestamda.amda_provider())
        wait_for_downloads()
        t_ref, x_ref, y_ref, z_ref = amda.generate_data(np.datetime64(tstart), np.datetime64(tstop), 4)
        self.assertTrue( compare_with_ref(variable,(t_ref, x_ref, y_ref, z_ref) ) )


if __name__ == '__main__':
    unittest.main(exit=False)
