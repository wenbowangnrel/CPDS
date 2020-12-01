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
path_to_TransmissionSim = os.getcwd()

helicsversion = h.helicsGetVersion()
print("Helics version = {}".format(helicsversion))
# start a broker inside the file
brokerinitstring = "-f 5 --name=mainbroker" # 3 is the number of federates connecting

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
    simulation_step_time = data["simulation_step_time"]
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
ss.TDS.config.tf = 0.01

# start the 0.1 second dynamic simulation
ss.TDS.run()
ss.dae.ts.y
shed_buses = ss.PQ.bus.v
pq_shed_idx = ss.PQ.find_idx(keys='bus', values=shed_buses)

# define turbine gov AGC settings: find index and set value
tg_idx = list(ss.TurbineGov._idx2model.keys())
paux0_new_init = np.zeros(len(tg_idx))# - ss.ACEc.ace.v*1/len(tg_idx)
ss.TurbineGov.set(src='paux0',idx=tg_idx, attr='v', value=paux0_new_init)

PVD_names = ss.PVD1.idx.v
PVD_AGC_idx = ss.PVD1.find_idx(keys='idx', values=PVD_names)

PVD_AGC_response = ss.PVD1.get(src='Pext', idx=PVD_AGC_idx, attr='v')
PVD_AGC_response = np.zeros(len(PVD_AGC_idx))




# record the initial system load
pq_p = ss.PQ.get(src='Ppf', idx=pq_shed_idx, attr='v')



# pq_p = array([0.217, 0.5  , 0.478, 0.076, 0.15 , 0.295, 0.09 , 0.035, 0.061,
#        0.135, 0.2  ]

# Sbase = 100 MW

# dae: differential–algebraic equation

# get the load time series randomly choose
consistent_random_object = np.random.RandomState(123)
Load_timeseries = consistent_random_object.normal(1, 0.01, int(total_time/simulation_step_time))
#Load_timeseries_df = pd.DataFrame(Load_timeseries)
pd.DataFrame(Load_timeseries).plot()
# ss.Bus.v.a = array([14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27])
plt.show()
# register the publication
for k, v in publications.items():
    pub = h.helicsFederateRegisterGlobalTypePublication(fed, v['topic'], v['type'], "") # register to helics
    PUBLICATIONS[k] = pub # store the HELICS object

for k, v in subscriptions.items():
    print(k)
    sub = h.helicsFederateRegisterSubscription(fed, v['topic'], "")
    SUBSCRIPTIONS[k] = sub  # store the HELICS object

############### Entering Execution Mode ########################
h.helicsFederateEnterExecutingMode(fed)
print(f"{federate_name}: Entering execution mode", flush=True)

print(f"===========Start simulation==================")

