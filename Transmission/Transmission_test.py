# -*- coding: utf-8 -*-
"""
Transmission simulator using Andes
"""
from datetime import datetime
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
path_to_results = os.path.join(os.getcwd(), "..", "Results_figures")



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
    ACE_interval = data["ACE_interval"]
print("reading json okay!")
PUBLICATIONS = {}
SUBSCRIPTIONS = {}



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
ss.TDS.config.tf = 10

# start the 0.1 second dynamic simulation
ss.TDS.run()
ss.dae.ts.y
shed_buses = ss.PQ.bus.v
pq_shed_idx = ss.PQ.find_idx(keys='bus', values=shed_buses)

# define turbine gov AGC settings: find index and set value
tg_idx = list(ss.TurbineGov._idx2model.keys())
paux0_new = np.zeros(len(tg_idx))# - ss.ACEc.ace.v*1/len(tg_idx)

ss.TurbineGov.set(src='paux0',idx=tg_idx, attr='v', value=paux0_new)

PVD_names = ss.PVD1.idx.v
PVD_AGC_idx = ss.PVD1.find_idx(keys='idx', values=PVD_names)

PVD_AGC_response = ss.PVD1.get(src='Pext', idx=PVD_AGC_idx, attr='v')
PVD_AGC_response = np.zeros(len(PVD_AGC_idx))
PVD_AGC_response1 = np.zeros(int(len(PVD_AGC_idx)/2))
PVD_AGC_response2 = np.zeros(int(len(PVD_AGC_idx)/2))
# record the initial system load
pq_p = ss.PQ.get(src='Ppf', idx=pq_shed_idx, attr='v')
# record DER output
#ss.dae.ts.get_data([ss.PVD1.Ipout_y],a=[1,])*ss.dae.ts.get_data([ss.PVD1.v],a=[1,])*100
pvd1_current = ss.PVD1.Ipout_y.v
pvd1_voltage = ss.PVD1.v.v
pvd1_power = pvd1_current*pvd1_voltage*100 # in MW
# pq_p = array([0.217, 0.5  , 0.478, 0.076, 0.15 , 0.295, 0.09 , 0.035, 0.061,
#        0.135, 0.2  ]
# Sbase = 100 MW
# dae: differential–algebraic equation
# get the load time series randomly choose
consistent_random_object = np.random.RandomState(123)
load_timeseries = consistent_random_object.normal(1, 0.0, int(total_time/simulation_step_time))
#Load_timeseries_df = pd.DataFrame(Load_timeseries)

print(f"===========Start simulation==================")

current_time = 0
for current_time in np.arange(0, total_time, simulation_step_time):
    # while current_time < request_time:
    #     current_time = h.helicsFederateRequestTime(fed, request_time)
    print("=============================")
    print(f"current_time={current_time}")
    # set power for all loads
    pq_p_new = pq_p * load_timeseries[int(current_time/simulation_step_time)]
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

    while h.helicsEndpointHasMessage(epid1): # epid1 from thermal control
        m = h.helicsEndpointGetMessage(epid1)
        message = json.loads(m.data)
        paux0_new = message
        print(f"type(message)={type(message)}")
        print(f"Received paux0_new = {paux0_new} from thermal_controller at time {current_time}.")

    while h.helicsEndpointHasMessage(epid2):
        m = h.helicsEndpointGetMessage(epid2)
        message = json.loads(m.data)
        PVD_AGC_response1 = message
        print(f"Received PVD_AGC_response1 = {PVD_AGC_response1} from Aggregator_DER_34Bus at time {current_time}.")

    while h.helicsEndpointHasMessage(epid3):
        m = h.helicsEndpointGetMessage(epid3)
        message = json.loads(m.data)
        PVD_AGC_response2 = message
        print(f"Received PVD_AGC_response2 = {PVD_AGC_response2} from Aggregator_DER_8500Node at time {current_time}.")


    ss.TurbineGov.set(src='paux0', idx=tg_idx, attr='v', value=paux0_new)
    PVD_AGC_response = np.concatenate([PVD_AGC_response1, PVD_AGC_response2])
    ss.PVD1.set(src='Pext0', idx=PVD_AGC_idx, attr='v', value=PVD_AGC_response)
    # start the dynamic simulation
    ss.TDS.config.tf = current_time + simulation_step_time
    ss.TDS.run()
    # print(f"Bus_voltages = {ss.Bus.v.v}")
    ACE = ss.ACEc.ace.v[0]
    # every 0.5 s, set ACE signal through two endpoint
    #if current_time % ACE_interval < 1e-4:
    # send messages to Thermal controller
    h.helicsEndpointSendTo(epid1, "Controller_Thermal_ep", json.dumps(ACE))
    print(f'Sending to Controller_Thermal_ep at time {current_time}: ACE {ACE} 100 MW.')
    # send messages to DER aggregator
    h.helicsEndpointSendTo(epid1, "Aggregator_DER_34Bus_ep", json.dumps(ACE))
    print(f'Sending to Aggregator_DER_34Bus_ep at time {current_time}: ACE {ACE} 100 MW.')
    # send message to another DER aggregator
    h.helicsEndpointSendTo(epid1, "Aggregator_DER_8500Node_ep", json.dumps(ACE))
    print(f'Sending to Aggregator_DER_8500Node_ep at time {current_time}: ACE {ACE} 100 MW.')


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

    # if dynamic simulation can't converge, terminate the simulation
    if ss.exit_code != 0:
        raise ValueError(current_time)

fig, (ax1, ax2, ax3) = plt.subplots(nrows=3, ncols=1, figsize=(8, 6))
ax1.plot(ss.dae.ts.t, ss.dae.ts.get_data([ss.ACEc.f])*60)
ax1.set_xlabel('Time (s)')
ax1.set_ylabel('Frequency (Hz)')

ax2.plot(ss.dae.ts.t, ss.dae.ts.get_data([ss.ACEc.ace])*100)
ax2.set_xlabel('Time (s)')
ax2.set_ylabel('ACE (MW)')

ax3.plot(ss.dae.ts.t, ss.dae.ts.get_data([ss.Bus.v],a=[0,3,8,]))
ax3.set_xlabel('Time (s)')
ax3.set_ylabel('Voltage (pu)')

#plt.show()
now = datetime.now() # record the time
append_time = now.strftime("%m_%d_%Y_%H_%M_%S")
figure_name = "cosim_results_" + append_time + ".png"
fig.savefig(os.path.join(path_to_results, figure_name), dpi=300)

#ss.TDS.load_plotter()
#print(ss.dae.ts.y.shape)
#plot the system frequency
#ss.TDS.plt.plot(ss.ACEc.f, ytimes=60, ylabel='Frequency (Hz)')

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

