# -*- coding: utf-8 -*-
"""
Transmission simulator using Andes
"""

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
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import andes


##################### First define a broker for total cosim ###########################

helicsversion = h.helicsGetVersion()
print("Helics version = {}".format(helicsversion))
# start a broker inside the file
brokerinitstring = "-f 3 --name=mainbroker" # 3 is the number of federates connecting

# Create broker #
broker = h.helicsCreateBroker("zmq", "", brokerinitstring)
isconnected = h.helicsBrokerIsConnected(broker)
if isconnected == 1:
    print("Broker created and connected")

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

########## Create federate ###############

# define federate information (configuration)
fedinfo = h.helicsCreateFederateInfo()

fedinitstring = "--broker=mainbroker --federates=1" # this string is for defining the core
h.helicsFederateInfoSetCoreName(fedinfo, f"{federate_name}") # define name
h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq") # core type
h.helicsFederateInfoSetCoreInitString(fedinfo, fedinitstring) # define number fo federate and tell the federate it is the main broker
h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, 0.01)
#h.helicsFederateInfoSetLoggingLevel(fedinfo, 5)  # from loglevel in json

# create value federate based on federate info: this type of federate is used for exchange electrical information
fed = h.helicsCreateValueFederate(f"{federate_name}", fedinfo)
print(f"{federate_name}: Combination federate created", flush=True)

# ###################  initialize transmission systems #####################################
andes.main.config_logger(stream_level=20)
ieee14 = andes.get_case('ieee14/ieee14_pvd1_2DistBus.xlsx')
#ieee14 = andes.get_case('ieee14/ieee14_pvd1_debug.xlsx')

ss = andes.load(ieee14, setup=False, no_output=True)
# this is to add fault
#ss.add("Toggler", dict(model='SynGen', dev="GENROU_3", t=10.0))

ss.setup()

# use constant power model for PQ (we will come back to this later)
ss.PQ.config.p2p = 1
ss.PQ.config.q2q = 1
ss.PQ.config.p2z = 0
ss.PQ.config.q2z = 0

# turn off under-voltage PQ-to-Z conversion
ss.PQ.pq2z = 0

#perform initial power flow for dynamic simulation initialization
ss.PFlow.run()

#time domain simulation initialization
ss.TDS.init()

#first run 0.1 to make sure everything runs well
ss.TDS.config.tf = step_time

# start the 0.1 second dynamic simulation
ss.TDS.run()
ss.dae.ts.y
shed_buses = ss.PQ.bus.v
pq_shed_idx = ss.PQ.find_idx(keys='bus', values=shed_buses)

# record the initial system load
pq_p = ss.PQ.get(src='Ppf', idx=pq_shed_idx, attr='v')

# pq_p = array([0.217, 0.5  , 0.478, 0.076, 0.15 , 0.295, 0.09 , 0.035, 0.061,
#        0.135, 0.2  ]

# Sbase = 100 MW

# dae: differential–algebraic equation

# get the load time series randomly choose
consistent_random_object = np.random.RandomState(123)
Load_timeseries = consistent_random_object.normal(1, 0, int(total_time/step_time))
#Load_timeseries_df = pd.DataFrame(Load_timeseries)

# ss.Bus.v.a = array([14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27])

# register the publication
#pub = h.helicsFederateRegisterGlobalTypePublication(fed, "voltage", "complex", "")
for k, v in publications.items():
    pub = h.helicsFederateRegisterGlobalTypePublication(fed, v['topic'], "complex", "") # register to helics
    PUBLICATIONS[k] = pub # store the HELICS object

for k, v in subscriptions.items():
    sub = h.helicsFederateRegisterSubscription(fed, v['topic'], "")
    SUBSCRIPTIONS[k] = sub  # store the HELICS object
#sub = h.helicsFederateRegisterSubscription(fed, "load", "")

############### Entering Execution Mode ########################
h.helicsFederateEnterExecutingMode(fed)
print(f"{federate_name}: Entering execution mode", flush=True)

print(f"===========Start simulation==================")

