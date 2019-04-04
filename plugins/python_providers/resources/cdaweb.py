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
        tstart=datetime.datetime.fromtimestamp(start).strftime('%Y%m%dT%H%M%SZ')
        tend=datetime.datetime.fromtimestamp(stop).strftime('%Y%m%dT%H%M%SZ')
        req_url=f"https://cdaweb.gsfc.nasa.gov/WS/cdasr/1/dataviews/sp_phys/datasets/MMS4_SCM_SRVY_L2_SCSRVY/data/{tstart},{tend}/mms4_scm_acb_gse_scsrvy_srvy_l2?format=csv"
        resp = requests.get(req_url,headers={"Accept":"application/json"})
        csv_url = resp.json()['FileDescription'][0]['Name']
        df = pds.read_csv(csv_url,comment='#',index_col=0, infer_datetime_format=True,parse_dates=True)
        t = np.array([d.timestamp()-7200 for d in df.index])
        values = df.values
        return pysciqlopcore.VectorTimeSerie(t,values)
    except Exception as e:
        print("fuck ",str(e))
        return pysciqlopcore.VectorTimeSerie(1)

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


