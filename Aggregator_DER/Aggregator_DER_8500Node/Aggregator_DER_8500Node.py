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
print(f"python_dir={os.getcwd()}")
dir_to_project = os.path.join(dir_to_Controller,'..','..',)
dir_to_Algorithm = os.path.join(dir_to_project, 'Algorithm_utils')
sys.path.append(dir_to_Algorithm)
import vsm_utils

################# read in config file ###########################################
print("reading json")
filename = "Aggregator_DER_8500Node.json"
with open(filename) as f:
    data = json.loads(f.read())
    federate_name = data["name"]
    total_time = data["total_time"]
    simulation_step_time = data["simulation_step_time"]
    num_DER = data["num_DER"]
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

# register endpoints
epid1 = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep1", "") # receive ACE
epid2 = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep2", "") # receive vsm/send pvd1_power to feeder
epid3 = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep3", "") # send DER pmax to transmission/receive pvd1 power output from transmission

h.helicsFederateEnterExecutingMode(fed)
print(f"{federate_name}: Entering execution mode", flush=True)
################### Now start executation ###################
vsm = None
allbusmagpu_base = None

scale = 0.295*100/11.96
DER_caps = np.ones(num_DER)*900/scale # in kw
print(f"DER_caps is {DER_caps}")
current_time = 0
PVD_AGC_response = np.zeros(num_DER)
num_nodes = 8531
#index_DERs = np.arange(num_nodes-10, num_nodes, 1) # attach DER to the last 10 nodes
index_DERs = np.array([19, 291, 292, 293, 712, 713, 714, 1419, 1420, 1421])
pvd1_power = np.ones(10)*500/scale # initialize pvd1_power
KI=0.2
for request_time in np.arange(0, total_time, simulation_step_time):
    while current_time < request_time:

        current_time = h.helicsFederateRequestTime(fed, request_time)

    print(f"current_time={current_time}")

    # initialized ACE = 0
    if current_time == 0:
        ACE = 0

    # check message from transmission: get ACE
    while h.helicsEndpointHasMessage(epid1):
        m = h.helicsEndpointGetMessage(epid1)
        message = json.loads(m.data)
        ACE = message
        print(f"Received message at time {current_time}: ACE {message}")

    # check message from Distribution: get vsm
    while h.helicsEndpointHasMessage(epid2):
        m = h.helicsEndpointGetMessage(epid2)
        message = json.loads(m.data)
        vsm = np.array(message[0])
        allbusmagpu_base = np.array(message[1])
        print(f"Received message at time {current_time}: vsm {vsm[index_DERs,:]}")

    # check message from transmission: get DER_power output
    while h.helicsEndpointHasMessage(epid3):
        m = h.helicsEndpointGetMessage(epid3)
        message = json.loads(m.data)
        pvd1_power = np.array(message)*1e5/scale
        print(f"Received message at time {current_time}: pvd1_power {message} 100 MW")

    h.helicsEndpointSendBytesTo(epid2, json.dumps(pvd1_power.tolist()), "8500Node_ep")
    print(f"sending pvd1_power={pvd1_power} in kw to feeder 8500Node.")

    ##### use ACE calculate PVD AGC 2 ###########
    PVD_AGC_response = PVD_AGC_response - ACE*simulation_step_time * 0.005*KI # this is vector
    print(f"PVD_AGC_response={PVD_AGC_response}")

    if current_time % 4 <= 1e-6: # it was 4 sec
        h.helicsEndpointSendBytesTo(epid1, json.dumps(PVD_AGC_response.tolist()), "TransmissionSim_ep3")
        print(f"sending PVD_AGC_response_8500Node={PVD_AGC_response}")

    if current_time % 10 <= 1e-6:
        if vsm is not None and allbusmagpu_base is not None:
            # perform optimization
            DER_headroom_df, total_DER_headroom_limit = vsm_utils.get_DER_local_limit(vsm, DER_caps-pvd1_power, allbusmagpu_base)
            # get output headroom
            print(f"DER_limit_df={DER_headroom_df}")
            total_DER_power_limit = pvd1_power + np.array(DER_headroom_df.solution_value)

            # this DER_limit_df*scale should be sent to Transmission
            h.helicsEndpointSendBytesTo(epid3, json.dumps((total_DER_power_limit*scale/1e5).tolist()), "TransmissionSim_ep5")
            print(f"sending total_DER_power_limit={total_DER_power_limit}")





h.helicsFederateFinalize(fed)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Federate finalized")

