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
from pulp import *



def get_vsm(dss, feeder_name, index_DERs, allbusmagpu_base):
    """
    input:
        dss: object
        feeder_name: str
        index_DERs: np.array
        allbusmagpu_base: np.array
    output: vsm
    """
    delta_p = 5  # kw
    allnodenames = dss.Circuit.AllNodeNames()
    num_DERs = index_DERs.shape[0]
    num_nodes = len(allnodenames)
    allloadnames = dss.Loads.AllNames()

    #print(f"In VSM function: allloadnames={allloadnames}")
    vsm = np.zeros([num_nodes, num_DERs])
    #allbusmagpu_base = np.load('temp_v'+'_'+feeder_name+'.npz')['arr_0']
    #print(f'Base min voltage is {np.min(allbusmagpu_base)}')
    #print(f"dss.Circuit.TotalPower() = {dss.Circuit.TotalPower()}")
    i=0
    print(f"index_DERs={index_DERs}")
    for ind in index_DERs:

        nodename = allnodenames[ind]
        #buskv = float(run_command(f"? bus.{nodename.split('.')[0]}.kv"))
        dss.Circuit.SetActiveBus(nodename)
        buskv = dss.Bus.kVBase()
        allloadnames = dss.Loads.AllNames()
        #print(f'buskv={buskv} at node {nodename}') #note that these are all 1 phases
        if 'p_perturb' not in allloadnames:
            run_command(f'New Load.P_perturb bus1={nodename} Phases=1 Conn=Wye Model=1 kv={buskv} kw={delta_p} kvar=0')
        else:
            run_command(f"Edit Load.P_perturb bus1={nodename}")
        dss.Solution.ControlMode(2) # set control mode off
        dss.Solution.Solve()
        #dss.Solution.SolveNoControl()
        # not get the voltage
        allbusmagpu = np.array(dss.Circuit.AllBusMagPu())
        # get the column of the sensitivity matrix for column i
        delta_v = allbusmagpu - allbusmagpu_base
        #print(f"delta_v={delta_v}")

        column_i = delta_v/delta_p
        vsm[:, i] = column_i
        i=i+1
        if ind==index_DERs[-1]:
            run_command("Edit Load.P_perturb kw=0")
            #run_command("Edit Load.P_perturb enabled=False")
            #dss.Solution.ControlMode(1)
    #print('compose vsm is done, high five!')
    return vsm

def get_DER_local_limit(vsm, DER_caps, allbusmagpu_base):
    """:cvar
    input:
        vsm: voltage sensitivity matrix
        DER_caps: DER name plate capacity in kw as a np.array
        allbusmagpu_base: np.array
    maximize sum of DER output
    constrains: local voltage constrain based vsm
    output df contains each DER allowed kw output
    """


    opt_model = LpProblem("get_pmax_for_DER", LpMaximize)

    #DER_cap = np.ones(num_DERs)*100

    # prepare data structure
    num_nodes = vsm.shape[0]
    num_DERs = len(DER_caps)
    set_x = range(0, num_DERs)
    set_v = range(0, num_nodes)
    low = {i: 0 for i in set_x}
    #DER_index = 87
    up = {i: DER_caps[i] for i in set_x}
    #up[tuple(index_DERs)] = DER_caps

    # v_l_ANSI = 0.90
    # v_u_ANSI = 1.08
    v_l_ANSI = np.min(allbusmagpu_base) - 0.01
    v_u_ANSI = np.max(allbusmagpu_base) + 0.01
    v_l = {i: v_l_ANSI - allbusmagpu_base[i] for i in set_v}
    v_u = {i: v_u_ANSI - allbusmagpu_base[i] for i in set_v}

    # define x decision varibles: cat = LpContinuous, LpInteger
    x_vars = {i: LpVariable(cat = LpContinuous, lowBound=low[i], upBound=up[i], name="x_{}".format(i)) \
            for i in set_x}
    # define <= constraints
    constraints = {i: opt_model.addConstraint(LpConstraint(\
        e=lpSum(vsm[i, j]*-x_vars[j] for j in set_x), \
        sense=LpConstraintLE, \
        rhs = v_u[i],\
        name="constraint_v_u{}".format(i)))\
        for i in set_v}
    # define >= constraints
    constraints = {i: opt_model.addConstraint(LpConstraint(\
        e=lpSum(vsm[i, j]*-x_vars[j] for j in set_x), \
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
    #print("The total P max of DER is {}".format(round(obj_value,2)))

    return (opt_df, obj_value)


