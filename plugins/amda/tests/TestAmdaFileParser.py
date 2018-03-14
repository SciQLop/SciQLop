import sys
import os
if not hasattr(sys, 'argv'):
    sys.argv  = ['']
current_script_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_script_path)
import pytestamda
import amda

import numpy as np
import datetime
import time
import unittest
import ddt

path = current_script_path+'/../tests-resources/TestAmdaResultParser/ValidScalar1.txt'

@ddt.ddt
class FunctionalTests(unittest.TestCase):
    def setUp(self):
        pass

    @ddt.data(
        current_script_path+'/../tests-resources/TestAmdaResultParser/ValidScalar1.txt'
    )
    def test_correct_scalars(self, case):
        scalar_sciqlop = pytestamda.AmdaResultParser.readScalarTxt(case)
        scalar_ref = amda.load_scalar(case)
        self.assertTrue(len(scalar_ref) == len(scalar_sciqlop))
        self.assertTrue(all(
            [scalar_ref[i][1] == scalar_sciqlop[i].value()
            for i in range(len(scalar_sciqlop))]))
        self.assertTrue(all(
            [scalar_ref[i][0].timestamp() == scalar_sciqlop[i].x
            for i in range(len(scalar_sciqlop))]))


if __name__ == '__main__':
    unittest.main(exit=False)
