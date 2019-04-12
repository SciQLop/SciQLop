import sys
sys.path.append("/home/jeandet/Documents/prog/build-SciQLop-Desktop-Debug/core")
import os
import datetime
import PythonProviders
import pysciqlopcore
import numpy as np
import pandas as pds
import requests
from spwc.cdaweb import cdaweb

cd = cdaweb()

def cda_get_sample(metadata, start,stop):
    ts_type = pysciqlopcore.ScalarTimeSerie
    default_ctor_args = 1
    try:
        variable_id = None
        dataset_id = None
        for key,value in metadata:
            if key == 'VAR_ID':
                variable_id = value
            elif key == 'DATASET_ID':
                dataset_id = value
            elif key == 'type':
                if value == 'vector':
                    ts_type = pysciqlopcore.VectorTimeSerie
                elif value == 'multicomponent':
                    ts_type = pysciqlopcore.MultiComponentTimeSerie
                    default_ctor_args = (0,2)
        tstart=datetime.datetime.fromtimestamp(start, tz=timezone.utc)
        tend=datetime.datetime.fromtimestamp(stop, tz=timezone.utc)
        df = cd.get_variable(dataset=dataset_id,variable=variable_id,tstart=tstart,tend=tend)
        t = np.array([d.timestamp() for d in df.index])
        values = df.values
        print(values.shape)
        return ts_type(t,values)
    except Exception as e: 
        print(traceback.format_exc())
        print("Error in amda.py ",str(e))
        return ts_type(default_ctor_args)


products = [
   ("/CDA/Themis/ThA/tha_fgl_gsm", [], [("type","multicomponent"), ('size','4'), ("DATASET_ID","THA_L2_FGM"), ("VAR_ID","tha_fgl_gsm")]),
   ("/CDA/Themis/ThB/thb_fgl_gsm", [], [("type","multicomponent"), ('size','4'), ("DATASET_ID","THB_L2_FGM"), ("VAR_ID","thb_fgl_gsm")]),
 
]

PythonProviders.register_product(products, cda_get_sample)


