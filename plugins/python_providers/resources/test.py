import sys
sys.path.append("/home/jeandet/Documents/prog/build-SciQLop-Desktop-Debug/core")
import PythonProviders
import pysciqlopcore
import numpy as np
import math

someglobal = 1

def make_scalar(x):
    y = np.cos(x/10.)
    return pysciqlopcore.ScalarTimeSerie(x,y)

def make_vector(x):
    v=np.ones((3,len(x)))
    for i in range(3):
        v[:][i] = np.cos(x/10. + float(i))
    return pysciqlopcore.VectorTimeSerie(x,v)


def make_multicomponent(x):
    v=np.ones((4,len(x)))
    for i in range(4):
        v[:][i] = float(i+1) * np.cos(x/10. + float(i))
    return pysciqlopcore.MultiComponentTimeSerie(x,v)


def get_data(metadata,start,stop):
    x = np.arange(math.ceil(start), math.floor(stop))
    for key,value in metadata:
        if key == 'xml:id':
            param_id = value
        elif key == 'type':
            if value == 'vector':
                return make_vector(x)
            elif value == 'multicomponent':
                return make_multicomponent(x)
    return make_scalar(x)




PythonProviders.register_product([("/tests/scalar",[],[("type","scalar")]), ("/tests/vector",[],[("type","vector")]), ("/tests/multicomponent",[],[("type","multicomponent"),('size','4')])],get_data)