current_time = 0
for request_time in np.arange(0, total_time, simulation_step_time):
    while current_time < request_time:
        current_time = h.helicsFederateRequestTime(fed, request_time)
    print("=============================")
    print(f"request_time={request_time}")
    print(f"current_time={current_time}")
    # set power for all loads
    pq_p_new = pq_p * Load_timeseries[int(current_time/simulation_step_time)]
    ss.PQ.set(src='Ppf', idx=pq_shed_idx, attr='v', value=pq_p_new)
    # here set the power from distribution (bus index=4)
    for key, sub in SUBSCRIPTIONS.items():
        if subscriptions[key]['value']=='Powers': # power meaning it is for distribution systems
            if current_time % subscriptions[key]['sub_interval']<=1e-6:
                val = h.helicsInputGetComplex(sub) # val is P, Q
                bus_name = subscriptions[key]['element_name']
                bus_PQ_index = int(subscriptions[key]['bus_PQ_index'])

                P, Q = val
                print("Received active power from {} at time {}: {} kw".format(key, current_time, P))
                print("Received reactive power (not use) from {} at time {}: {} kvar".format(key, current_time, Q))
                # convert to pu
                P = P/1e5
                Q = Q/1e5

            if current_time == 0:
                print("manually set up first step load bus P and Q")
                P = ss.PQ.p0.v[int(bus_PQ_index)]
                Q = 0

            ss.PQ.set(src='Ppf', idx=pq_shed_idx[int(bus_PQ_index)], attr='v', value=P) # set load as P
            #print(f"total_bus_load = {ss.PQ.p0.v}")
        if subscriptions[key]['value']=='AGC_signal_C':
            if current_time % subscriptions[key]['sub_interval']<=1e-6:
                val = h.helicsInputGetVector(sub)
                val_unit = subscriptions[key]['unit']
                if current_time == 0:
                    val = paux0_new_init
                    val_unit = subscriptions[key]['unit']

                # use val to adjust
                print(f"Received {subscriptions[key]['value']} at time {current_time}: {val} {val_unit}.")

                paux0_new = np.array(val)  # go to add pub ACE
                ss.TurbineGov.set(src='paux0', idx=tg_idx, attr='v', value=paux0_new)

        if subscriptions[key]['value']=='AGC_signal_A':
            if current_time % subscriptions[key]['sub_interval']<=1e-6:
                val = h.helicsInputGetVector(sub)
                val_unit = subscriptions[key]['unit']
                if current_time == 0:
                    val = PVD_AGC_response
                    val_unit = subscriptions[key]['unit']

                # use val to adjust
                print(f"Received {subscriptions[key]['value']} at time {current_time}: {val} {val_unit}.")

                PVD_AGC_response = np.array(val)  # go to add pub ACE
                ss.PVD1.set(src='Pext0', idx=PVD_AGC_idx, attr='v', value=PVD_AGC_response)


    # start the dynamic simulation
    #print(f'current_time + simulation_step_time = {current_time+simulation_step_time}')
    ss.TDS.config.tf = current_time + simulation_step_time
    ss.TDS.run()
    # print(f"Bus_voltages = {ss.Bus.v.v}")

    ## get the PUBLICATION OUT
    for key, pub in PUBLICATIONS.items():
        # get voltage and angle and publish
        if publications[key]['value']=='Voltage':
            bus_name = publications[key]['element_name']
            element_type = publications[key]['element_type']

            val1 = ss.Bus.v.v[int(bus_name)-1]
            val2 = ss.Bus.a.v[int(bus_name)-1]
            # decide when to publish based on pub_interval
            if current_time % publications[key]['pub_interval']<=1e-6:
                print("Sent voltage mag at time {}: {} pu from {} {}".format(current_time, val1, element_type, bus_name))
                print("Sent voltage ang at time {}: {} rad from {} {}".format(current_time, val2, element_type, bus_name))
                h.helicsPublicationPublishComplex(pub, val1, val2)
        # get frequency and publish
        if publications[key]['value']=='Frequency':
            element_unit = publications[key]['unit']
            element_name = publications[key]['element_name']
            frequency = ss.dae.ts.y[-1, ss.ACEc.f.a][0]*60
            if current_time % publications[key]['pub_interval']<=1e-6:
                print(f"Sent frequency at time {current_time}: {frequency} {element_unit} from {element_name}.")
                h.helicsPublicationPublishDouble(pub, frequency)
        # get ACE and publish
        if publications[key]['value']=='ACE':
            element_unit = publications[key]['unit']
            element_name = publications[key]['element_name']
            ACE = ss.ACEc.ace.v[0]
            print(f"publications[key]['pub_interval']={publications[key]['pub_interval']}")
            print(f"current_time % publications[key]['pub_interval']={current_time % publications[key]['pub_interval']}")
            if current_time % publications[key]['pub_interval']<=1e-6:
                print(f"Sent ACE at time {current_time}: {ACE} {element_unit} from {element_name}.")
                h.helicsPublicationPublishDouble(pub, ACE)

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
# path_to_results = "simulation_results"
# np.savetxt(path_to_results + "\\voltage_all_fault.csv", voltage_all, delimiter=",")
# np.savetxt(path_to_results + "\\voltage_PQ_3_fault.csv", voltage_PQ_3, delimiter=",")
# np.savetxt(path_to_results + "\\dae_time_fault.csv", dae_time, delimiter=",")
# np.savetxt(path_to_results + "\\dae_frequency_fault.csv", dae_frequency, delimiter=",")
# np.savetxt(path_to_results + "\\dae_ACE_fault.csv", dae_ACE, delimiter=",")

# np.savetxt(path_to_results + "\\voltage_all.csv", voltage_all, delimiter=",")
# np.savetxt(path_to_results + "\\voltage_PQ_3.csv", voltage_PQ_3, delimiter=",")
# np.savetxt(path_to_results + "\\dae_time.csv", dae_time, delimiter=",")
# np.savetxt(path_to_results + "\\dae_frequency.csv", dae_frequency, delimiter=",")
# np.savetxt(path_to_results + "\\dae_ACE.csv", dae_ACE, delimiter=",")

h.helicsFederateFinalize(fed)
print(f"{federate_name}: Federate finalized",flush=True)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Broker disconnected")