current_time = 0
for request_time in range(0, int(total_time), int(step_time)):
    while current_time < request_time:
        current_time = h.helicsFederateRequestTime(fed, request_time)
    #print(f"request_time={request_time}")
    # set power for all loads
    pq_p_new = pq_p * Load_timeseries[int(current_time)]
    ss.PQ.set(src='Ppf', idx=pq_shed_idx, attr='v', value=pq_p_new)
    # here set the power from distribution (bus index=4)
    for key, sub in SUBSCRIPTIONS.items():
        val = h.helicsInputGetComplex(sub) # val is P, Q
        bus_name = subscriptions[key]['element_name']
        bus_PQ_index = int(subscriptions[key]['bus_PQ_index'])

        P, Q = val
        print("Received active power from {} at time {}: {} kw".format(key, current_time, P))
        print("Received reactive power (not use) from {} at time {}: {} kvar".format(key, current_time, Q))
        # convert to pu
        P = P/1e5
        Q = Q/1e5
        if current_time ==0:
            print("manually set up first step load bus P and Q")
            P = ss.PQ.p0.v[int(bus_PQ_index)]
            Q = 0
        else:
            ss.PQ.set(src='Ppf', idx=pq_shed_idx[int(bus_PQ_index)], attr='v', value=P) # set load as P
        print(f"total_bus_load = {ss.PQ.p0.v}")
    # start the 1 seconds dynamic simulation
    ss.TDS.config.tf = current_time + step_time
    ss.TDS.run()
    ## get the PUBLICATION OUT
    for key, pub in PUBLICATIONS.items():
        if publications[key]['value']=='Voltage':
            bus_name = publications[key]['element_name']
            element_type = publications[key]['element_type']
            val1 = ss.Bus.v.v[int(bus_name)-1]
            val2 = ss.Bus.a.v[int(bus_name)-1]

            print("Sent voltage mag at time {}: {} pu from {} {}".format(current_time, val1, element_type, bus_name))
            print("Sent voltage ang at time {}: {} rad from {} {}".format(current_time, val2, element_type, bus_name))
        # get voltage and angle and publish
            print(f"Bus_voltages = {ss.Bus.v.v}")
        h.helicsPublicationPublishComplex(pub, val1, val2)

    # if dynamic simulation can't converge, terminate the simulation
    if ss.exit_code != 0:
        raise ValueError(current_time)



ss.TDS.load_plotter()
print(ss.dae.ts.y.shape)
#plot the system frequency
ss.TDS.plt.plot(ss.ACEc.f, ytimes=60, ylabel='Frequency (Hz)')

# #plot the system ACE
#ss.TDS.plt.plot(ss.ACEc.ace, ytimes=100, ylabel='ACE (MW)')
#
# #plot the bus voltage magnitude
#ss.TDS.plt.plot(ss.Bus.v, a=(0, 1, 2, 6), ylabel='Voltage (p.u.)')
# # get all voltage and save

y_object = ss.dae.ts.y

dae_ts_y = ss.dae.ts.y[:, ss.Bus.v.a[3]]
#np.savetxt("dae_ts_y.csv", dae_ts_y, delimiter=",")
# after the loop
voltage_all = ss.dae.ts.y[:, ss.Bus.v.a]
voltage_PQ_3 = ss.dae.ts.y[:, ss.Bus.v.a[3]]
dae_time = ss.dae.ts.t
dae_frequency = ss.dae.ts.y[:, ss.ACEc.f.a]*60
dae_ACE = ss.dae.ts.y[:, ss.ACEc.ace.a]*100

print(y_object.shape)
# np.savetxt("voltage_all_fault.csv", voltage_all, delimiter=",")
# np.savetxt("voltage_PQ_3_fault.csv", voltage_PQ_3, delimiter=",")
# np.savetxt("dae_time_fault.csv", dae_time, delimiter=",")
# np.savetxt("dae_frequency_fault.csv", dae_frequency, delimiter=",")
# np.savetxt("dae_ACE_fault.csv", dae_ACE, delimiter=",")

# np.savetxt("voltage_all.csv", voltage_all, delimiter=",")
# np.savetxt("voltage_PQ_3.csv", voltage_PQ_3, delimiter=",")
# np.savetxt("dae_time.csv", dae_time, delimiter=",")
# np.savetxt("dae_frequency.csv", dae_frequency, delimiter=",")
# np.savetxt("dae_ACE.csv", dae_ACE, delimiter=",")

h.helicsFederateFinalize(fed)
print(f"{federate_name}: Federate finalized",flush=True)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Broker disconnected")

