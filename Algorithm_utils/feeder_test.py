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
feeder_name = '34Bus'
dir_to_feeder_dss = os.path.join(cwd,'..','Distribution', feeder_name ,'DSSfiles')

# run snapshot and get v and p at current step, and save pickle/npz file

run_command(f'compile {dir_to_feeder_dss}/Master.dss')

if dss.Text.Result() == '':
    print('------ Success for the base run -----')
else:
    print('------ Opendss failed ----')
    print(f'Error is "{dss.Text.Result()}"!')
run_command("BatchEdit Load..* Vminpu=0.9")
run_command("BatchEdit Load..* Yearly=dummy")

run_command("set mode=yearly number=60 stepsize=1s")
print(f"dss.Solution.Mode()={dss.Solution.Mode()}")

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

