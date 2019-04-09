import sys
sys.path.append("/home/jeandet/Documents/prog/build-SciQLop-Desktop-Debug/core")
import PythonProviders
import pysciqlopcore
import numpy as np

someglobal = 1

def test(name,start,stop):
    x = np.arange(start, stop)
    y = np.cos(x/10.)
    return pysciqlopcore.ScalarTimeSerie(x,y)


#PythonProviders.register_product(["/folder1/folder2/product1", "/folder1/folder3/product2", "/folder4/folder5/product3"],test)


