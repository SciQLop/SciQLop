import pytestamda
import os
current_script_path = os.path.dirname(os.path.realpath(__file__))
path = current_script_path+'/../tests-resources/TestAmdaResultParser/ValidScalar1.txt'
c = pytestamda.AmdaResultParser.readScalarTxt(path)
