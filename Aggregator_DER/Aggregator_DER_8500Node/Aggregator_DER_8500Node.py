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
epid = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep", "")
# define pub and sub directly:

h.helicsFederateEnterExecutingMode(fed)
print(f"{federate_name}: Entering execution mode", flush=True)
################### Now start executation ###################

current_time = 0
PVD_AGC_response = np.zeros(num_DER)
for request_time in np.arange(0, total_time, simulation_step_time):
    while current_time < request_time:

        current_time = h.helicsFederateRequestTime(fed, request_time)

    print(f"current_time={current_time}")

    # initialized ACE = 0
    if current_time == 0:
        ACE = 0

    # check message from transmission: get ACE
    while h.helicsEndpointHasMessage(epid):
        m = h.helicsEndpointGetMessage(epid)
        message = json.loads(m.data)
        ACE = message
        print(f"Received message at time {current_time}: ACE {message}")

    PVD_AGC_response = PVD_AGC_response - ACE*0.02*0.001 # this is vector
    print(f"PVD_AGC_response={PVD_AGC_response}")

    if current_time % 4 <= 1e-6:
        h.helicsEndpointSendTo(epid, "TransmissionSim_ep3", json.dumps(PVD_AGC_response.tolist()))
        print(f"sending PVD_AGC_response_8500Node={PVD_AGC_response}")

h.helicsFederateFinalize(fed)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Federate finalized")

