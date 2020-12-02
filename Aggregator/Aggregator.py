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
filename = "Aggregator.json"
with open(filename) as f:
    data = json.loads(f.read())
    federate_name = data["name"]
    total_time = data["total_time"]
    simulation_step_time = data["simulation_step_time"]
    num_DER = data["num_DER"]
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
#import pdb;pdb.set_trace()
# define pub and sub through json
for k, v in publications.items():
    pub = h.helicsFederateRegisterTypePublication(fed, v["topic"], v["type"], "")
    PUBLICATIONS[k] = pub
for k, v in subscriptions.items():
    sub = h.helicsFederateRegisterSubscription(fed, v["topic"], "")
    SUBSCRIPTIONS[k] = sub

# define pub and sub directly:

h.helicsFederateEnterExecutingMode(fed)
################### Now start executation ###################

current_time = 0
PVD_AGC_response = np.zeros(num_DER)
for request_time in np.arange(0, total_time, simulation_step_time):
    while current_time < request_time:

        current_time = h.helicsFederateRequestTime(fed, request_time)

    print(f"current_time={current_time}")

    # get ACE results
    for key, sub in SUBSCRIPTIONS.items():
        if subscriptions[key]['value'] == 'ACE':
            #if current_time % subscriptions[key]['sub_interval']<=1e-6:
            val = h.helicsInputGetDouble(sub)
            val_unit = subscriptions[key]["unit"]
            print(f"Received {subscriptions[key]['value']} at time {current_time}: {val} {val_unit}.")

            if current_time == 0:
                val = 0
                val_unit = subscriptions[key]["unit"]
                print(f"Manually set up first step ACE {val} {val_unit}.")

            ##### use val (ACE) calculate AGC  ###########
            PVD_AGC_response = PVD_AGC_response - val*0.02*0.001 # this is vector
            print(f"PVD_AGC_response={PVD_AGC_response}")
    # get AGC published
    for key, pub in PUBLICATIONS.items():
        if publications[key]['value'] == 'AGC':
            element_unit = publications[key]['unit']
            element_name = publications[key]['element_name']
            if (10*current_time) % (10*publications[key]['pub_interval']) <= 1e-6:
                print(f"Sent AGC signal at time {current_time}: {PVD_AGC_response} {element_unit} from {element_name}.")
                h.helicsPublicationPublishVector(pub, list(PVD_AGC_response))


h.helicsFederateFinalize(fed)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Federate finalized")

