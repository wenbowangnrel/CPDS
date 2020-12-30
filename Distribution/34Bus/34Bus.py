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
print(f"python_dir={os.getcwd()}")
dir_to_project = os.path.join(dir_to_feeder,'..','..',)
dir_to_Algorithm = os.path.join(dir_to_project, 'Algorithm_utils')
sys.path.append(dir_to_Algorithm)
import vsm_utils

################# read in config file ###########################################
print("reading json")
filename = "34Bus.json"
with open(filename) as f:
    data = json.loads(f.read())
    federate_name = data["name"]
    total_time = data["total_time"]
    simulation_step_time = data["simulation_step_time"]
    subscriptions = data["subscriptions"]
    publications = data["publications"]
print("reading json okay!")


# read time series load profile data
# load_profile_df = pd.read_csv(dir_to_feeder + '\\DSSfiles\\load_profile.csv', index_col=0)
# load_profile = load_profile_df.iloc[:, 0]
#
# # convert it to the range in [0.9, 1]
# old_min = load_profile.min()
# old_max = load_profile.max()
# new_max = 1.1
# new_min = 0.9
# load_profile_scaled = (load_profile - old_min) / (old_max - old_min) * (new_max - new_min) + new_min
# load_profile_scaled = pd.concat([load_profile_scaled, load_profile_scaled])

# fig, ax1 = plt.subplots()
# ax1 = load_profile.plot()

consistent_random_object = np.random.RandomState(321)
load_profile_random = consistent_random_object.normal(1, 0.02, int(total_time))

# test run Opendss feeder
feeder_name = '34Bus'
print('------ Running the {} feeder in opendss'.format(feeder_name))
run_command('compile DSSfiles/Master.dss')
if dss.Text.Result() == '':
    print('------ Success for the test run -----')
else:
    print('------ Opendss failed ----')
    print(f'Error is "{dss.Text.Result()}"!')
print(f"After opendss run os.getcwd()={os.getcwd()}")

# get load kw values
BASEKV = dss.Vsources.BasekV()
loadname_all=[]
loadkw_all=[]
loadkvar_all=[]
num_loads = dss.Loads.Count()
dss.Loads.First()
for i in range(num_loads):
    loadname = dss.Loads.Name()
    #print(f'loadname={loadname}')
    loadkw = dss.Loads.kW()
    loadkvar = dss.Loads.kvar()
    loadname_all.append(loadname)
    loadkw_all.append(loadkw)
    loadkvar_all.append(loadkvar)
    dss.Loads.Next()

loadkw_dict = dict(zip(loadname_all, loadkw_all))
loadkvar_dict = dict(zip(loadname_all, loadkvar_all))
allnodenames = dss.Circuit.AllNodeNames()
num_nodes = len(allnodenames)

print(f"Total power base line is {dss.Circuit.TotalPower()}")
print(f"allloadnames={dss.Loads.AllNames()}")
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
#import pdb;pdb.set_trace()
# define pub and sub through json
for k, v in publications.items():
    pub = h.helicsFederateRegisterTypePublication(fed, v["topic"], "complex", "")
    PUBLICATIONS[k] = pub
for k, v in subscriptions.items():
    sub = h.helicsFederateRegisterSubscription(fed, v["topic"], "")
    SUBSCRIPTIONS[k] = sub

epid = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep", "")

h.helicsFederateEnterExecutingMode(fed)
################### Now start executation ###################

current_time = 0
allbusmagpu_ts = []
totalpower_ts = []

#index_DERs = np.arange(num_nodes-10, num_nodes, 1) # attach DER to the last 10 nodes
index_DERs = np.array([12, 25, 26, 27, 28, 29, 30, 92, 93, 94])
# here define DER power output=500
scale = 0.478*100/2.032
DER_output = np.ones(10)*500/scale
i=1
for ind in index_DERs:
    nodename = allnodenames[ind]
    dss.Circuit.SetActiveBus(nodename)
    buskv = dss.Bus.kVBase()
    run_command(f'New generator.der_{i} bus1={nodename} Phases=1 Conn=Wye Model=1 kV={buskv} kw={DER_output[i-1]} kvar=0')
    i=i+1
# DER output should come from transmission sim
print(f"index_DERs = {index_DERs}")
for request_time in np.arange(0, total_time, simulation_step_time):
    while current_time < request_time:
        current_time = h.helicsFederateRequestTime(fed, request_time)
        #print(current_time)
    print(f"current_time={current_time}")
    # add DER power
    while h.helicsEndpointHasMessage(epid):
        m = h.helicsEndpointGetMessage(epid)
        message = json.loads(m.data)
        DER_output = np.array(message)
        print(f"Received message at time {current_time}: DER_power {DER_output} in kw")
    # based on the DER_output modify DER
    j=1
    for ind in index_DERs:
        nodename = allnodenames[ind]
        run_command(f'Edit generator.der_{j} kw={DER_output[j-1]}')
        j=j+1

    dss.run_command("Solve")
    # save some results
    allbusmagpu = dss.Circuit.AllBusMagPu()
    allbusmagpu_ts.append(allbusmagpu)
    totalpower_ts.append(dss.Circuit.TotalPower())
    # total power adjust amount of total DER_output
    S = dss.Circuit.TotalPower() # the total power is negative
    S[0] = S[0] - np.sum(DER_output) # adjust
    #
    print(f"Total power={dss.Circuit.TotalPower()}")
    print(f"DER power is {np.sum(DER_output)}")
    print(f"Overall after adjustment S={S}")
    P = -S[0]
    Q = -S[1]

    P = P*scale
    Q = Q*scale
    # now publish the results
    h.helicsPublicationPublishComplex(pub, P, Q)
    print("Sent Active power at time {}: {} kw".format(current_time, P))
    print("Sent Reactive power at time {}: {} kvar".format(current_time, Q))
    if current_time % 10 < 1e-4:
        # calculate vsm
        allbusmagpu_base = np.array(allbusmagpu)
        print("********* getting vsm ****************")
        #print(f'before control mode = {dss.Solution.ControlMode()}')
        print(f'min of voltage = {min(allbusmagpu_base)}')
        print(f'max of voltage = {max(allbusmagpu_base)}')
        vsm = vsm_utils.get_vsm(dss, feeder_name, index_DERs, allbusmagpu_base)
        #print(f'after control mode = {dss.Solution.ControlMode()}')
        #print(f'after dss.Loads.Count()={dss.Loads.Count()}')
        print("***************************************")

        # send vsm to aggregator
        h.helicsEndpointSendBytesTo(epid, json.dumps([vsm.tolist(), allbusmagpu_base.tolist()]), "Aggregator_DER_34Bus_ep2")
        print(f'Sending vsm to Aggregator_DER_34Bus_ep2 at time {current_time}: showing a block of vsm {vsm[index_DERs,:]}')

    # send this vsm and v_base to aggregator

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
                angle_deg = 0
                voltage = 1
            dss.Vsources.AngleDeg(angle_deg)
            dss.Vsources.PU(voltage)
    # change load according to load profile
    dss.Loads.First()
    for j in range(num_loads):
        loadname = dss.Loads.Name()
        #print(f"{loadname} kw={dss.Loads.kW()}")
        #text = run_command("? Load.p_perturb.enabled")

        # now calculate kw and kvar based on the csv
        load_mult = load_profile_random[int(current_time)]
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

