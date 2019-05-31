import traceback
import os
from datetime import datetime, timedelta, timezone
import PythonProviders
import pysciqlopcore
import numpy as np
import requests
import copy
from spwc.amda import AMDA

amda = AMDA()

def amda_make_scalar(var=None):
    if var is None:
        return pysciqlopcore.ScalarTimeSerie(1)
    else:
        return pysciqlopcore.ScalarTimeSerie(var.time,var.data)

def amda_make_vector(var=None):
    if var is None:
        return pysciqlopcore.VectorTimeSerie(1)
    else:
        return pysciqlopcore.VectorTimeSerie(var.time,var.data)

def amda_make_multi_comp(var=None):
    if var is None:
        return pysciqlopcore.MultiComponentTimeSerie((0,2))
    else:
        return pysciqlopcore.MultiComponentTimeSerie(var.time,var.data)

def amda_make_spectro(var=None):
    if var is None:
        return pysciqlopcore.SpectrogramTimeSerie((0,2))
    else:
        if "PARAMETER_TABLE_MIN_VALUES[1]" in var.meta:
            min_v = np.array([ float(v) for v in var.meta["PARAMETER_TABLE_MIN_VALUES[1]"].split(',') ])
            max_v = np.array([ float(v) for v in var.meta["PARAMETER_TABLE_MAX_VALUES[1]"].split(',') ])
            y = (max_v + min_v)/2.
        elif "PARAMETER_TABLE_MIN_VALUES[0]" in var.meta:
            min_v = np.array([ float(v) for v in var.meta["PARAMETER_TABLE_MIN_VALUES[0]"].split(',') ])
            max_v = np.array([ float(v) for v in var.meta["PARAMETER_TABLE_MAX_VALUES[0]"].split(',') ])
            y = (max_v + min_v)/2.
        else:
            y = np.logspace(1,3,var.data.shape[1])[::-1]
        return pysciqlopcore.SpectrogramTimeSerie(var.time,y,var.data)

def amda_get_sample(metadata,start,stop):
    ts_type = amda_make_scalar
    try:
        param_id = None
        for key,value in metadata:
            if key == 'xml:id':
                param_id = value
            elif key == 'type':
                if value == 'vector':
                    ts_type = amda_make_vector
                elif value == 'multicomponent':
                    ts_type = amda_make_multi_comp
                elif value == 'spectrogram':
                    ts_type = amda_make_spectro
        tstart=datetime.fromtimestamp(start, tz=timezone.utc)
        tend=datetime.fromtimestamp(stop, tz=timezone.utc)
        var = amda.get_parameter(start_time=tstart, stop_time=tend, parameter_id=param_id, method="REST")
        return ts_type(var)
    except Exception as e:
        print(traceback.format_exc())
        print("Error in amda.py ",str(e))
        return ts_type()


if len(amda.component) is 0:
    amda.update_inventory()
parameters = copy.deepcopy(amda.parameter)
for name,component in amda.component.items():
    if 'components' in parameters[component['parameter']]:
        parameters[component['parameter']]['components'].append(component)
    else:
        parameters[component['parameter']]['components']=[component]

products = []
for key,parameter in parameters.items():
    path = f"/AMDA/{parameter['mission']}/{parameter.get('observatory','')}/{parameter['instrument']}/{parameter['dataset']}/{parameter['name']}"
    components = [component['name'] for component in parameter.get('components',[])]
    metadata = [ (key,item) for key,item in parameter.items() if key is not 'components' ]
    n_components = parameter.get('size',0)
    if n_components == '3':
        metadata.append(("type","vector"))
    elif parameter.get('display_type','')=="spectrogram":
        metadata.append(("type","spectrogram"))
    elif n_components !=0:
        metadata.append(("type","multicomponent"))
    else:
        metadata.append(("type","scalar"))
    products.append( (path, components, metadata))

PythonProviders.register_product(products, amda_get_sample)


