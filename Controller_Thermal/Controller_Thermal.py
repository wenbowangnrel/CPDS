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
filename = "Controller_Thermal.json"
with open(filename) as f:
    data = json.loads(f.read())
    federate_name = data["name"]
    total_time = data["total_time"]
    simulation_step_time = data["simulation_step_time"]
    num_TurbineGov = data["num_TurbineGov"]
    # subscriptions = data["subscriptions"]
    # publications = data["publications"]
    endpoints = data["endpoints"]
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
#import pdb;pdb.set_trace()
# define pub and sub through json
# for k, v in publications.items():
#     pub = h.helicsFederateRegisterTypePublication(fed, v["topic"], v["type"], "")
#     PUBLICATIONS[k] = pub
# for k, v in subscriptions.items():
#     sub = h.helicsFederateRegisterSubscription(fed, v["topic"], "")
#     SUBSCRIPTIONS[k] = sub
# register endpoints
epid = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep", "") # receive ACE

# filter1_id = h.helicsFederateRegisterFilter(fed, h.HELICS_FILTER_TYPE_CUSTOM, "filter1")
# h.helicsFilterAddDestinationTarget(filter1_id, "TransmissionSim_ep1")

#h.helicsFilterSet(filter1_id, "delay", 0.1)

# define pub and sub directly:

h.helicsFederateEnterExecutingMode(fed)
print(f"{federate_name}: Entering execution mode", flush=True)

################### Now start executation ###################

current_time = 0
paux0_new = np.zeros(num_TurbineGov)
KI=0.2
for request_time in np.arange(0, total_time, simulation_step_time):
    while current_time < request_time:
        current_time = h.helicsFederateRequestTime(fed, request_time)
    print(f"current_time={current_time}")

    # initialized ACE = 0
    if current_time == 0:
        ACE = 0

    # check message from transmission (ACE is float)
    while h.helicsEndpointHasMessage(epid):
        m = h.helicsEndpointGetMessage(epid)
        message = json.loads(m.data)
        ACE = message
        print(f"Received message at time {current_time}: ACE {ACE}")
    # TODO normal condition should be 0.18
    paux0_new = paux0_new - ACE * simulation_step_time * 0.18 * KI
    # if current_time <= 5:
    #     paux0_new = paux0_new - ACE*simulation_step_time*0.18*KI
    # else:
    #     paux0_new = paux0_new - ACE * simulation_step_time * 0.225 * KI

    print(f"paux0_new={paux0_new}")
    if current_time % 4 <= 1e-6: # it was 4 sec
        h.helicsEndpointSendTo(epid, "TransmissionSim_ep1", json.dumps(paux0_new.tolist()))

        print(f"sending {paux0_new}")

h.helicsFederateFinalize(fed)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Federate finalized")

