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

start_time = time.time()

##################### First define a broker for total cosim ###########################
path_to_TransmissionSim = os.getcwd()
path_to_results = os.path.join(os.getcwd(), "..", "Results_figures")

helicsversion = h.helicsGetVersion()
print("Helics version = {}".format(helicsversion))
# start a broker inside the file
brokerinitstring = "-f 6 --name=mainbroker" # 3 is the number of federates connecting

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
    ACE_interval = data["ACE_interval"]
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
fed = h.helicsCreateCombinationFederate(f"{federate_name}", fedinfo)
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
#ss.TDS.config.tf = 0.01

# start the 0.1 second dynamic simulation
#ss.TDS.run()
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
DER_Pmax_34Bus_np = None
DER_Pmax_8500Node_np = None

# record the initial system load
pq_p = ss.PQ.get(src='Ppf', idx=pq_shed_idx, attr='v')
# record DER output: TODO
#ss.dae.ts.get_data([ss.PVD1.Ipout_y],a=[1,])*ss.dae.ts.get_data([ss.PVD1.v],a=[1,])*100
pvd1_current = ss.PVD1.Ipout_y.v
pvd1_voltage = ss.PVD1.v.v
pvd1_power = pvd1_current*pvd1_voltage # in 100 MW
DER_caps = np.ones(20)*0.009
# pq_p = array([0.217, 0.5  , 0.478, 0.076, 0.15 , 0.295, 0.09 , 0.035, 0.061,
#        0.135, 0.2  ]
# Sbase = 100 MW
# dae: differential–algebraic equation
# get the load time series randomly choose
consistent_random_object = np.random.RandomState(123)
load_timeseries = consistent_random_object.normal(1, 0.02, int(total_time))
#Load_timeseries_df = pd.DataFrame(Load_timeseries)
# register the publication
for k, v in publications.items():
    pub = h.helicsFederateRegisterGlobalTypePublication(fed, v['topic'], v['type'], "") # register to helics
    PUBLICATIONS[k] = pub # store the HELICS object

for k, v in subscriptions.items():
    sub = h.helicsFederateRegisterSubscription(fed, v['topic'], "")
    SUBSCRIPTIONS[k] = sub  # store the HELICS object

epid1 = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep1", "")
epid2 = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep2", "")
epid3 = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep3", "") #
epid4 = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep4", "") # receive DER pmax from 34Bus
epid5 = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep5", "") # receive DER pmax from 8500Node


# filter_trans_id = h.helicsFederateRegisterFilter(fed, h.HELICS_FILTER_TYPE_DELAY, "filter1")
# h.helicsFilterAddDestinationTarget(filter_trans_id, federate_name+"_ep")
# h.helicsFilterSet(filter_trans_id, "delay", 0.1)

############### Entering Execution Mode ########################
h.helicsFederateEnterExecutingMode(fed)
print(f"{federate_name}: Entering execution mode", flush=True)

