# -*- coding: utf-8 -*-
# TODO add 13Bus test feeder simulator
import cmath
import json
import math
import re
import os
import sys
import numpy
import helics as h
import opendssdirect as dss
from opendssdirect.utils import run_command

import csv
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


PUBLICATIONS = {}
SUBSCRIPTIONS = {}


# read time series load profile data
load_profile_df = pd.read_csv(os.getcwd() + '\\37Bus\\load_profile.csv', index_col=0)
load_profile = load_profile_df.iloc[:, 0]

# old_min = load_profile.min()
# old_max = load_profile.max()
# new_max = 1
# new_min = 0.9
# load_profile_scaled = (load_profile - old_min) / (old_max - old_min) * (new_max - new_min) + new_min


fig, ax1 = plt.subplots()
ax1 = load_profile.plot()
#plt.show()
# test run
feeder_name = '37Bus'
print('------ Running the {} feeder in opendss'.format(feeder_name))
run_command('compile ' + feeder_name + '/Master.dss')
if dss.Text.Result() == '':
    print('------ Success for the test run -----')
else:
    print('------ Opendss failed ----')

loadname_all=[]
loadkw_all=[]
loadkvar_all=[]

dss.Loads.First()
for i in range(dss.Loads.Count()):
    loadname = dss.Loads.Name()
    loadkw = dss.Loads.kW()
    loadkvar = dss.Loads.kvar()
    loadname_all.append(loadname)
    loadkw_all.append(loadkw)
    loadkvar_all.append(loadkvar)
    dss.Loads.Next()

loadkw_dict = dict(zip(loadname_all,loadkw_all))
loadkvar_dict = dict(zip(loadname_all,loadkvar_all))
allnodenames = dss.Circuit.AllNodeNames()
num_sim = 75
num_sim = 75
allbusmagpu_ts = []
for i in range(num_sim):
    print(f"Doing {i} time step: at load multiply {load_profile.iloc[i]}")
    dss.Loads.First()
    for j in range(dss.Loads.Count()):
        loadname = dss.Loads.Name()
        # now calculate kw and kvar based on the csv
        load_mult = load_profile.iloc[i]
        loadkw_new = load_mult * loadkw_dict[loadname]
        loadkvar_new = load_mult * loadkvar_dict[loadname]
        # now change opendss load object
        run_command('edit load.{ln} kw={kw}'.format(ln=loadname, kw=loadkw_new))
        run_command('edit load.{ln} kvar={kw}'.format(ln=loadname, kw=loadkvar_new))
        dss.Loads.Next()
    run_command('solve')
    allbusmagpu = dss.Circuit.AllBusMagPu()
    allbusmagpu_ts.append( allbusmagpu)

# change list of results to dataframe
v_results_df = pd.DataFrame(allbusmagpu_ts)

#fig, ax2 = plt.subplots()
ax2 =v_results_df.plot(legend=False)
plt.show()