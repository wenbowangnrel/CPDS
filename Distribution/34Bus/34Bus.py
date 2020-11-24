# -*- coding: utf-8 -*-
"""
34Bus test feeder simulator
"""
import cmath
import json
import math
import re
import os
import sys
import numpy as np
import helics as h
import opendssdirect as dss
from opendssdirect.utils import run_command

import csv
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

dir_to_feeder = os.getcwd()
# read time series load profile data
load_profile_df = pd.read_csv(dir_to_feeder + '\\DSSfiles\\load_profile.csv', index_col=0)
load_profile = load_profile_df.iloc[:, 0]

# convert it to the range in [0.9, 1]
old_min = load_profile.min()
old_max = load_profile.max()
new_max = 1
new_min = 0.9
load_profile_scaled = (load_profile - old_min) / (old_max - old_min) * (new_max - new_min) + new_min
load_profile_scaled = pd.concat([load_profile_scaled, load_profile_scaled])

# fig, ax1 = plt.subplots()
# ax1 = load_profile.plot()
print(f"os.getcwd()={os.getcwd()}")
# test run Opendss feeder
feeder_name = '34Bus'
print('------ Running the {} feeder in opendss'.format(feeder_name))
run_command('compile DSSfiles/Master.dss')
if dss.Text.Result() == '':
    print('------ Success for the test run -----')
else:
    print('------ Opendss failed ----')

print(f"After opendss run os.getcwd()={os.getcwd()}")

# get load kw values
BASEKV = dss.Vsources.BasekV()
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

loadkw_dict = dict(zip(loadname_all, loadkw_all))
loadkvar_dict = dict(zip(loadname_all, loadkvar_all))
allnodenames = dss.Circuit.AllNodeNames()

print(f"Total power base line is {dss.Circuit.TotalPower()}")

################# read in config file ###########################################
print("reading json")
filename = "..\\34Bus.json"
with open(filename) as f:
    data = json.loads(f.read())
    federate_name = data["name"]
    total_time = data["total_time"]
    step_time = data["step_time"]
    subscriptions = data["subscriptions"]
    publications = data["publications"]
print("reading json okay!")

################### create the federate info object ##################

PUBLICATIONS = {}
SUBSCRIPTIONS = {}
# define federate information (configuration)
fedinfo = h.helicsCreateFederateInfo() # initialization
h.helicsFederateInfoSetCoreName(fedinfo, f"{federate_name}") # define name
h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq") # core type:
h.helicsFederateInfoSetCoreInitString(fedinfo, "--federates=1") # define number of federate connect to this core
h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, 1.0)

# create the value federate: this type of federate is used for exchange electrical information
fed = h.helicsCreateValueFederate(f"{federate_name}", fedinfo)
print(f"{federate_name}: Combination federate created", flush=True)

# define pub and sub through json
# for k, v in publications.items():
#     pub = h.helicsFederateRegisterTypePublication(fed, v["topic"], "complex", "")
#     PUBLICATIONS[k] = pub
for k, v in subscriptions.items():
    sub = h.helicsFederateRegisterSubscription(fed, v["topic"], "")
    SUBSCRIPTIONS[k] = sub

# define pub and sub directly:
#sub = h.helicsFederateRegisterSubscription(fed, "voltage", "")
pub = h.helicsFederateRegisterGlobalTypePublication(fed, "34Bus/Totalpower", "complex", "")

h.helicsFederateEnterExecutingMode(fed)
################### Now start executation ###################

current_time = 0
allbusmagpu_ts = []
totalpower_ts = []
for request_time in range(0, int(total_time), int(step_time)):
    while current_time < request_time:

        current_time = h.helicsFederateRequestTime(fed, request_time)
        #print(current_time)
    print(f"current_time={current_time}")
    dss.run_command("Solve")
    # save some results
    allbusmagpu = dss.Circuit.AllBusMagPu()
    allbusmagpu_ts.append(allbusmagpu)
    totalpower_ts.append(dss.Circuit.TotalPower())
    S = dss.Circuit.TotalPower()
    P = -S[0]
    Q = -S[1]

    scale = 0.478*100/2.032
    P = P*scale
    Q = Q*scale
    # now publish the results
    h.helicsPublicationPublishComplex(pub, P, Q)
    print("Sent Active power at time {}: {} kw".format(current_time, P))
    print("Sent Reactive power at time {}: {} kvar".format(current_time, Q))

    # now get sub the results
    for key, sub in SUBSCRIPTIONS.items():
        val = h.helicsInputGetComplex(sub)
        if subscriptions[key]['value'] == 'Voltage':

            print("Received voltage mag at time {}: {} pu".format(current_time, val[0]))
            print("Received voltage ang at time {}: {} rad".format(current_time, val[1]))

        voltage, angle_rad = val
        # convert angle to degree
        angle_deg = np.degrees(angle_rad)
    # change the substation voltage and angle based on sub
    #print(f'current time={current_time}')
    if current_time == 0:
        print('manually set up first step voltage')
        dss.Vsources.AngleDeg(0)
        dss.Vsources.PU(1)
    else:
        dss.Vsources.AngleDeg(angle_deg)
        dss.Vsources.PU(voltage)
    # change load according to load profile
    dss.Loads.First()
    for j in range(dss.Loads.Count()):
        loadname = dss.Loads.Name()
        # now calculate kw and kvar based on the csv
        load_mult = load_profile_scaled.iloc[request_time]
        loadkw_new = load_mult * loadkw_dict[loadname]
        loadkvar_new = load_mult * loadkvar_dict[loadname]
        # now change opendss load object
        run_command('edit load.{ln} kw={kw}'.format(ln=loadname, kw=loadkw_new))
        run_command('edit load.{ln} kvar={kw}'.format(ln=loadname, kw=loadkvar_new))
        dss.Loads.Next()
voltage_results = pd.DataFrame(allbusmagpu_ts, columns=allnodenames)
#voltage_results.to_csv(dir_to_feeder+'\\voltage_results.csv')

h.helicsFederateFinalize(fed)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Federate finalized")

