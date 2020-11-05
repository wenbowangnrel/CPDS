# -*- coding: utf-8 -*-
# TODO: add transmission simulator

# TODO: fetch output information


import cmath
import json
import math
import re
import os
import sys
import time
import numpy as np
import helics as h
import opendssdirect as odd
#NEW
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

import andes


def pol2cart(rho, phi):
    x = rho * np.cos(phi)
    y = rho * np.sin(phi)
    return x, y

helicsversion = h.helicsGetVersion()
print("Helics version = {}".format(helicsversion))
# start a broker inside the file
brokerinitstring = "-f 2 --name=mainbroker" # 2 is the number of federates connecting

# Create broker #
print("Creating Broker")
broker = h.helicsCreateBroker("zmq", "", brokerinitstring)
print("Created Broker")

print("Checking if Broker is connected")
isconnected = h.helicsBrokerIsConnected(broker)
print("Checked if Broker is connected")

if isconnected == 1:
    print("Broker created and connected")

# broker.disconnect()

# borker.isconnected()



load_profile_df = pd.read_csv(os.getcwd() + '\\load_profile.csv', index_col=0)
load_profile = load_profile_df.iloc[:, 0]

old_min = load_profile.min()
old_max = load_profile.max()
new_max = 1
new_min = 0.9
load_profile_scaled = (load_profile - old_min) / (old_max - old_min) * (new_max - new_min) + new_min
load_profile_scaled = pd.concat([load_profile_scaled, load_profile_scaled])

# fig, ax1 = plt.subplots()
# ax = load_profile_scaled.plot()


andes.main.config_logger()
pfss = andes.load('network_model/t3ps.raw')
pfss.PV.cache.refresh()
pfss.PQ.cache.refresh()
# setup system
#pfss.setup()
# run power flow
pfss.PFlow.run()

print(pfss.PV.p0.v)
PQ_orig = pfss.PQ.p0.v # array of load at the PQ points



allbusv = pfss.Bus.v.v # voltage for all the buses
allbusang = pfss.Bus.a.v
bus_idx = pfss.Bus.idx.v
# get the load index
loadbus_name = pfss.PQ.bus.v
# get the load value
loadp = pfss.PQ.p0.v
loadq = pfss.PQ.q0.v
loadname_p = dict(zip(loadbus_name, loadp))
loadname_q = dict(zip(loadbus_name, loadq))
############ put in the index ##########
loadbus_idx = [] # this will have the same index as voltage
for i in loadbus_name:
    loadbus_idx.append(bus_idx.index(i))

### manual define one bus for publication ###
loadbusname_publication = 2
# val for publication
voltage_publication = allbusv[bus_idx.index(loadbusname_publication)]
angle_publication = allbusang[bus_idx.index(loadbusname_publication)]

#pd.read_csv('')
# pfss.as_dict() # check all dict


################# reading in config file ###########################################
print("reading json")
filename = "TransmissionSim.json"
with open(filename) as f:
    data = json.loads(f.read())
    federate_name = data["name"]
    total_time = data["total_time"]
    step_time = data["step_time"]
    subscriptions = data["subscriptions"]
    publications = data["publications"]
print("reading json okay!")
PUBLICATIONS = {}
SUBSCRIPTIONS = {}

########## Create the federate info object ###############

fedinfo = h.helicsCreateFederateInfo()

fedinitstring = "--broker=mainbroker --federates=1"

h.helicsFederateInfoSetCoreName(fedinfo, f"{federate_name}")
h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
h.helicsFederateInfoSetCoreInitString(fedinfo, fedinitstring)
h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, 1.0)
#h.helicsFederateInfoSetLoggingLevel(fedinfo, 5)  # from loglevel in json

# create combine/value federate
fed = h.helicsCreateValueFederate(f"{federate_name}", fedinfo)
print(f"{federate_name}: Combination federate created", flush=True)

# register the publication
pub = h.helicsFederateRegisterGlobalTypePublication(fed, "voltage", "complex", "")
sub = h.helicsFederateRegisterSubscription(fed, "load", "")
#time.sleep(10)
print('Before')
############### Entering Execution Mode ########################
h.helicsFederateEnterExecutingMode(fed)
print(f"{federate_name}: Entering execution mode", flush=True)
print('After')






# read load profile
# system nominal voltage 230 v
num_sim = 150
v_results = []
num_v = pfss.Bus.v.v.shape[0]
v_results_np = np.zeros([num_sim, num_v])

# I may need to initialized P and Q.
# P, Q =

print(f"===========Start simulation==================")
current_time = 0
for request_time in range(0, int(total_time), int(step_time)):
    while current_time < request_time:
        current_time = h.helicsFederateRequestTime(fed, request_time)

    print(f"request_time={request_time}")


    pfss.PV.cache.refresh()
    pfss.PQ.cache.refresh()
    # run one step of power flow
    pfss.PFlow.run()




    P, Q = h.helicsInputGetComplex(sub)

    print("Receive active power at time {}: {} ".format(request_time, P))
    print("Receive reactive power (not use) at time {}: {} ".format(request_time, Q))
    # change the P, Q

    pfss.PQ.p0.v = PQ_orig * load_profile_scaled.iloc[int(request_time)]
    if current_time == 0:
        print("condition first step")
        P = pfss.PQ.p0.v[0]
        Q = 0
    else:
        pfss.PQ.p0.v[0] = P


    allbusv = pfss.Bus.v.v
    allbusang = pfss.Bus.a.v

    voltage = allbusv[bus_idx.index(loadbusname_publication)]
    angle = allbusang[bus_idx.index(loadbusname_publication)]

    print("Sent voltage mag at time {}: {} ".format(request_time, voltage))
    print("Sent voltage ang at time {}: {} ".format(request_time, angle))

    h.helicsPublicationPublishComplex(pub, voltage, angle)

    # x = {} # can I do nothing
    # # now get the publications
    # for key, pub in PUBLICATIONS.items():
    #     unit = ''
    #     if publications[key]['value'] == 'Voltage':
    #         val = results
    #         unit = "pu"
    # typ = "complex"
    # if typ == "complex":
    #     h.helicsPublicationPublishComplex(pub, val[0], val[1])
    # else:
    #     raise NotImplementedError(f"Unknown type of data {typ}")


    # for key, sub in SUBSCRIPTIONS.items():
    #     val = h.helicsInputGetComplex(sub)
    #     unit = ''
    #     if subscriptions[key]['value'] == 'Powers':
    #         x[subscriptions[key]] = {'kw': val[0], 'kvar': val[1]}
    #         unit = 'kw, kvar'

    # use x change the input for power flow next step




# after the loop
h.helicsFederateFinalize(fed)
print(f"{federate_name}: Federate finalized",flush=True)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Broker disconnected")

""":cvar
#num_sim = 75 # 5*60/4
#num_sim = 5

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
"""