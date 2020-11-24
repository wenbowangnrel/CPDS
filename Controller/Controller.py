# -*- coding: utf-8 -*-
"""
Controller simulator
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

dir_to_Controller = os.getcwd()

################# read in config file ###########################################
print("reading json")
filename = "Controller.json"
with open(filename) as f:
    data = json.loads(f.read())
    federate_name = data["name"]
    total_time = data["total_time"]
    simulation_step_time = data["simulation_step_time"]
    control_interval = data["control_interval"]
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
h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, 0.01)

# create the value federate: this type of federate is used for exchange electrical information
fed = h.helicsCreateCombinationFederate(f"{federate_name}", fedinfo)
print(f"{federate_name}: Combination federate created", flush=True)

# define pub and sub through json
for k, v in publications.items():
    pub = h.helicsFederateRegisterTypePublication(fed, v["topic"], v["type"], "")
    PUBLICATIONS[k] = pub
for k, v in subscriptions.items():
    sub = h.helicsFederateRegisterSubscription(fed, v["topic"], "")
    SUBSCRIPTIONS[k] = sub

# define pub and sub directly:
#sub = h.helicsFederateRegisterSubscription(fed, "voltage", "")
#pub = h.helicsFederateRegisterGlobalTypePublication(fed, "34Bus/Totalpower", "scalar", "")

h.helicsFederateEnterExecutingMode(fed)
################### Now start executation ###################

current_time = 0

for request_time in np.arange(0, total_time, simulation_step_time):
    while current_time < request_time:

        current_time = h.helicsFederateRequestTime(fed, request_time)
        #print(current_time)
    print(f"current_time={current_time}")

    # get frequency results
    for key, sub in SUBSCRIPTIONS.items():
        val = h.helicsInputGetDouble(sub)
        val_unit = subscriptions[key]["unit"]
        if subscriptions[key]['value'] == 'f_delta':
            print("Received f_delta at time {}: {} {}".format(current_time, val,val_unit))
        # use val do something: check what is val unit


        voltage, angle_rad = val
        # convert angle to degree
        angle_deg = np.degrees(angle_rad)




    # send AGC results to a Turbine











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
        load_mult = load_profile_scaled.iloc[int(current_time)]
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

