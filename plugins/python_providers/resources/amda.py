import sys
sys.path.append("/home/jeandet/Documents/prog/build-SciQLop-Desktop-Debug/core")
import traceback
import os
from datetime import datetime, timedelta, timezone
import PythonProviders
import pysciqlopcore
import numpy as np
import pandas as pds
import requests
from spwc.amda import AMDA

amda = AMDA()

def get_sample(metadata,start,stop):
    ts_type = pysciqlopcore.ScalarTimeSerie
    try:
        param_id = None
        for key,value in metadata:
            if key == 'xml:id':
                param_id = value
            elif key == 'type':
                if value == 'vector':
                    ts_type = pysciqlopcore.VectorTimeSerie
        tstart=datetime.datetime.utcfromtimestamp(start)
        tend=datetime.datetime.utcfromtimestamp(stop)
        df = amda.get_parameter(start_time=tstart, stop_time=tend, parameter_id=param_id)
        #t = np.array([d.timestamp()-7200 for d in df.index])
        t = np.array([d.timestamp() for d in df.index])
        values = df.values
        return ts_type(t,values)
        return ts_type(1)
    except Exception as e:
        print(traceback.format_exc())
        print("Error in amda.py ",str(e))
        return ts_type(1)


if len(amda.component) is 0:
    amda.update_inventory()
parameters = amda.parameter.copy()
for name,component in amda.component.items():
    if 'components' in parameters[component['parameter']]:
        parameters[component['parameter']]['components'].append(component)
    else:
        parameters[component['parameter']]['components']=[component]

products = []
for key,parameter in parameters.items():
    path = f"/AMDA/{parameter['mission']}/{parameter['instrument']}/{parameter['dataset']}/{parameter['name']}" 
    components = [component['name'] for component in parameter.get('components',[])]
    metadata = [ (key,item) for key,item in parameter.items() if key is not 'components' ]
    if parameter.get('size',0) is '3':
        metadata.append(("type","vector"))
    else:
        metadata.append(("type","scalar"))
    products.append( (path, components, metadata))

PythonProviders.register_product(products, get_sample)


