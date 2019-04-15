import sys
sys.path.append("/home/jeandet/Documents/prog/build-SciQLop-Desktop-Debug/core")
import PythonProviders
import pysciqlopcore
import numpy as np
import math
from spwc.cache import _cache
from spwc.common.datetime_range import DateTimeRange
from functools import partial
from datetime import datetime, timedelta, timezone

someglobal = 1

def make_scalar(x):
    y = np.cos(x/10.)
    return pds.DataFrame(index=[datetime.fromtimestamp(t, tz=timezone.utc) for t in x], data=y)

def make_vector(x):
    v=np.ones((len(x),3))
    for i in range(3):
        v.transpose()[:][i] = np.cos(x/10. + float(i)) + (100. * np.cos(x/10000. + float(i)))
    return pds.DataFrame(index=[datetime.fromtimestamp(t, tz=timezone.utc) for t in x], data=v)


def make_multicomponent(x):
    v=np.ones((len(x),4))
    for i in range(4):
        v.transpose()[:][i] = float(i+1) * np.cos(x/10. + float(i))
    return pds.DataFrame(index=[datetime.fromtimestamp(t, tz=timezone.utc) for t in x], data=v)


def _get_data(p_type, start, stop):
    if type(start) is datetime:
        start = start.timestamp()
        stop = stop.timestamp()
    x = np.arange(math.ceil(start), math.floor(stop))
    if p_type == 'scalar':
        return make_scalar(x)
    if p_type == 'vector':
        return make_vector(x)
    if p_type == 'multicomponent':
        return make_multicomponent(x)
    return None

def get_data(metadata,start,stop):
    ts_type = pysciqlopcore.ScalarTimeSerie
    default_ctor_args = 1
    use_cache = False
    p_type = 'scalar'
    try:
        for key,value in metadata:
            if key == 'type':
                p_type = value
                if value == 'vector':
                    ts_type = pysciqlopcore.VectorTimeSerie
                elif value == 'multicomponent':
                    ts_type = pysciqlopcore.MultiComponentTimeSerie
                    default_ctor_args = (0,2)
            if key == 'cache' and value == 'true':
                use_cache = True
        if use_cache:
            cache_product = f"tests/{p_type}"
            df = _cache.get_data(cache_product, DateTimeRange(datetime.fromtimestamp(start, tz=timezone.utc), datetime.fromtimestamp(stop, tz=timezone.utc)),
                                     partial(_get_data, p_type),
                                     fragment_hours=24)
        else:
            print("No Cache")
            df = _get_data(p_type, start, stop)
        t = np.array([d.timestamp() for d in df.index])
        values = df.values
        return ts_type(t,values)
    except Exception as e:
        print(traceback.format_exc())
        print("Error in test.py ",str(e))
        return ts_type(default_ctor_args)

products = [
    ("/tests/without_cache/scalar",[],[("type","scalar")]),
    ("/tests/without_cache/vector",[],[("type","vector")]),
    ("/tests/without_cache/multicomponent",[],[("type","multicomponent"),('size','4')]),
    ("/tests/with_cache/scalar",[],[("type","scalar"), ("cache","true")]),
    ("/tests/with_cache/vector",[],[("type","vector"), ("cache","true")]),
    ("/tests/with_cache/multicomponent",[],[("type","multicomponent"),('size','4'), ("cache","true")])
    ]


PythonProviders.register_product(products ,get_data)
