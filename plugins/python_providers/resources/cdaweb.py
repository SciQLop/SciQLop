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

def get_sample(name,start,stop):
    try:
        tstart=datetime.datetime.fromtimestamp(start)
        tend=datetime.datetime.fromtimestamp(stop)
        df = cd.get_variable(dataset="MMS2_SCM_SRVY_L2_SCSRVY",variable="mms2_scm_acb_gse_scsrvy_srvy_l2",tstart=tstart,tend=tend)
        t = np.array([d.timestamp()-7200 for d in df.index])
        values = df.values
        return pysciqlopcore.VectorTimeSerie(t,values)
    except Exception as e:
        print("fuck ",str(e))
        return pysciqlopcore.VectorTimeSerie(1)


PythonProviders.register_product([("/CDA/mms4_scm_acb_gse_scsrvy_srvy_l2",[],[("type","vector")])],get_sample)


