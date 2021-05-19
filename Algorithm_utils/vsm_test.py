"""
this file includes get vsm function
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

cwd = os.getcwd()
print(f"python_dir={os.getcwd()}")
feeder_name = 'J1'
distribution_folder = r'C:\Users\wwang2\Documents\OE\CPDS_setup\Network_models\Distribution'
dir_to_feeder_dss = os.path.join(distribution_folder, feeder_name)

# run snapshot and get v and p at current step, and save pickle/npz file

run_command(f'compile {dir_to_feeder_dss}/Master.dss')

if dss.Text.Result() == '':
    print('------ Success for the base run -----')
else:
    print('------ Opendss failed ----')
    print(f'Error is "{dss.Text.Result()}"!')

# now get nominal value and save npz

loadname_all=[]
loadkw_all=[]
loadkvar_all=[]

dss.Loads.First()
for i in range(dss.Loads.Count()):
    loadname = dss.Loads.Name()
    loadkw = dss.Loads.kW()
    loadkvar = dss.Loads.kvar()
    loadname_all.append(loadname)
    loadkw_all.append(loadkw)
    loadkvar_all.append(loadkvar)
    dss.Loads.Next()

loadkw_dict = dict(zip(loadname_all, loadkw_all))
loadkvar_dict = dict(zip(loadname_all, loadkvar_all))
allnodenames = dss.Circuit.AllNodeNames()
allnodenames = np.array(allnodenames)
allbusmagpu = np.array(dss.Circuit.AllBusMagPu())
# notes for getting power flow results for individual element
# dss.Circuit.SetActiveElement('Load.S830b')
# dss.CktElement.Powers()
#
# save voltage base case values as npz
# get back to cwd, since opendss messed up the directory
os.chdir(cwd)
np.savez('temp_v'+'_'+feeder_name+'.npz',allbusmagpu)

# now perturb starts
delta_p = 5 # kw

# define DER node index
index_DERs = np.array([86,87]) # the value in the list are corresponding to
num_DERs = index_DERs.shape[0]
num_nodes = len(allnodenames)

vsm = np.zeros([num_nodes, num_DERs])
allbusmagpu_base = np.load('temp_v'+'_'+feeder_name+'.npz')['arr_0']
print(f'Base min voltage is {np.min(allbusmagpu_base)}')

i=0
for ind in index_DERs:
    nodename = allnodenames[ind]
    #buskv = float(run_command(f"? bus.{nodename.split('.')[0]}.kv"))
    dss.Circuit.SetActiveBus(nodename)
    buskv = dss.Bus.kVBase()
    print(f'buskv={buskv} at node {nodename}') #note that these are all 1 phases
    if i==0:
        run_command(f'New Load.P_perturb bus1={nodename} Phases=1 Conn=Wye Model=1 kv={buskv} kw={delta_p} kvar=0')
    else:
        run_command(f"Edit Load.P_perturb bus1={nodename}")
    dss.Solution.ControlMode(-1) # set control mode off
    #dss.Solution.SolveNoControl()
    dss.Solution.Solve()
    # not get the voltage
    allbusmagpu = np.array(dss.Circuit.AllBusMagPu())
    # get the column of the sensitivity matrix for column i
    delta_v = allbusmagpu - allbusmagpu_base
    column_i = delta_v/delta_p
    vsm[:, i] = column_i
    i=i+1
print('compose vsm is done, high five!')

# now validation of voltage change

# change of p vector
delta_p_vector = np.zeros([num_DERs,1])
delta_p_vector[-1] = 100
run_command(f"Edit Load.P_perturb kw=100")
dss.Solution.SolveNoControl()
allbusmagpu_opendss = np.array(dss.Circuit.AllBusMagPu())
delta_v_vector = vsm @ delta_p_vector
allbusmagpu_vsm = delta_v_vector.flatten() + allbusmagpu_base

# compare two results
err = (allbusmagpu_vsm-allbusmagpu_opendss)/allbusmagpu_opendss*100


print('Hope the error is small')

# contruct dataframe for ploting
data = np.vstack((allbusmagpu_vsm, allbusmagpu_opendss,err)).transpose()
df = pd.DataFrame(data, columns = ['vsm','opendss','err_percent'])

# visulize results
fig, ax = plt.subplots()
sns.heatmap(vsm, ax=ax)
#plt.show()
fig, (ax1,ax2) = plt.subplots(nrows=1,ncols=2,figsize=(10,4))
df[['vsm','opendss']].plot(ax=ax1)
ax1.set_title('comparison of vsm and opendss results')
df.err_percent.plot(ax=ax2)
ax2.set_title('Error in percent')
#plt.show()
# end of script


### start optimizing the DER output
from pulp import *

opt_model = LpProblem("get_pmax_for_DER", LpMaximize)
#DER_cap = 100
DER_cap = np.ones(num_DERs)*100

# prepare data structure
set_x = range(0, num_DERs)
set_v = range(0, num_nodes)
low = {i: 0 for i in set_x}
#DER_index = 87
up = {i: DER_cap[i] for i in set_x}
#up[tuple(index_DERs)] = DER_cap

v_l_ANSI = 0.90
v_u_ANSI = 1.05

v_l = {i: v_l_ANSI - allbusmagpu_base[i] for i in set_v}
v_u = {i: v_u_ANSI - allbusmagpu_base[i] for i in set_v}

# define x decision varibles: cat = LpContinuous, LpInteger
x_vars = {i: LpVariable(cat = LpContinuous, lowBound=low[i], upBound=up[i], name="x_{}".format(i)) \
          for i in set_x}
# define <= constraints
constraints = {i: opt_model.addConstraint(LpConstraint(\
    e=lpSum(vsm[i, j]*x_vars[j] for j in set_x), \
    sense=LpConstraintLE, \
    rhs = v_u[i],\
    name="constraint_v_u{}".format(i)))\
    for i in set_v}
# define >= constraints
constraints = {i: opt_model.addConstraint(LpConstraint(\
    e=lpSum(vsm[i, j]*x_vars[j] for j in set_x), \
    sense=LpConstraintGE, \
    rhs = v_l[i],\
    name="constraint_v_l{}".format(i)))\
    for i in set_v}
# define objective
objective = lpSum(x_vars[i] for i in set_x)
#opt_model.sense = LpMaximize
opt_model.setObjective(objective)

# solving with CBC
opt_model.solve()
print("=====> Status:", LpStatus[opt_model.status])
if opt_model.status!=1:
    raise NameError('***** Optimization not solved! *****')

opt_df = pd.DataFrame.from_dict(x_vars, orient="index", columns = ["variable_object"])
opt_df["solution_value"] = opt_df["variable_object"].apply(lambda item: item.varValue)

obj_value = value(opt_model.objective)
print("The total P max of DER is {}".format(round(obj_value,2)))

print("End of script")
# simple test
x_test = np.zeros(num_DERs)
x_test = np.array(opt_df['solution_value'])
v_test = allbusmagpu_base + vsm@x_test
np.min(v_test)

print("End of script")
fig, ax3 = plt.subplots()
xx = np.arange(0,num_nodes)
ax3.plot(xx,allbusmagpu_base)
