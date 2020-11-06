# -*- coding: utf-8 -*-
# TODO add 13Bus test feeder simulator
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


PUBLICATIONS = {}
SUBSCRIPTIONS = {}


# read time series load profile data
load_profile_df = pd.read_csv(os.getcwd() + '\\37Bus\\load_profile.csv', index_col=0)
load_profile = load_profile_df.iloc[:, 0]

old_min = load_profile.min()
old_max = load_profile.max()
new_max = 1
new_min = 0.9
load_profile_scaled = (load_profile - old_min) / (old_max - old_min) * (new_max - new_min) + new_min
load_profile_scaled = pd.concat([load_profile_scaled, load_profile_scaled])
# add more



# fig, ax1 = plt.subplots()
# ax1 = load_profile.plot()

# test run
feeder_name = '37Bus'
print('------ Running the {} feeder in opendss'.format(feeder_name))
run_command('compile ' + feeder_name + '/Master.dss')
if dss.Text.Result() == '':
    print('------ Success for the test run -----')
else:
    print('------ Opendss failed ----')

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

# num_sim = 75
# num_sim = 150

################# read in config file ###########################################
print("reading json")
filename = "..\\37Bus.json"
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

fedinfo = h.helicsCreateFederateInfo()

h.helicsFederateInfoSetCoreName(fedinfo, f"{federate_name}")
h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
h.helicsFederateInfoSetCoreInitString(fedinfo, "--federates=1")
h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, 1.0)

# create the federate
fed = h.helicsCreateValueFederate(f"{federate_name}", fedinfo)
print(f"{federate_name}: Combination federate created", flush=True)

# for k, v in publications.items():
#     pub = h.helicsFederateRegisterTypePublication(fed, v["topic"], "complex", "")
#     PUBLICATIONS[k] = pub
# for k, v in subscriptions.items():
#     sub = h.helicsFederateRegisterSubscription(fed, v["topic"], "")
#     SUBSCRIPTIONS[k] = sub
sub = h.helicsFederateRegisterSubscription(fed, "voltage", "")
pub = h.helicsFederateRegisterGlobalTypePublication(fed, "load", "complex", "")

print('Before')
h.helicsFederateEnterExecutingMode(fed)
print('After')

def cart2pol(x, y):
    rho = np.sqrt(x**2 + y**2)
    phi = np.arctan2(y, x)
    return(rho, phi)

current_time = 0

for request_time in range(0, int(total_time), int(step_time)):
    while current_time < request_time:

        current_time = h.helicsFederateRequestTime(fed, request_time)
        #print(current_time)
    print(f"current_time={current_time}")

    dss.run_command("Solve")
    #dss.run_command("show voltage ln nodes")
    S = dss.Circuit.TotalPower()
    P = S[0]
    Q = S[1]
    print("Sent Active power at time {}: {} ".format(request_time, -P/2500))
    print("Sent Reactive power at time {}: {} ".format(request_time, -Q/2500))

    h.helicsPublicationPublishComplex(pub, -P/2500, -Q/2500)

    voltage, angle_rad = h.helicsInputGetComplex(sub)
    # convert angle to degree
    angle_deg = np.degrees(angle_rad)

    #dss.Circuit.SetActiveClass("Vsource")
    #dss.Circuit.SetActiveElement("source")
    if current_time == 0:
        dss.Vsources.AngleDeg(0)
        dss.Vsources.PU(1)
    else:
        dss.Vsources.AngleDeg(angle_deg)
        dss.Vsources.PU(voltage)
    print("Receive voltage mag at time {}: {} ".format(request_time, voltage))
    print("Receive voltage ang at time {}: {} ".format(request_time, angle_deg))




    # relative 40 multiply P

h.helicsFederateFinalize(fed)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Federate finalized")





"""

allbusmagpu_ts = []

totalpower_ts = []

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
    allbusmagpu_ts.append(allbusmagpu)
    totalpower_ts.append(dss.Circuit.TotalPower())
# change list of results to dataframe
v_results_df = pd.DataFrame(allbusmagpu_ts)
totalpower_array = np.array(totalpower_ts)
totalpower_results_df = pd.DataFrame(-totalpower_array)
#fig, ax2 = plt.subplots()


ax2 =v_results_df.plot(legend=False)

ax3 = totalpower_results_df.plot()
plt.show()




"""