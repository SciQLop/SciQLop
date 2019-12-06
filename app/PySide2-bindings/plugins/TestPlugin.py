import traceback
from SciQLopBindings import PyDataProvider, Product, VectorTimeSerie, ScalarTimeSerie, DataSeriesType
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
    x = np.arange(math.ceil(start), math.floor(stop))*1.
    if p_type == 'scalar':
        return make_scalar(x)
    if p_type == 'vector':
        return make_vector(x)
    if p_type == 'multicomponent':
        return make_multicomponent(x)
    if p_type == 'spectrogram':
        return make_spectrogram(np.arange(math.ceil(start), math.floor(stop),15.))
    return None

class MyProvider(PyDataProvider):
    def __init__(self):
        super(MyProvider,self).__init__()
        self.register_products([Product("/tests/without_cache/scalar",[],{"type":"scalar"}),
            Product("/tests/without_cache/vector",[],{"type":"vector"}),
            Product("/tests/without_cache/multicomponent",[],{"type":"multicomponent",'size':'4'}),
            Product("/tests/without_cache/spectrogram",[],{"type":"spectrogram",'size':'32'}),
            Product("/tests/with_cache/scalar",[],{"type":"scalar", "cache":"true"}),
            Product("/tests/with_cache/vector",[],{"type":"vector", "cache":"true"}),
            Product("/tests/with_cache/multicomponent",[],{"type":"multicomponent",'size':'4', "cache":"true"})
            ])

    def get_data(self,metadata,start,stop):
        ts_type = DataSeriesType.SCALAR
        default_ctor_args = 1
        use_cache = False
        p_type = 'scalar'
        try:
            for key,value in metadata.items():
                if key == 'type':
                    p_type = value
                    if value == 'vector':
                        ts_type = DataSeriesType.VECTOR
                    elif value == 'multicomponent':
                        ts_type = DataSeriesType.MULTICOMPONENT
                    elif value == 'spectrogram':
                        ts_type = DataSeriesType.SPECTROGRAM
                if key == 'cache' and value == 'true':
                    use_cache = True
            if use_cache:
                cache_product = f"tests/{p_type}"
                var = _cache.get_data(cache_product, DateTimeRange(datetime.fromtimestamp(start, tz=timezone.utc), datetime.fromtimestamp(stop, tz=timezone.utc)), partial(_get_data, p_type), fragment_hours=24)
            else:
                var = _get_data(p_type, start, stop)
            return (((var.time, np.array([])),var.data), ts_type)
        except Exception as e:
            print(traceback.format_exc())
            print("Error in test.py ",str(e))
            return (((np.array([]), np.array([])), np.array([])), ts_type)


t=MyProvider()

