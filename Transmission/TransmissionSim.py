# -*- coding: utf-8 -*-
# TODO: add transmission simulator

# TODO: fetch output information


import cmath
import json
import math
import re
import os
import sys
import numpy as np
import helics as h
import opendssdirect as odd
#NEW
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

import andes

load_profile_df = pd.read_csv(os.getcwd() + '\\load_profile.csv', index_col=0)
load_profile = load_profile_df.iloc[:, 0]

old_min = load_profile.min()
old_max = load_profile.max()
new_max = 1
new_min = 0.9
load_profile_scaled = (load_profile - old_min) / (old_max - old_min) * (new_max - new_min) + new_min


fig, ax1 = plt.subplots()
ax = load_profile_scaled.plot()


andes.main.config_logger()

#pd.read_csv('')

pfss = andes.load('network_model/t3ps.raw')
pfss.PV.cache.refresh()
pfss.PQ.cache.refresh()
# setup system
#pfss.setup()
# run power flow
pfss.PFlow.run()

print(pfss.PV.p0.v)
PQ_orig = pfss.PQ.p0.v # array of load at the PQ points

pfss.Bus.v.v # voltage for all the buses

# read load profile
# system nominal voltage 230 v

################# reading in config file ###########################################
filename = "TransmissionSim.json"
with open(filename) as f:
    data = json.loads(f.read())
    federate_name = data["name"]
    total_time = data["total_time"]
    step_time = data["step_time"]
    subscriptions = data["subscriptions"]
    publications = data["publications"]

PUBLICATIONS = {}
SUBSCRIPTIONS = {}

fedinfo = h.helicsCreateFederateInfo()

h.helicsFederateInfoSetCoreName(fedinfo, f"{federate_name}")
h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
h.helicsFederateInfoSetCoreInitString(fedinfo,
                                      f"--federates=1 --broker_address=tcp://{master_ip} --interface=tcp://{fed_ip}")
h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, 1.0)

fed = h.helicsCreateCombinationFederate(f"{federate_name}", fedinfo)
print(f"{federate_name}: Combination federate created", flush=True)

for k, v in publications.items():
    pub = h.helicsFederateRegisterTypePublication(fed, v["topic"], "complex", "")
    PUBLICATIONS[k] = pub
for k, v in subscriptions.items():
    sub = h.helicsFederateRegisterSubscription(fed, v["topic"], "")
    SUBSCRIPTIONS[k] = sub

epid = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name + "_ep", "")

h.helicsFederateEnterExecutingMode(fed)
print(f"{federate_name}: Entering execution mode", flush=True)

#num_sim = 75 # 5*60/4
#num_sim = 5








v_results = []
num_v = pfss.Bus.v.v.shape[0]
v_results_np = np.zeros([num_sim, num_v])

for i in range(num_sim):
    print(f"Doing {i} time step: at load multiply {load_profile_scaled.iloc[i]}")
    # change load of TransmissionSim
    # TODO how to change input
    # load index [2, 3, 5, 6, 8, 10, 12]
    pfss.PQ.p0.v = PQ_orig*load_profile_scaled.iloc[i]

    # n = 0
    # for ldi in list([2, 3, 5, 6, 8, 10, 12]):  # wenbo notes: update load, Sbase = 100 MVA
    #     pfss.PQ.p0.v[ldi] = pfss.PQ.p0.v[ldi]*load_profile_scaled.iloc[i]
    #     n = n + 1

    # transmission run step function
    pfss.PV.cache.refresh()
    pfss.PQ.cache.refresh()
    # setup system
    pfss.setup()
    # run power flow
    pfss.PFlow.run()

    # TODO get the results variable out
    v_all = pfss.Bus.v.v
    v_results.append(pfss.Bus.v.v)
    print(pfss.Bus.v.v)
    v_results_np[i, :] = pfss.Bus.v.v

v_results_df = pd.DataFrame(v_results_np)

#fig, ax2 = plt.subplots()
ax2 = v_results_df.plot()
plt.show()


