import sys
import os
import numpy as np
import datetime
import time

os.environ['TZ'] = 'UTC'
epoch_2000 = np.datetime64('2000-01-01T00:00:00',tzinfo=datetime.timezone.utc)

def load_scalar(fname):
    with open(fname, "r") as f:
        return [[
            datetime.datetime(*(time.strptime(line.split()[0], '%Y-%m-%dT%H:%M:%S.%f')[0:6]),
                              tzinfo=datetime.timezone.utc),
            float(line.split()[1])]
            for line in f if "#" not in line]

def extract_vector(variable):
    return zip(*[(pt.x, pt.value(0), pt.value(1), pt.value(2)) for pt in variable])


"""
Copied from myAMDA should be factored in somehow
"""
def generate_data(tstart, tstop, dt):
    delta = np.timedelta64(dt, 's')
    vector_size = int(np.round((tstop-tstart)/delta)) + 1
    t = [tstart+i*delta for i in range(vector_size)]
    x0 = tstart-epoch_2000
    x = [(x0 + i * delta).astype('float')/1000000 for i in range(vector_size)]
    y = [(x0 + (i+1) * delta).astype('float')/1000000 for i in range(vector_size)]
    z = [(x0 + (i+2) * delta).astype('float')/1000000 for i in range(vector_size)]
    return t,x,y,z

def compare_with_ref(var, ref):
    t_ref, x_ref, y_ref, z_ref = ref
    t,x,y,z = extract_vector(var)
    return all([
             all([t_ref[i].astype(float)/1000000 == t[i] for i in range(len(t))]),
             all([x_ref[i] == x[i] for i in range(len(x))]),
             all([y_ref[i] == y[i] for i in range(len(y))]),
             all([z_ref[i] == z[i] for i in range(len(z))])
             ])