print(f"===========Start simulation==================")
mppt=1
current_time = 0
for request_time in np.arange(0, total_time, simulation_step_time):
    while current_time < request_time:
        current_time = h.helicsFederateRequestTime(fed, request_time)
    print("=============================")
    print(f"request_time={request_time}")
    print(f"current_time={current_time}")
    # set power for all loads
    pq_p_new = pq_p * load_timeseries[int(current_time)]
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
        #print(f"type(message)={type(message)}")
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

    while h.helicsEndpointHasMessage(epid4):
        m = h.helicsEndpointGetMessage(epid4)
        message = json.loads(m.data)
        DER_Pmax_34Bus = message
        print(f"Received DER_Pmax_34Bus = {DER_Pmax_34Bus} from Aggregator_DER_34Bus at time {current_time}.")
        DER_Pmax_34Bus_np = DER_Pmax_34Bus

    while h.helicsEndpointHasMessage(epid5):
        m = h.helicsEndpointGetMessage(epid5)
        message = json.loads(m.data)
        DER_Pmax_8500Node = message
        print(f"Received DER_Pmax_8500Node = {DER_Pmax_8500Node} from Aggregator_DER_8500Node at time {current_time}.")
        DER_Pmax_8500Node_np = DER_Pmax_8500Node

    ss.TurbineGov.set(src='paux0', idx=tg_idx, attr='v', value=paux0_new)
    PVD_AGC_response = np.concatenate([PVD_AGC_response1, PVD_AGC_response2])
    if DER_Pmax_34Bus_np is not None and DER_Pmax_8500Node_np is not None:
        PVD_vsm_max = np.concatenate([DER_Pmax_34Bus_np, DER_Pmax_8500Node_np])
        PVD_mppt_new = np.minimum(DER_caps*mppt, PVD_vsm_max)
        print(f"PVD_mppt_new={PVD_mppt_new}")
        ss.PVD1.set(src='pmx', idx=PVD_AGC_idx, attr='v', value=PVD_mppt_new)
    # the AGC response should stay below the Pmax: should set the andes varibles pmax for PVD1
    print(f"PVD_AGC_response={PVD_AGC_response}")

    ss.PVD1.set(src='Pext0', idx=PVD_AGC_idx, attr='v', value=PVD_AGC_response)
    # start the dynamic simulation
    ss.TDS.config.tf = current_time + simulation_step_time
    ss.TDS.run()
    # print(f"Bus_voltages = {ss.Bus.v.v}")
    ACE = ss.ACEc.ace.v[0]
    # get DER output
    pvd1_current = ss.PVD1.Ipout_y.v
    pvd1_voltage = ss.PVD1.v.v
    pvd1_power = pvd1_current * pvd1_voltage # unit is 100 MW
    pvd1_power_34Bus = pvd1_power[:10]
    pvd1_power_8500Node = pvd1_power[10:]
    # send power to the aggregator and feeders
    h.helicsEndpointSendBytesTo(epid4, json.dumps(pvd1_power_34Bus.tolist()), "Aggregator_DER_34Bus_ep3")
    print(f'Sending to Aggregator_DER_34Bus_ep at time {current_time}: pvd1_power {pvd1_power_34Bus} 100 MW.')

    h.helicsEndpointSendBytesTo(epid5, json.dumps(pvd1_power_8500Node.tolist()), "Aggregator_DER_8500Node_ep3")
    print(f'Sending to Aggregator_DER_8500Node_ep at time {current_time}: pvd1_power {pvd1_power_8500Node} 100 MW.')



    # every 0.5 s, set ACE signal through two endpoint
    #if current_time % ACE_interval < 1e-4: # reciving end will control this
    # send messages to Thermal controller
    h.helicsEndpointSendBytesTo(epid1, json.dumps(ACE), "Controller_Thermal_ep")
    print(f'Sending to Controller_Thermal_ep at time {current_time}: ACE {ACE} 100 MW.')
    # send messages to DER aggregator
    h.helicsEndpointSendBytesTo(epid1, json.dumps(ACE), "Aggregator_DER_34Bus_ep1")
    print(f'Sending to Aggregator_DER_34Bus_ep at time {current_time}: ACE {ACE} 100 MW.')
    # send message to another DER aggregator
    h.helicsEndpointSendBytesTo(epid1, json.dumps(ACE), "Aggregator_DER_8500Node_ep1")
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

fig, (ax1, ax2, ax3, ax4) = plt.subplots(nrows=4, ncols=1, figsize=(11, 9))
ax1.plot(ss.dae.ts.t, ss.dae.ts.get_data([ss.ACEc.f])*60)
ax1.set_xlabel('Time (s)')
ax1.set_ylabel('Frequency (Hz)')

ax2.plot(ss.dae.ts.t, ss.dae.ts.get_data([ss.ACEc.ace])*100)
ax2.set_xlabel('Time (s)')
ax2.set_ylabel('ACE (MW)')

ax3.plot(ss.dae.ts.t, ss.dae.ts.get_data([ss.Bus.v],a=[0,3,8,]))
ax3.set_xlabel('Time (s)')
ax3.set_ylabel('Voltage (pu)')

ax4.plot(ss.dae.ts.t, ss.dae.ts.get_data([ss.PVD1.Pext]*100,a=[0,]))
ax4.set_xlabel('Time (s)')
ax4.set_ylabel('PVD1 AGC signal (MW)')
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
end_time = time.time()
time_passed = round(end_time-start_time,2) # in s
time_passed_s = time_passed % 60
time_passed_m = time_passed // 60
print(f"**********************************************")
print(f"Time passed {time_passed_m} min {time_passed_s} s.")
print(f"**********************************************")

h.helicsFederateFinalize(fed)
print(f"{federate_name}: Federate finalized", flush=True)

h.helicsFederateFree(fed)
h.helicsCloseLibrary()
print("Broker disconnected")

