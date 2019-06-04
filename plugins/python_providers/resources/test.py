import traceback
import pandas as pds
import PythonProviders
import pysciqlopcore
import numpy as np
import math
from spwc.cache import _cache
from spwc.common.datetime_range import DateTimeRange
from functools import partial
from datetime import datetime, timedelta, timezone
from spwc.common.variable import SpwcVariable

def make_scalar(x):
    y = np.cos(x/10.)
    return SpwcVariable(time=x, data=y)

def make_vector(x):
    v=np.ones((len(x),3))
    for i in range(3):
        v.transpose()[:][i] = np.cos(x/10. + float(i)) + (100. * np.cos(x/10000. + float(i)))
    return SpwcVariable(time=x, data=v)


def make_multicomponent(x):
    v=np.ones((len(x),4))
    for i in range(4):
        v.transpose()[:][i] = float(i+1) * np.cos(x/10. + float(i))
    return SpwcVariable(time=x, data=v)

def make_spectrogram(x):
    v=np.ones((len(x),32))
    for i in range(32):
        v.transpose()[:][i] = 100.*(2.+ float(i+1) * np.cos(x/1024. + float(i)))
    return SpwcVariable(time=x, data=v)


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
    if p_type == 'spectrogram':
        return make_spectrogram(np.arange(math.ceil(start), math.floor(stop),15.))
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
                elif value == 'spectrogram':
                    ts_type = lambda t,values: pysciqlopcore.SpectrogramTimeSerie(t,np.logspace(1,3,32)[::-1],values,np.nan,np.nan)
                    default_ctor_args = (0,2)
            if key == 'cache' and value == 'true':
                use_cache = True
        if use_cache:
            cache_product = f"tests/{p_type}"
            var = _cache.get_data(cache_product, DateTimeRange(datetime.fromtimestamp(start, tz=timezone.utc), datetime.fromtimestamp(stop, tz=timezone.utc)),
                                     partial(_get_data, p_type),
                                     fragment_hours=24)
        else:
            print("No Cache")
            var = _get_data(p_type, start, stop)
        return ts_type(var.time,var.data)
    except Exception as e:
        print(traceback.format_exc())
        print("Error in test.py ",str(e))
        return ts_type(default_ctor_args)

products = [
    ("/tests/without_cache/scalar",[],[("type","scalar")]),
    ("/tests/without_cache/vector",[],[("type","vector")]),
    ("/tests/without_cache/multicomponent",[],[("type","multicomponent"),('size','4')]),
    ("/tests/without_cache/spectrogram",[],[("type","spectrogram"),('size','32')]),
    ("/tests/with_cache/scalar",[],[("type","scalar"), ("cache","true")]),
    ("/tests/with_cache/vector",[],[("type","vector"), ("cache","true")]),
    ("/tests/with_cache/multicomponent",[],[("type","multicomponent"),('size','4'), ("cache","true")])
    ]


PythonProviders.register_product(products ,get_data)
