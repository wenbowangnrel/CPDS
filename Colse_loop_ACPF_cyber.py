# For SAGA project T&D co-simulation to obtain T&D voltage

#!/usr/bin/env python
# coding: utf-8

# In[1]:
# Generalized operating script for the MIDAS-Scheduling
# Main Script
# Current Progress: Step 3: Encapsulation
# 06/20/2020
# Maintainers: SMU Power Group (J. Wang, S. Yin, Y. Lin)
# Contributors: Z. Li, NREL GEM Group (J. Tan, X. Fang, H. Yuan)

# --------------- Preliminaries Import ----------------
# ---- Libraries
import pandas as pd
import numpy as np
import pyomo.opt as pyo
import pyomo.environ as pe
import matplotlib.pyplot as plt
import xlrd
import time
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
import warnings
import random
import other_services
from collections import OrderedDict, namedtuple
import math
from pyomo.opt import SolverStatus, TerminationCondition
from pyomo.util.infeasible import log_infeasible_constraints

# ---- Operation routines
from Calculate_PTDF import calPTDF
from LMP_Export import ExportLMP
from DA_Figure_Plot import DAFigurePlot
from RTED_Figure_Plot import RTEDFigurePlot
from Preprocess_Input import PreprocessEXCEL
from Preprocess_Timeseries import PreprocessTimeSeries
from Supply_Set_Initialization import SupplySet
#from TypeIdentification import Type_Identify
from RTUC_DAT_Creation import RTUC_create_dat
from RTED_DAT_Creation import RTED_create_dat
from DAUC_DAT_Creation import DAUC_create_dat
from DAED_DAT_Creation import DAED_create_dat
from DAUCModel import UCmdl
from DAEDModel import DAEDmdl
from RTUCModel import RTUCmdl
from RTEDModel import EDmdl
# --------------- End of this Section ----------------


# import andes for AC PF and load the ACPF cases
import andes
andes.main.config_logger()

pfss = andes.load(str(REPO_ROOT / 'Transmission' / 'network_model' / 't3ps.raw'))

switched_shut0= pfss.Shunt.b.v
v1_bus2 = pd.DataFrame()

# # Initial OpenDss run base case power flow
from DSS_Communicator import DSS
from Event_generators import SLG_fault, Switch_off, Load_perturb
import os
import numpy as np
import pandas as pd

# Examples of configuration dictionary for the DSS instance
dict_DSS = {
    'Sbus': 'st_mat',
    'BaseS': 100,
    'feedername': 'P5U/p5uhs2_1247',
    'masterfile': 'Master.dss',
    'TIME': '1:01 PM'
    }

# Examples of configuration dictionary for the SLG_fault event
dict_SLG_fault = {
    'name': 'F1',
    'bus': 'p5udt6490-p5udt747xx',
    'phase': 3
    }

# Examples of configuration dictionary for the Switch_mis event
dict_Switch_mis = {
    'line': 'l(r:p5udt6490-p5udt747)',
    'terminal': 2,
    'phase': 3
    }

# Examples of configuration dictionary for the load perturb event
dict_Load_perturb = {
    'load': 'load_p5ulv58'
}

maindir = str(REPO_ROOT / '.local' / 'Austin')

# Claim the DSS instance and event initialization
Austin = DSS(dict_DSS, maindir)
SLG_fault = SLG_fault(Austin)
Switch_off = Switch_off(Austin)
Load_perturb = Load_perturb(Austin)

# Relevant simulation parameters
duration = 288        # duration of the simulation (in second)
# event_start = 120      # time index when the event occurs (in second)
# event_end = 132       # time index when the event cleans (in second)

# Configure for the steady-state mode simulation
Austin.static_run_config()

# Getting the nodes list
Nodes = Austin.getNodes()

# Getching the base voltage values
Vbase = Austin.getVbase().Vbase.tolist()

# Create an empty numpy array for solving the simulation results
Vpu_ts = np.empty((len(Nodes), duration))
v1_all = []
Feeder_total_power=[]

# In[2]:


# --------------- Temporary Prompt ----------------
# This section serves for all MODIFIABLE system parameters
# and settings. In the GUI design, we need to change this section.

# ---- Solver configuration
opt_uc = pyo.SolverFactory('xpress', is_mip = True)
opt_ed = pyo.SolverFactory('xpress', is_mip = False)
opt_uc.options['threads'] = 8
opt_ed.options['threads'] = 8
# More solver options can be added later.

# ---- Data directory configuration
# Main directory
prefix_dir = str(REPO_ROOT / '.local' / '18_bus')

# Branch directory
rawData_fp = prefix_dir + "/ToGenerateUC&EDInput/"
timeseries_fp = prefix_dir + "/ToGenerateUC&EDInput/Time_Series/"
intermediate_fp = prefix_dir + "/Intermediate_Files/"
DAUC_DAT_fp = intermediate_fp + "/DAUC_dat/"
RTUC_DAT_fp = intermediate_fp + "/RTUC_dat/"
RTED_DAT_fp = intermediate_fp + "/RTED_dat/"
Dynamic_ex_fp = prefix_dir + "/Dynamic_Exchange/"
os.makedirs(os.path.dirname(intermediate_fp), exist_ok=True)
os.makedirs(os.path.dirname(DAUC_DAT_fp), exist_ok=True)
os.makedirs(os.path.dirname(RTUC_DAT_fp), exist_ok=True)
os.makedirs(os.path.dirname(RTED_DAT_fp), exist_ok=True)
os.makedirs(os.path.dirname(Dynamic_ex_fp), exist_ok=True)

# Result saving directory
Result_fp = prefix_dir + "/Results/"
DAUCResult_fp = Result_fp + "/DAUCresult/"
RTUCResult_fp = Result_fp + "/RTUCresult/"
RTEDResult_fp = Result_fp + "/RTEDresult/"
DAfig_savepath = Result_fp + '/DAFigs/'
RTfig_savepath = Result_fp + '/RTFigs/'
os.makedirs(os.path.dirname(Result_fp), exist_ok=True)
os.makedirs(os.path.dirname(DAUCResult_fp), exist_ok=True)
os.makedirs(os.path.dirname(RTUCResult_fp), exist_ok=True)
os.makedirs(os.path.dirname(RTEDResult_fp), exist_ok=True)
os.makedirs(os.path.dirname(DAfig_savepath), exist_ok=True)
os.makedirs(os.path.dirname(RTfig_savepath), exist_ok=True)

# ---- Plotting configuration
# plt.rc('text', usetex = True)
# plt.rc('font', family = 'serif')
# plt.rc('text.latex', preamble = r'\usepackage{xcolor}')

# ---- File name configuration
# If multiple days, it should be changed in the Timeseries.xlsx.
#files = {'MainFile': "Input.xlsx", 'TimeSeries': 'Timeseries.xlsx'}

# --------------- End of this Section ----------------


# In[ ]:





# In[3]:


# --------------- Data Preprocessing ----------------
# This section serves for reading input data and performing 
# data preprocessing.

# ---- Read the main input data

setting_input = pd.read_excel(rawData_fp + 'Input.xlsx', 'Setting')
reserve_input = pd.read_excel(rawData_fp + 'Input.xlsx', 'Reserve')

PreInput = PreprocessEXCEL(rawData_fp, 'Input.xlsx')

bus_input, bus_list                     = PreInput.bus_initialize()
gen_input, gen_list, missing_Gen_type   = PreInput.gen_initialize()
ess_input, ess_list, missing_ESS_type   = PreInput.ess_initialize()
line_input, line_list                   = PreInput.line_initialize()

# ---- Read the timeseries data

last_day_flag = 1         # 1: this is the last day of simulation. Add the first two hours timeseries in the end
                          # 0: this is not the last day. Add the next day's two hours timeseries in the end (Not finished yet)
extend_time   = 2         # [hour] How many hours should we extend to catch up the look-ahead horizon. (Please set 2 for now)

PreTS        = PreprocessTimeSeries(rawData_fp+"Time_Series/", setting_input, reserve_input, bus_list,                                 missing_Gen_type, missing_ESS_type, last_day_flag, extend_time)

if setting_input.loc[0,"Forecast_Method"] == 0:
    Load_TS      = PreTS.load_TS_initialize()
    Supply_TS    = PreTS.supply_TS_initialize()
else:
    Load_TS      = Load_Forecast()
    Supply_TS    = Supply_Forecast()
    
Reserve_TS   = PreTS.reserve_TS_initialize()

# ---- supply set initialization

Supply_List = SupplySet(gen_list, ess_list).set_initialize()

# Side Notes:
# G1 (Gen-1): Dispatchable (thermal) units.        Scheduling w.r.t. Pmin/Pmax
# G2 (Gen-2): Dispatchable (renewable) units.      Scheduling w.r.t. TimeSeries
# G3 (Gen-3): Non-dispatchable (renewable) units.  Rigorously following TimeSeries (Cannot provide ancillary services)
# E1 (ESS-1): Non-dispatchable ESS.                Rigorously following TimeSeries (Cannot provide ancillary services)
# E2 (ESS-2): Pumped-hydro ESS.                    Ancillary service providable inflexibly
# E3 (ESS-3): Battery ESS.                         Ancillary service providable flexibly

# Code Protection
# if len(setting_input) != 1:
#     raise Exception("The \"" + "Setting" + "\" tab in the Input.xlsx should only have one row. Please double-check.")

# if len(reserve_input) != 1:
#     raise Exception("The \"" + "Reserve" + "\" tab in the Input.xlsx should only have one row. Please double-check.")
# LETS FINISH THIS LATER

# Simulation setting
DAUC_res = int(setting_input.loc[0,'DAUC_res'])
RTUC_res = int(setting_input.loc[0,'RTUC_res'])
RTED_res = int(setting_input.loc[0,'RTED_res'])
DAUC_hor = int(setting_input.loc[0,'DAUC_hor'])
RTUC_hor = int(setting_input.loc[0,'RTUC_hor'])
RTED_hor = int(setting_input.loc[0,'RTED_hor'])
RTUC_loh = int(setting_input.loc[0,'RTUC_LookAhead'])
Simulation_len = int(setting_input.loc[0,'Simulation_Length'])
inter_num = int(60 / RTED_res)

hour_list = list(range(1, Simulation_len+extend_time+1))

# ---- Process PTDF Generation
Slack_bus = str(setting_input['SlackBus'][0])
PTDF_calculation = calPTDF(line_input, bus_input, Slack_bus)
PTDF_input = PTDF_calculation.createPTDF()

# ---- Input Processing

close_loop_flag = 0         # 1: the simulation works in closed-loop. Should have an input from dynamic simulation.
ess_interpolate_method = 0  # 1: All RTED ESS dispatch in the 12 intervals is exactly the DAUC dispatch
                            # 0: We build the RTED ESS dispatch trajectory according to the DAUC dispatch
    


# EDins = EDmdl.create_instance(RTED_DAT_fp + str(53) + '.dat')
# results = opt.solve(EDins, tee=True, keepfiles=True)

# In[4]:


# --------------- DAUC Part ----------------
# ----- Create DAT file
DAUCTime = 0
DAUCTime1 = time.process_time()

UCdat = DAUC_create_dat(DAUC_DAT_fp, setting_input, DAUC_res, DAUC_hor, bus_input,                         gen_input, ess_input, line_input, PTDF_input, reserve_input,                         Supply_List, hour_list, Load_TS["DAUC_Load"], Load_TS["DAUC_Load_raw"],                         Supply_TS["DAUC_G23"], Supply_TS["DAUC_E1"], Reserve_TS) 
   
# ----- Create instance and solve
UCins = UCmdl.create_instance(DAUC_DAT_fp + "DAUC.dat")
results = opt_uc.solve(UCins, tee=True, keepfiles=True)

DAUCTime2 = time.process_time()
DAUCTime += DAUCTime2 - DAUCTime1

# ----- Post-solution processing

Inflex_UCPmax = pd.DataFrame(.0, columns = ["Pmax"],                      index = pd.MultiIndex.from_product([Supply_List["INFLEX_SET"],range(1,Simulation_len+extend_time+1)]))
Inflex_UCPmax.index.names = ['genname','hour']
Inflex_UCPmin = pd.DataFrame(.0, columns = ["Pmin"],                      index = pd.MultiIndex.from_product([Supply_List["INFLEX_SET"],range(1,Simulation_len+extend_time+1)]))  
Inflex_UCPmin.index.names = ['genname','hour']
Inflex_EDPmax = pd.DataFrame(.0, columns = ["Pmax"],                      index = pd.MultiIndex.from_product([Supply_List["INFLEX_SET"],range(1,(Simulation_len+extend_time)*inter_num+1)]))
Inflex_EDPmax.index.names = ['genname','inter']
Inflex_EDPmin = pd.DataFrame(.0, columns = ["Pmin"],                      index = pd.MultiIndex.from_product([Supply_List["INFLEX_SET"],range(1,(Simulation_len+extend_time)*inter_num+1)]))
Inflex_EDPmin.index.names = ['genname','inter']

DA_UCresults = pd.DataFrame(0, columns = ["I"],                      index = pd.MultiIndex.from_product([Supply_List["DPGEN_SET"],range(1,Simulation_len+extend_time+1)]))
DA_UCresults.index.names = ['genname','hour']

DA_ESSBinresults = pd.DataFrame(0, columns = ["Ch","Dis"],                    index = pd.MultiIndex.from_product([Supply_List["DPESS_SET"],range(1,Simulation_len+extend_time+1)]))
DA_ESSBinresults.index.names = ['essname','hour']      

for hi in UCins.HOUR_SET:
    for gi in UCins.GEN1_SET:
        DA_UCresults.loc[(gi,hi),'I'] = UCins.gen_onoff[gi,hi].value  
    for ei in UCins.DPESS_SET:
        DA_ESSBinresults.loc[(ei,hi),"Ch"] = UCins.ess_ch_indic[ei,hi].value
        DA_ESSBinresults.loc[(ei,hi),"Dis"] = UCins.ess_dis_indic[ei,hi].value

DAUC_PgenResult = pd.DataFrame(columns = Supply_List["GEN_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_RegionDispatch = pd.DataFrame(.0, columns = [str(x) for x in set(list(bus_input["Region"]))],                                   index = range(1,Simulation_len+extend_time+1), dtype = "float64")

DAUC_PVCurtail = pd.DataFrame(columns = Supply_List["GEN2_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_LineFlow = pd.DataFrame(np.nan, columns = line_list, index = range(1,Simulation_len+extend_time+1))
DAUC_pfrup_Result = pd.DataFrame(columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_pfrdn_Result = pd.DataFrame(columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_agcup_Result = pd.DataFrame(columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_agcdn_Result = pd.DataFrame(columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_socResult = pd.DataFrame(columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_ess_ch = pd.DataFrame(columns = Supply_List["ESS_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_ess_dis = pd.DataFrame(columns = Supply_List["ESS_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_ess_pfr_up = pd.DataFrame(columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_ess_pfr_dn = pd.DataFrame(columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_ess_agc_up = pd.DataFrame(columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+extend_time+1))
DAUC_ess_agc_dn = pd.DataFrame(columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+extend_time+1))

# ----- Save PGen, PFR, AGC Results

for h in UCins.HOUR_SET:
    for i in Supply_List["DPGEN_SET"]:
        DAUC_PgenResult.loc[h,i] = UCins.gen_power[i,h].value
    for i in Supply_List["GEN3_SET"]:
        DAUC_PgenResult.loc[h,i] = Supply_TS["DAUC_G23"].loc[h,i]
    for j in DAUC_RegionDispatch.columns:
        for i in Supply_List["DPGEN_SET"]:
            if str(bus_input.loc[str(gen_input.loc[i,'busname']), 'Region']) == str(j):
                DAUC_RegionDispatch.loc[h,j] += UCins.gen_power[i,h].value
        for i in Supply_List["GEN3_SET"]:
            if str(bus_input.loc[str(gen_input.loc[i,'busname']), 'Region']) == str(j):
                DAUC_RegionDispatch.loc[h,j] += Supply_TS["DAUC_G23"].loc[h,i]

        for i in Supply_List["DPESS_SET"]:
            if str(bus_input.loc[str(ess_input.loc[i,'busname']), 'Region']) == str(j):
                DAUC_RegionDispatch.loc[h,j] += UCins.ess_pow[i,h].value
        for i in Supply_List["ESS1_SET"]:
            if str(bus_input.loc[str(ess_input.loc[i,'busname']), 'Region']) == str(j):
                DAUC_RegionDispatch.loc[h,j] += Supply_TS["DAUC_E1"].loc[h,i]
            
    for i in UCins.DPESS_SET:
        DAUC_ess_dis.loc[h,i] = UCins.ess_dis[i,h].value 
        DAUC_ess_ch.loc[h,i] = UCins.ess_ch[i,h].value 
    for i in Supply_List["ESS1_SET"]:
        DAUC_ess_dis.loc[h,i] = Supply_TS["DAUC_E1"].loc[h,i] if Supply_TS["DAUC_E1"].loc[h,i] > 0 else 0
        DAUC_ess_ch.loc[h,i] = -Supply_TS["DAUC_E1"].loc[h,i] if Supply_TS["DAUC_E1"].loc[h,i] <= 0 else 0
    for i in UCins.GEN2_SET:
        DAUC_PVCurtail.loc[h,i] = Supply_TS["DAUC_G23"].loc[h,i] - UCins.gen_power[i,h].value
    for i in UCins.LINE_SET:
        if abs(line_input.loc[i,"Active"] - 1) <= 1e-4:
            DAUC_LineFlow.loc[h,i] = sum(UCins.Ln_PTDF[i, UCins.Gen_Bus[gi]] * UCins.gen_power[gi,h].value for gi in UCins.DPGEN_SET) +                                    sum(UCins.Ln_PTDF[i,UCins.ESS_Bus[ei]]* UCins.ess_pow[ei,h].value                                     for ei in UCins.DPESS_SET) - sum(UCins.Ln_PTDF[i,ldi] * (UCins.Load_Bus[ldi,h].value                                     - UCins.lol[ldi,h].value + UCins.sol[ldi,h].value) for ldi in UCins.LOAD_BUS_SET)
    for i in UCins.DPGEN_SET:        
        DAUC_pfrup_Result.loc[h,i] = UCins.gen_pfr_pos[i,h].value
        DAUC_pfrdn_Result.loc[h,i] = UCins.gen_pfr_neg[i,h].value
        DAUC_agcup_Result.loc[h,i] = UCins.gen_agc_pos[i,h].value
        DAUC_agcdn_Result.loc[h,i] = UCins.gen_agc_neg[i,h].value
    for ei in UCins.DPESS_SET:
        DAUC_socResult.loc[h,ei] = UCins.soc[ei,h].value
        DAUC_ess_pfr_up.loc[h,ei] = UCins.ess_pfr_pos[ei,h].value
        DAUC_ess_pfr_dn.loc[h,ei] = UCins.ess_pfr_neg[ei,h].value
        DAUC_ess_agc_up.loc[h,ei] = UCins.ess_agc_pos[ei,h].value
        DAUC_ess_agc_dn.loc[h,ei] = UCins.ess_agc_neg[ei,h].value

# ----- Build Trajectories
for gi in Supply_List["INFLEX_SET"]:
    for hi in UCins.HOUR_SET:
        Inflex_UCPmax.loc[(gi,hi),'Pmax'] = UCins.gen_onoff[gi,hi].value * gen_input.loc[gi,'Pmax']
        Inflex_UCPmin.loc[(gi,hi),'Pmin'] = UCins.gen_onoff[gi,hi].value * gen_input.loc[gi,'Pmin']
for gi in Supply_List["INFLEX_SET"]:
    for hi in UCins.HOUR_SET:
        for ii in range(1,inter_num+1):
            Inflex_EDPmax.loc[(gi,(inter_num*(hi-1)+ii)),'Pmax'] = UCins.gen_onoff[gi,hi].value * gen_input.loc[gi,'Pmax']
            Inflex_EDPmin.loc[(gi,(inter_num*(hi-1)+ii)),'Pmin'] = UCins.gen_onoff[gi,hi].value * gen_input.loc[gi,'Pmin']  
            
for gi in Supply_List["INFLEX_SET"]:
    for hi in UCins.HOUR_SET: 
        if UCins.gen_startup[gi,hi].value == 1:
            houreq = gen_input.loc[gi,'SUTime']/60
            for n in range(1,inter_num*(RTUC_hor-RTUC_loh)):
                if houreq - n >= 0:
                    Inflex_UCPmax.loc[(gi,hi-n),'Pmax'] = (houreq - n) / houreq * gen_input.loc[gi,'Pmax']
                    Inflex_UCPmin.loc[(gi,hi-n),'Pmin'] = (houreq - n) / houreq * gen_input.loc[gi,'Pmin']
                else:
                    continue
  
    for hi in UCins.HOUR_SET:                        
        if UCins.gen_shutdow[gi,hi].value == 1:
            houreq = gen_input.loc[gi,'SDTime']/60
            for n in range(1,inter_num*(RTUC_hor-RTUC_loh)):
                if houreq - n >= 0:
                    Inflex_UCPmax.loc[(gi,hi-n),'Pmax'] = gen_input.loc[gi,'Pmax'] * n / houreq
                    Inflex_UCPmin.loc[(gi,hi-n),'Pmin'] = gen_input.loc[gi,'Pmin'] * n / houreq
                else:
                    continue
            
for gi in Supply_List["INFLEX_SET"]:
    for hi in UCins.HOUR_SET:
        if UCins.gen_startup[gi,hi].value == 1:
            # A Try Except Error Handle Should be Here!
            intereq = gen_input.loc[gi,'SUTime']/5
            for n in range(1,Simulation_len*inter_num+1):
                if intereq - n >= 0:
                    Inflex_EDPmax.loc[(gi,inter_num*hi-n),'Pmax'] = (intereq - n) / intereq * gen_input.loc[gi,'Pmax']
                    Inflex_EDPmin.loc[(gi,inter_num*hi-n),'Pmin'] = (intereq - n) / intereq * gen_input.loc[gi,'Pmin']
                else:
                    continue
                
        if UCins.gen_shutdow[gi,hi].value == 1:
            # A Try Except Error Handle Should be Here!
            intereq = gen_input.loc[gi,'SDTime']/5
            for n in range(1,Simulation_len*inter_num+1):
                if intereq - n >= 0:
                    Inflex_EDPmax.loc[(gi,inter_num*hi-n),'Pmax'] = gen_input.loc[gi,'Pmax'] * n / intereq
                    Inflex_EDPmin.loc[(gi,inter_num*hi-n),'Pmin'] = gen_input.loc[gi,'Pmin'] * n / intereq   
                else:
                    continue



# In[5]:


UCins


# In[6]:


# ---- DAUC Penalty Check (PC)
lol_sol_indic = 0
Ramp_slack_indic = 0
Cap_Slack_indic = 0
PC_answer = {1: "Yes", 0: "No"}
for hi in UCins.HOUR_SET:
    for ldi in UCins.LOAD_BUS_SET:
        if abs(UCins.lol[ldi, hi].value+UCins.sol[ldi, hi].value) >= 1e-4:
            lol_sol_indic = 1
    #print('lol sum  ', UCins.lol_sum[hi].value)
    #print('sol sum  ', UCins.sol_sum[hi].value)
    for gi in UCins.GEN1_SET:
        #print('ramp up slack  ', UCins.gen_ramp_up_slack[gi,hi].value)
        #print('ramp dn slack  ', UCins.gen_ramp_dn_slack[gi,hi].value)
        if abs(UCins.gen_ramp_up_slack[gi,hi].value+UCins.gen_ramp_dn_slack[gi,hi].value) >= 1e-4:
            Ramp_Slack_indic = 1
        
    for li in UCins.LINE_SET:
        if abs(UCins.Ln_Cap_up_Slack[li,hi].value+UCins.Ln_Cap_dn_Slack[li,hi].value) >= 1e-4:
            Cap_Slack_indic = 1
        #print('Ln_Cap_up_Slack  ', UCins.Ln_Cap_up_Slack[li,hi].value)
        #print('Ln_Cap_dn_Slack  ', UCins.Ln_Cap_dn_Slack[li,hi].value)
        
print('Has any loss of load or surplus of load?   ' + PC_answer[lol_sol_indic] + '\n')
print('Has any ramping slack?   ' + PC_answer[Ramp_slack_indic] + '\n')
print('Has any capacity slack?   ' + PC_answer[Cap_Slack_indic] + '\n')


# In[ ]:





# In[7]:


# --------------- DAED Part ----------------
# ----- Create DAT file
DAEDTime1 = time.process_time()

DAEDdat = DAED_create_dat(DAUC_DAT_fp, DA_UCresults, DA_ESSBinresults, setting_input, DAUC_res, DAUC_hor, bus_input,                         gen_input, ess_input, line_input, PTDF_input, reserve_input,                         Supply_List, hour_list, Load_TS["DAUC_Load"], Load_TS["DAUC_Load_raw"],                         Supply_TS["DAUC_G23"], Supply_TS["DAUC_E1"], Reserve_TS) 
   
# ----- Create instance and solve
DAEDins = DAEDmdl.create_instance(DAUC_DAT_fp + "DAED.dat")
DAEDins.dual = pe.Suffix(direction = pe.Suffix.IMPORT) # To include the duals if any
DAEDTime2 = time.process_time()
DAEDTime = DAEDTime2 - DAEDTime1

DAED_results = opt_ed.solve(DAEDins, tee=True, keepfiles=True)

DA_LMP = ExportLMP(DAEDins, DAEDins.dual, line_input, DAEDins.HOUR_SET, DAEDins.LOAD_BUS_SET, DAEDins.LINE_SET).Calculate_LMP()


# In[8]:


sum_index = ["DAUC elapsed time",
             "Solver termination status",
             "# of constraints",
             "# of variables",
             "# of binary variables",
             "DAUC Total Cost",
             "DA-Geneneration Cost",
             "DA-ESS Cost",
             "DA-Reserve Cost",
             "DA-Penalty Cost"]
sum_value = [DAUCTime, results.Solver.Termination_condition,  
             results.Problem.Number_of_constraints, results.Problem.Number_of_variables,
             results.Problem.Number_of_integer_variables,
             UCins.OBJ(),
             sum([UCins.gen_cost[h].value for h in UCins.HOUR_SET]),
             sum([UCins.ess_cost[h].value for h in UCins.HOUR_SET]),
             sum([UCins.reserve_cost[h].value for h in UCins.HOUR_SET]),
             sum([UCins.penalty_cost[h].value for h in UCins.HOUR_SET])]
DAUC_summary = pd.DataFrame(.0, index = sum_index, columns = ["value"])
for i in range(10):
    DAUC_summary.iloc[i] = sum_value[i]


# In[ ]:





# In[9]:


DAResults = {'Summary': DAUC_summary.copy(),
             'Gen_Dispatch': DAUC_PgenResult.copy(),
             'Region_Dispatch': DAUC_RegionDispatch.copy(),
             'Gen_PFR_up': DAUC_pfrup_Result.copy(),
             'Gen_PFR_dn': DAUC_pfrdn_Result.copy(),
             'Gen_AGC_up': DAUC_agcup_Result.copy(),
             'Gen_AGC_dn': DAUC_agcdn_Result.copy(),
             'ESS_Ch': DAUC_ess_ch.copy(),
             'ESS_Dis': DAUC_ess_dis.copy(),
             'DA_LMP': DA_LMP.copy(),
             'DA_Line_Flow': DAUC_LineFlow.copy(),
             'ESS SOC': DAUC_socResult.copy(),
             'ESS_PFR_up': DAUC_ess_pfr_up.copy(),
             'ESS_PFR_dn': DAUC_ess_pfr_dn.copy(),
             'ESS_AGC_up': DAUC_ess_agc_up.copy(),
             'ESS_AGC_dn': DAUC_ess_agc_dn.copy()}

np.save(DAUCResult_fp + "DAResult_Dict.npy", DAResults)

for i in list(DAResults.keys()):
    for j in list(DAResults[i].columns):
        if "Dum" in j:
            del DAResults[i][j]

with pd.ExcelWriter(DAUCResult_fp + 'Output.xlsx') as writer: 
    DAResults["Summary"].to_excel(writer, sheet_name = "Summary")
    DAResults["Gen_Dispatch"].to_excel(writer, sheet_name = "Dispatch")
    DAResults["Region_Dispatch"].to_excel(writer, sheet_name = "Regional Dispatch")
    DAResults["Gen_PFR_up"].to_excel(writer, sheet_name = "Gen PFRup")
    DAResults["Gen_PFR_dn"].to_excel(writer, sheet_name = "Gen PFRdn")
    DAResults["Gen_AGC_up"].to_excel(writer, sheet_name = "Gen AGCup")
    DAResults["Gen_AGC_dn"].to_excel(writer, sheet_name = "Gen AGCdn")
    DAResults["ESS_Ch"].to_excel(writer, sheet_name = "ESS Ch")
    DAResults["ESS_Dis"].to_excel(writer, sheet_name = "ESS Dis")
    DAResults["DA_LMP"].to_excel(writer, sheet_name = "DA LMP")
    DAResults["DA_Line_Flow"].to_excel(writer, sheet_name = "Line Flow")
    DAResults["ESS SOC"].to_excel(writer, sheet_name = "ESS SOC")
    DAResults["ESS_PFR_up"].to_excel(writer, sheet_name = "ESS PFRup")
    DAResults["ESS_PFR_dn"].to_excel(writer, sheet_name = "ESS PFRdn")
    DAResults["ESS_AGC_up"].to_excel(writer, sheet_name = "ESS AGCup")
    DAResults["ESS_AGC_dn"].to_excel(writer, sheet_name = "ESS AGCdn")


# In[ ]:





# In[10]:


# ---- ESS data preprocessing for Real-time operation

ESS_PowResults = pd.DataFrame(.0, columns = ["pow"],                index = pd.MultiIndex.from_product([list(UCins.DPESS_SET),range(1,(Simulation_len+extend_time)*inter_num+1)]),dtype='float64')
ESS_PowResults.index.names = ['essname','inter']
ESS_RTED_Dis = pd.DataFrame(.0, columns = ["dis"],                index = pd.MultiIndex.from_product([list(UCins.DPESS_SET),range(1,(Simulation_len+extend_time)*inter_num+1)]),dtype='float64')
ESS_RTED_Dis.index.names = ['essname','inter']
ESS_RTED_Ch = pd.DataFrame(.0, columns = ["ch"],                index = pd.MultiIndex.from_product([list(UCins.DPESS_SET),range(1,(Simulation_len+extend_time)*inter_num+1)]),dtype='float64')
ESS_RTED_Ch.index.names = ['essname','inter']
ESS_RTUC_Dis = pd.DataFrame(.0, columns = ["dis"],                index = pd.MultiIndex.from_product([list(UCins.DPESS_SET),range(1,Simulation_len+extend_time+1)]),dtype='float64')
ESS_RTUC_Dis.index.names = ['essname','hour']
ESS_RTUC_Ch = pd.DataFrame(.0, columns = ["ch"],                index = pd.MultiIndex.from_product([list(UCins.DPESS_SET),range(1,Simulation_len+extend_time+1)]),dtype='float64')
ESS_RTUC_Ch.index.names = ['essname','hour']
ESS_RTUC_Ch_INDIC = pd.DataFrame(0, columns = ["ch"],                index = pd.MultiIndex.from_product([list(UCins.DPESS_SET),range(1,Simulation_len+extend_time+1)]),dtype='int64')
ESS_RTUC_Ch_INDIC.index.names = ['essname','hour']
ESS_RTUC_Dis_INDIC = pd.DataFrame(0, columns = ["dis"],                index = pd.MultiIndex.from_product([list(UCins.DPESS_SET),range(1,Simulation_len+extend_time+1)]),dtype='int64')
ESS_RTUC_Dis_INDIC.index.names = ['essname','hour']
ESS_RTED_SOC_LOSS = pd.DataFrame(0, columns = ["loss"],                index = pd.MultiIndex.from_product([list(UCins.DPESS_SET),range(1,(Simulation_len+extend_time)*inter_num+1)]),dtype='float64')
ESS_RTED_SOC_LOSS.index.names = ['essname','inter']

# Create the simple interpolation of the ESS operation

for ei in UCins.DPESS_SET:
    for hi in range(1,Simulation_len+extend_time+1):
        if hi in UCins.HOUR_SET:
            for ii in range(1,inter_num+1):
                if hi == 1:
                    ESS_RTED_SOC_LOSS.loc[(ei,(hi-1)*inter_num+ii),'loss'] = ess_input.loc[ei,'ESS_InitSOC'] * ess_input.loc[ei,'ESS_LossRate'] / inter_num
                    prev = ess_input.loc[ei,'ESS_Pow0']
                else:
                    ESS_RTED_SOC_LOSS.loc[(ei,(hi-1)*inter_num+ii),'loss'] = UCins.soc[ei,hi-1].value * ess_input.loc[ei,'ESS_LossRate'] / inter_num
                    prev = ESS_PowResults.loc[(ei,(hi-1)*inter_num),'pow'] 
                    
                if ess_interpolate_method == 0:
                    interv = (UCins.ess_pow[ei,hi].value - prev) / inter_num
                    ESS_PowResults.loc[(ei,(hi-1)*inter_num+ii),"pow"] = prev + interv * ii
                elif ess_interpolate_method == 1:
                    ESS_PowResults.loc[(ei,(hi-1)*inter_num+ii),"pow"] = UCins.ess_pow[ei,hi].value
                    
        else:
            for ii in range(1,inter_num+1):
                ESS_RTED_SOC_LOSS.loc[(ei,(hi-1)*inter_num+ii),'loss'] = UCins.soc[ei,hi-RTED_hor].value * ess_input.loc[ei,'ESS_LossRate'] / inter_num
                
for ei in UCins.DPESS_SET:
    for i in range(1,(Simulation_len+extend_time)*inter_num+1):
        if ESS_PowResults.loc[(ei,i),'pow'] > 1e-4:
            ESS_RTED_Dis.loc[(ei,i),'dis'] = ESS_PowResults.loc[(ei,i),'pow']
            ESS_RTED_Ch.loc[(ei,i),'ch'] = 0
        elif ESS_PowResults.loc[(ei,i),'pow'] < -1e-4:
            ESS_RTED_Dis.loc[(ei,i),'dis'] = 0
            ESS_RTED_Ch.loc[(ei,i),'ch'] = - ESS_PowResults.loc[(ei,i),'pow']
        else:
            ESS_RTED_Dis.loc[(ei,i),'dis'] = 0
            ESS_RTED_Ch.loc[(ei,i),'ch'] = 0        

# If use 24 hour horizon, use the code below.  
#         if i in range(Simulation_len*inter_num+1, (Simulation_len+RTUC_hor-RTUC_loh)*inter_num+1):
#             ESS_RTED_Dis.loc[(ei,i),'dis'] = ESS_RTED_Dis.loc[(ei,i-Simulation_len*inter_num),'dis']
#             ESS_RTED_Ch.loc[(ei,i),'ch'] = ESS_RTED_Ch.loc[(ei,i-Simulation_len*inter_num),'ch']
            
for ei in UCins.DPESS_SET:
    for hi in range(1,Simulation_len+extend_time+1):
        ESS_RTUC_Dis.loc[(ei,hi),'dis'] = UCins.ess_dis[ei,hi].value
        ESS_RTUC_Ch.loc[(ei,hi),'ch'] = UCins.ess_ch[ei,hi].value  
        
# If use 24 hour horizon, use the code below.    
#         if hi in UCins.HOUR_SET:
#             ESS_RTUC_Dis.loc[(ei,hi),'dis'] = UCins.ess_dis[ei,hi].value
#             ESS_RTUC_Ch.loc[(ei,hi),'ch'] = UCins.ess_ch[ei,hi].value        
#         else:
#             ESS_RTUC_Dis.loc[(ei,hi),'dis'] = ESS_RTUC_Dis.loc[(ei,hi-Simulation_len),'dis']
#             ESS_RTUC_Ch.loc[(ei,hi),'ch'] = ESS_RTUC_Ch.loc[(ei,hi-Simulation_len),'ch']
#             ESS_RTUC_Dis_INDIC.loc[(ei,hi),'dis'] = ESS_RTUC_Dis_INDIC.loc[(ei,hi-Simulation_len),'dis']
#             ESS_RTUC_Ch_INDIC.loc[(ei,hi),'ch'] = ESS_RTUC_Ch_INDIC.loc[(ei,hi-Simulation_len),'ch']
            
                    
        if ESS_RTUC_Dis.loc[(ei,hi),'dis'] > 1e-4:
            ESS_RTUC_Dis_INDIC.loc[(ei,hi),'dis'] = 1
        if ESS_RTUC_Ch.loc[(ei,hi),'ch'] > 1e-4:
            ESS_RTUC_Ch_INDIC.loc[(ei,hi),'ch'] = 1 


# In[11]:


# --------------- Real-time Operation ----------------

# ---- Data savings and intermediate data creation

PFRup_insuf = 0
PFRdn_insuf = 0
AGCup_insuf = 0
AGCdn_insuf = 0

RTUC_lol = pd.DataFrame(columns = ['lol'], index = range(1,Simulation_len+1))
RTED_lol = pd.DataFrame(columns = ['lol'], index = range(1,Simulation_len*inter_num+1))
RTUC_sol = pd.DataFrame(columns = ['sol'], index = range(1,Simulation_len+1))
RTED_sol = pd.DataFrame(columns = ['sol'], index = range(1,Simulation_len*inter_num+1))
RTUC_RU_slack = pd.DataFrame(columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+1))
RTUC_RD_slack = pd.DataFrame(columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+1))
RTED_RU_slack = pd.DataFrame(columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len*inter_num+1))
RTED_RD_slack = pd.DataFrame(columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len*inter_num+1))
RTUC_CU_slack = pd.DataFrame(columns = line_list, index = range(1,Simulation_len+1))
RTUC_CD_slack = pd.DataFrame(columns = line_list, index = range(1,Simulation_len+1))
RTED_CU_slack = pd.DataFrame(columns = line_list, index = range(1,Simulation_len*inter_num+1))
RTED_CD_slack = pd.DataFrame(columns = line_list, index = range(1,Simulation_len*inter_num+1))

RTED_PgenResult = pd.DataFrame(.0, columns = Supply_List["GEN_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTUC_PgenResult = pd.DataFrame(.0, columns = Supply_List["GEN_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTED_RegionDispatch = pd.DataFrame(.0, columns = [str(x) for x in set(list(bus_input["Region"]))], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_pfrup_Result = pd.DataFrame(.0, columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTUC_pfrup_Result = pd.DataFrame(.0, columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTED_pfrdn_Result = pd.DataFrame(.0, columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTUC_pfrdn_Result = pd.DataFrame(.0, columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTED_agcup_Result = pd.DataFrame(.0, columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTUC_agcup_Result = pd.DataFrame(.0, columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTED_agcdn_Result = pd.DataFrame(.0, columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTUC_agcdn_Result = pd.DataFrame(.0, columns = Supply_List["DPGEN_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTED_LineFlow = pd.DataFrame(np.nan, columns = line_list, index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTUC_LineFlow = pd.DataFrame(np.nan, columns = line_list, index = range(1,Simulation_len+1), dtype = 'float64')

RTUC_socResult = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTUC_relax = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTUC_ess_dis = pd.DataFrame(.0, columns = Supply_List["ESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTUC_ess_ch = pd.DataFrame(.0, columns = Supply_List["ESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTUC_ess_pow = pd.DataFrame(.0, columns = Supply_List["ESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTUC_ess_pfr_up = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTUC_ess_pfr_dn = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTUC_ess_agc_up = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')
RTUC_ess_agc_dn = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len+1), dtype = 'float64')

RTED_socResult = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_relax = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_ess_dis = pd.DataFrame(.0, columns = Supply_List["ESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_ess_ch = pd.DataFrame(.0, columns = Supply_List["ESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_ess_pow = pd.DataFrame(.0, columns = Supply_List["ESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_ess_pfr_up = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_ess_pfr_dn = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_ess_agc_up = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
RTED_ess_agc_dn = pd.DataFrame(.0, columns = Supply_List["DPESS_SET"], index = range(1,Simulation_len*inter_num+1), dtype = 'float64')

RTED_pfrup_Insuf = pd.DataFrame(.0, columns = ['Insuf'], index = range(1,Simulation_len*inter_num+1))
RTED_pfrdn_Insuf = pd.DataFrame(.0, columns = ['Insuf'], index = range(1,Simulation_len*inter_num+1))
RTED_agcup_Insuf = pd.DataFrame(.0, columns = ['Insuf'], index = range(1,Simulation_len*inter_num+1))
RTED_agcdn_Insuf = pd.DataFrame(.0, columns = ['Insuf'], index = range(1,Simulation_len*inter_num+1))

RTED_LMP = pd.DataFrame(.0, columns = bus_list, index = range(1,Simulation_len*inter_num+1), dtype = 'float64')
Renew_curtail = pd.DataFrame(.0, columns = Supply_List["GEN2_SET"], index = range(1,Simulation_len*inter_num+1))

RTED_Total_Load_new    = pd.DataFrame(.0, columns = ['New_Load'], index = range(1,Simulation_len*inter_num+1))
RTED_Gen_cost_interval = pd.DataFrame(.0, columns = ['Gen_cost'], index = range(1,Simulation_len*inter_num+1))

RTED_gen_cost = 0
RTED_ess_cost = 0
RTED_reserve_cost = 0
RTED_penalty_cost = 0
RTUC_time = 0
RTED_time = 0
# RTED_solver_wall_time = 0


# In[ ]:





# In[12]:


# ---- Real-time operation loop

# For more comments, please go to the next cell in Jupyter
# In Python IDEs, please go to the next outer loop, i.e., next "for i in range(1,23)"

for i in range(1,2):
    
    if i == 1:
        
        # ----------------- FIRST RTED MODULE ------------- #
        
        gen_initialMW = pd.DataFrame(.0, columns = ['IntPow'], index = Supply_List["GEN1_SET"])
        gen_initialMW.index.names = ['genname']
        gen_initialPmax = pd.DataFrame(.0, columns = ['Pmax'], index = Supply_List["GEN1_SET"])
        gen_initialPmax.index.names = ['genname']
        gen_initialPmin = pd.DataFrame(.0, columns = ['Pmin'], index = Supply_List["GEN1_SET"])
        gen_initialPmin.index.names = ['genname']
        RTED_ess_InitPow = pd.DataFrame(.0, columns = ['Pow0'], index = Supply_List["DPESS_SET"])
        RTED_ess_InitPow.index.names = ['essname']
        SOC_initial = pd.DataFrame(.0, columns = ['soc'], index = Supply_List["DPESS_SET"])
        SOC_initial.index.names = ['essname']
        
        if close_loop_flag == 1:
            gen_initialMW = pd.read_csv(Dynamic_ex_fp + 'Dispatch_Setpoint.csv')
            SOC_initial = pd.read_csv(Dynamic_ex_fp + 'SOC_Setpoint.csv')
            RTED_ess_InitPow = pd.read_csv(Dynamic_ex_fp + 'SOC_Setpoint.csv')
            
            # I'm not sure whether the dynamic setpoints will change the trajectories
            Inflex_EDPmin_cur = pd.read_csv(Dynamic_ex_fp + 'Dyn_New_Inflex_Traj_Pmin.csv')
            Inflex_EDPmax_cur = pd.read_csv(Dynamic_ex_fp + 'Dyn_New_Inflex_Traj_Pmax.csv')
            Flex_EDPmin_cur = pd.read_csv(Dynamic_ex_fp + 'Dyn_New_Flex_Traj_Pmin.csv')
            Flex_EDPmax_cur = pd.read_csv(Dynamic_ex_fp + 'Dyn_New_Flex_Traj_Pmax.csv')
        
        # First ED in first hour has no trajectory
        for gi in Supply_List["GEN1_SET"]:
            gen_initialMW.loc[gi,'IntPow'] = gen_input.loc[gi,'InitPow']
            gen_initialPmax.loc[gi,'Pmax'] = gen_input.loc[gi,'Pmax']
            gen_initialPmin.loc[gi,'Pmin'] = gen_input.loc[gi,'Pmin']

        for ei in Supply_List["DPESS_SET"]:
            SOC_initial.loc[ei,'soc'] = ess_input.loc[ei,'ESS_InitSOC'] * ess_input.loc[ei,'Capacity']
            RTED_ess_InitPow.loc[ei,'Pow0'] = ess_input.loc[ei, 'ESS_Pow0']

        Inflex_EDPmin_cur = pd.DataFrame(Inflex_EDPmin.loc[(Supply_List["INFLEX_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'Pmin'])
        Inflex_EDPmax_cur = pd.DataFrame(Inflex_EDPmax.loc[(Supply_List["INFLEX_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'Pmax'])
        Flex_EDPmax_cur = pd.DataFrame(.0, columns = ["Pmax"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)]))
        Flex_EDPmax_cur.index.names = ['genname','inter']
        Flex_EDPmin_cur = pd.DataFrame(.0, columns = ["Pmin"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)]))
        Flex_EDPmin_cur.index.names = ['genname','inter']
        
        ESS_RTED_ch_cur = pd.DataFrame(ESS_RTED_Ch.loc[(Supply_List["DPESS_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'ch'])
        ESS_RTED_dis_cur = pd.DataFrame(ESS_RTED_Dis.loc[(Supply_List["DPESS_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'dis'])
        ESS_RTED_SOC_LOSS_cur = pd.DataFrame(ESS_RTED_SOC_LOSS.loc[(Supply_List["DPESS_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'loss'])

        for g in Supply_List["FLEX_SET"]:
            for j in range(1,RTED_hor+1):
                Flex_EDPmin_cur.loc[(g,j),'Pmin'] = gen_input.loc[g,'InitStatus'] * gen_input.loc[g,'Pmin']
                Flex_EDPmax_cur.loc[(g,j),'Pmax'] = gen_input.loc[g,'InitStatus'] * gen_input.loc[g,'Pmax']
                
        # Here starts the first ED in the hour
        RTEDTime1 = time.process_time()
        RTEDdatprev = RTED_create_dat(RTED_DAT_fp, (i-1)*inter_num+1, inter_num, setting_input, RTED_res, RTED_hor, bus_input, gen_input, ess_input, line_input,                                      PTDF_input, reserve_input, Load_TS["RTED_Load"], Load_TS["RTED_Load_raw"], Supply_TS["RTED_G23"],                                      Supply_TS["RTED_E1"], Supply_List, Inflex_EDPmin_cur, Inflex_EDPmax_cur, Flex_EDPmin_cur, Flex_EDPmax_cur,                                      ESS_RTED_ch_cur, ESS_RTED_dis_cur, ESS_RTED_SOC_LOSS_cur, SOC_initial,                                      gen_initialPmax, gen_initialPmin, gen_initialMW, RTED_ess_InitPow, Reserve_TS)
        
        EDins = EDmdl.create_instance(RTED_DAT_fp + str((i-1)*inter_num+1) + '.dat')       
        EDins.dual = pe.Suffix(direction = pe.Suffix.IMPORT) # To include the duals if any
        
        # sovle distribution PF to obtain distribution power     
        Austin.snapshot_run()
        Vmag = Austin.getVmag()
        Vpu = np.array([Vmag[i]/Vbase[i] for i in range(len(Vmag))])
        Vpu_ts[:, 0: 1 ] = Vpu.reshape((len(Vpu), 1)) 
        Feeder_head_power = []
        Feeder_head_power.append(Austin.dssCircuit.TotalPower()[0]/1000)
        Feeder_head_power = np.array(Feeder_head_power)   
                                        
        EDins.Load_Bus[2,1]=-float(Feeder_head_power)*10   
        
        v1 = Austin.dssCircuit.AllNodeVmagPUByPhase(1) # store phase 1 nodes 
        v1_name = Austin.dssCircuit.AllNodeNamesByPhase(1)  # name that match the voltage   
        v1_all.append(v1) # get all snapshot in the list                         
        Feeder_total_power.append(Feeder_head_power)
        #solve RTED with distribution power updates       
        results = opt_ed.solve(EDins, tee=True, keepfiles=True)
        
        # get gen and load and update ACPF cases.
        # update the load
        kk=0
        for ldi in list([2,3,5,6,8,10,12]):
            pfss.PQ.p0.v[kk] = EDins.Load_Bus[ldi,1].value/100
            kk=kk+1
        # update the generation from geneators and PV   
        gkk=0    
        for gi in Supply_List["DPGEN_SET"]: 
            if gi == 'SOUTHG1': # Slack bus generator
                pfss.Slack.p0.v =  EDins.gen_power[gi,1].value/100
            else:
                pfss.PV.p0.v[gkk] =  EDins.gen_power[gi,1].value/100
                gkk=gkk+1
        # update the generation from ESS         
        for gi in Supply_List["DPESS_SET"]:              
            pfss.PV.p0.v[gkk] =  EDins.ess_pow[gi,1].value/100
            gkk=gkk+1    
            
        pfss.PV.cache.refresh()
        pfss.PQ.cache.refresh()
        # setup system
        pfss.setup()
        # run power flow
        pfss.PFlow.run()      
        
        
        #record bus 2 voltage magnitude
        v1_bus2 = pd.DataFrame(np.reshape(pfss.Bus.v.v, (1,len(pfss.Bus.v.v))),columns=[list(range(19))])

        #update the feeder head voltage
        if pfss.PFlow.converged == True:
            temp_v =  pfss.Bus.v.v[1]       
            Austin.updateSubVmag(temp_v) 
        else: 
            Austin.updateSubVmag(1)     
        
        RTEDTime2 = time.process_time()
        RTED_time += RTEDTime2 - RTEDTime1
        # RTED_solver_wall_time += float(results.Solver.Wall_time)

        # ---- Post-solution data retrieval
        
        RTED_gen_cost += EDins.gen_cost[1].value
        RTED_ess_cost += EDins.ess_cost[1].value
        RTED_reserve_cost += EDins.reserve_cost[1].value
        RTED_penalty_cost += EDins.penalty_cost[1].value
        
        RT_LMP = ExportLMP(EDins, EDins.dual, line_input, [list(EDins.INTER_SET)[0]], EDins.LOAD_BUS_SET, EDins.LINE_SET).Calculate_LMP()
        
        for k in Supply_List["GEN2_SET"]:
            Renew_curtail.loc[1,k] = (Supply_TS["RTED_G23"].loc[1,k] - EDins.gen_power[k,1].value) / inter_num

        for ei in Supply_List["DPESS_SET"]:
            RTED_ess_dis.loc[1,ei] = EDins.ess_dis[ei,1].value
            RTED_ess_ch.loc[1,ei] = EDins.ess_ch[ei,1].value
            RTED_ess_pow.loc[1,ei] = EDins.ess_pow[ei,1].value
            RTED_socResult.loc[1,ei] = EDins.soc[ei,1].value
            RTED_relax.loc[1,ei] = EDins.soc_relax1[ei,1].value + EDins.soc_relax2[ei,1].value
            RTED_ess_pfr_up.loc[1,ei] = EDins.ess_pfr_pos[ei,1].value 
            RTED_ess_pfr_dn.loc[1,ei] = EDins.ess_pfr_neg[ei,1].value 
            RTED_ess_agc_up.loc[1,ei] = EDins.ess_agc_pos[ei,1].value
            RTED_ess_agc_dn.loc[1,ei] = EDins.ess_agc_neg[ei,1].value
        for ei in Supply_List["ESS1_SET"]:
            RTED_ess_ch.loc[1,ei] = -Supply_TS["RTED_E1"].loc[1,ei] if Supply_TS["RTED_E1"].loc[1,ei] <= 0 else 0
            RTED_ess_dis.loc[1,ei] = Supply_TS["RTED_E1"].loc[1,ei] if Supply_TS["RTED_E1"].loc[1,ei] > 0 else 0
            RTED_ess_pow.loc[1,ei] = Supply_TS["RTED_E1"].loc[1,ei]

        for gi in Supply_List["DPGEN_SET"]:
            RTED_PgenResult.loc[1,gi] = EDins.gen_power[gi,1].value
        for gi in Supply_List["GEN3_SET"]:
            RTED_PgenResult.loc[1,gi] = Supply_TS["RTED_G23"].loc[1,gi]
            
        for j in RTED_RegionDispatch.columns:
            for gi in Supply_List["DPGEN_SET"]:
                if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                    RTED_RegionDispatch.loc[1,j] += EDins.gen_power[gi,1].value
            for gi in Supply_List["GEN3_SET"]:
                if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                    RTED_RegionDispatch.loc[1,j] += Supply_TS["RTED_G23"].loc[1,gi]

            for ei in Supply_List["DPESS_SET"]:
                if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                    RTED_RegionDispatch.loc[1,j] += EDins.ess_pow[ei,1].value
            for ei in Supply_List["ESS1_SET"]:
                if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                    RTED_RegionDispatch.loc[1,j] += Supply_TS["RTED_E1"].loc[1,ei]
            
        for gi in Supply_List["GEN1_SET"]:
            RTED_RU_slack.loc[1,gi] = EDins.gen_ramp_up_slack[gi,1].value
            RTED_RD_slack.loc[1,gi] = EDins.gen_ramp_dn_slack[gi,1].value
        
        for li in line_list:
            RTED_CU_slack.loc[1,li] = EDins.Ln_Cap_up_Slack[li,1].value
            RTED_CD_slack.loc[1,li] = EDins.Ln_Cap_dn_Slack[li,1].value
            if abs(line_input.loc[li,"Active"] - 1) <= 1e-4:
                RTED_LineFlow.loc[1,li] = sum(EDins.Ln_PTDF[li, EDins.Gen_Bus[gi]] * EDins.gen_power[gi,1].value for gi in EDins.DPGEN_SET) +                                    sum(EDins.Ln_PTDF[li, EDins.ESS_Bus[ei]]* EDins.ess_pow[ei,1].value                                     for ei in EDins.DPESS_SET) - sum(EDins.Ln_PTDF[li, ldi] * (EDins.Load_Bus[ldi,1].value - EDins.lol[ldi,1].value + EDins.sol[ldi,1].value) for ldi in EDins.LOAD_BUS_SET)

        for bi in bus_list:
            RTED_LMP.loc[1,bi] = RT_LMP.loc[1,bi]
            
        RTED_lol.loc[1,'lol'] = sum(EDins.lol[ldi, 1].value for ldi in EDins.LOAD_BUS_SET)
        RTED_sol.loc[1,'sol'] = sum(EDins.sol[ldi, 1].value for ldi in EDins.LOAD_BUS_SET)
        
        RTED_pfrup_Insuf.loc[1] = EDins.sys_IR1_pos[1].value
        RTED_pfrdn_Insuf.loc[1] = EDins.sys_IR1_neg[1].value
        RTED_agcup_Insuf.loc[1] = EDins.sys_IR2_pos[1].value
        RTED_agcdn_Insuf.loc[1] = EDins.sys_IR2_neg[1].value
        
        RTED_Total_Load_new.loc[1] = sum(EDins.Load_Bus[ldi,1].value  for ldi in EDins.LOAD_BUS_SET)
        RTED_Gen_cost_interval.loc [1] = EDins.gen_cost[1].value        
            
        for gi in Supply_List["DPGEN_SET"]:
            RTED_pfrup_Result.loc[1,gi] = EDins.gen_pfr_pos[gi,1].value
            RTED_pfrdn_Result.loc[1,gi] = EDins.gen_pfr_neg[gi,1].value
            RTED_agcup_Result.loc[1,gi] = EDins.gen_agc_pos[gi,1].value
            RTED_agcdn_Result.loc[1,gi] = EDins.gen_agc_neg[gi,1].value
             
        os.makedirs(os.path.dirname(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str(1) + '.csv'), exist_ok=True)    
        with open(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str(1) + '.csv', 'w') as f:
            f.write('number,Pgen,PFR_up,PFR_dn,AGC_up,AGC_dn,SOC\n')
            for gi in Supply_List["DPGEN_SET"]:
                f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[1,gi], RTED_pfrup_Result.loc[1,gi],                                                     RTED_pfrdn_Result.loc[1,gi], RTED_agcup_Result.loc[1,gi],                                                     RTED_agcdn_Result.loc[1,gi], np.nan))
            for gi in Supply_List["GEN3_SET"]:
                f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[1,gi], np.nan, np.nan, np.nan, np.nan, np.nan))
                
            for ei in Supply_List["DPESS_SET"]:
                f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[1,ei], RTED_ess_pfr_up.loc[1,ei],                                                     RTED_ess_pfr_dn.loc[1,ei], RTED_ess_agc_up.loc[1,ei],                                                     RTED_ess_agc_dn.loc[1,ei], RTED_socResult.loc[1,ei])) 
                
            # Should we give the SOC value of the non-dispatchable ESSs to Dynamic Team?
            
            for ei in Supply_List["ESS1_SET"]:
                f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[1,ei], np.nan, np.nan, np.nan, np.nan, np.nan))  
        
        # ------------------ RTUC MODULE ------------------ #
        
        Flex_UC_initial_Stat = pd.DataFrame(.0, columns = ['IntStat'], index = Supply_List["FLEX_SET"])
        Flex_UC_initial_Stat.index.names = ['genname']
        Flex_UC_initial_Hour = pd.DataFrame(.0, columns = ['IntHour'], index = Supply_List["FLEX_SET"])
        Flex_UC_initial_Hour.index.names = ['genname']
        InitialGenMax = pd.DataFrame(.0, columns = ['Pmax'], index = Supply_List["INFLEX_SET"])
        InitialGenMax.index.names = ['genname']
        InitialGenMin = pd.DataFrame(.0, columns = ['Pmin'], index = Supply_List["INFLEX_SET"])
        InitialGenMin.index.names = ['genname']
        
        Inflex_UCPmin_cur = pd.DataFrame(Inflex_UCPmin.loc[(Supply_List["INFLEX_SET"],range(i+1,i+RTUC_hor+1)),'Pmin'])
        Inflex_UCPmax_cur = pd.DataFrame(Inflex_UCPmax.loc[(Supply_List["INFLEX_SET"],range(i+1,i+RTUC_hor+1)),'Pmax'])

        ESS_RTUC_ch_cur = pd.DataFrame(ESS_RTUC_Ch.loc[(Supply_List["DPESS_SET"],range(i+1,i+RTUC_hor+1)),'ch'])
        ESS_RTUC_dis_cur = pd.DataFrame(ESS_RTUC_Dis.loc[(Supply_List["DPESS_SET"],range(i+1,i+RTUC_hor+1)),'dis'])
        RTUC_SOC_init = pd.DataFrame(.0, columns = ['IntSOC'], index = Supply_List["DPESS_SET"])
        RTUC_SOC_init.index.names = ['essname']
        RTUC_ess_InitPow = pd.DataFrame(.0, columns = ['ESS_Pow0'], index = Supply_List["DPESS_SET"])
        RTUC_ess_InitPow.index.names = ['essname']
        for ei in Supply_List["DPESS_SET"]:
            RTUC_SOC_init.loc[ei,'IntSOC'] = EDins.soc[ei,inter_num].value
            RTUC_ess_InitPow.loc[ei,'ESS_Pow0'] = EDins.ess_pow[ei,inter_num].value

        # The first UC has no initial trajectories
        RTUC_initialMW = pd.DataFrame(.0, columns = ['IntPow'], index = Supply_List["DPGEN_SET"])
        RTUC_initialMW.index.names = ['genname']
        for gi in Supply_List["DPGEN_SET"]:
            RTUC_initialMW.loc[gi,'IntPow'] = EDins.gen_power[gi,i*inter_num].value           
            
        for gi in Supply_List["FLEX_SET"]:
            Flex_UC_initial_Stat.loc[gi,'IntStat'] = gen_input.loc[gi,'InitStatus']
            Flex_UC_initial_Hour.loc[gi,'IntHour'] = gen_input.loc[gi,'InitHour']
            
        for gi in Supply_List["INFLEX_SET"]:
            InitialGenMax.loc[gi, 'Pmax'] = gen_input.loc[gi,'Pmax']
            InitialGenMin.loc[gi, 'Pmin'] = gen_input.loc[gi,'Pmin']
        
        RTUCTime1 = time.process_time()
        RTUCdat = RTUC_create_dat(RTUC_DAT_fp, i, setting_input, RTUC_res, RTUC_hor, bus_input, gen_input, ess_input, line_input,                                   PTDF_input, reserve_input, Load_TS["RTUC_Load"], Load_TS["RTUC_Load_raw"], Supply_TS["RTUC_G23"],                                   Supply_TS["RTUC_E1"], Supply_List, Inflex_UCPmin_cur, Inflex_UCPmax_cur, ESS_RTUC_ch_cur, ESS_RTUC_dis_cur,                                   RTUC_SOC_init, InitialGenMax, InitialGenMin, Flex_UC_initial_Stat, Flex_UC_initial_Hour, RTUC_initialMW, RTUC_ess_InitPow, Reserve_TS)       
        
        RTUCins = RTUCmdl.create_instance(RTUC_DAT_fp + 'RTUC' + str(i) + '.dat')
        results = opt_uc.solve(RTUCins, tee=True, keepfiles=True)
        RTUCTime2 = time.process_time()
        RTUC_time += RTUCTime2 - RTUCTime1
        
        Flex_UC_initial_Stat_prev = Flex_UC_initial_Stat
        Flex_UC_initial_Hour_prev = Flex_UC_initial_Hour
        
        Inflex_UCPmin_prev = Inflex_UCPmin_cur
        Inflex_UCPmax_prev = Inflex_UCPmax_cur
        
        for gi in Supply_List["DPGEN_SET"]:
            RTUC_PgenResult.loc[2,gi] = RTUCins.gen_power[gi,2].value
            
        for ei in Supply_List["DPESS_SET"]:
            RTUC_ess_dis.loc[2,ei] = RTUCins.ess_dis[ei,2].value
            RTUC_ess_ch.loc[2,ei] = RTUCins.ess_ch[ei,2].value
                
        for ei in Supply_List["ESS1_SET"]:
            RTUC_ess_dis.loc[2,ei] = Supply_TS["RTUC_E1"].loc[2,ei] if Supply_TS["RTUC_E1"].loc[2,ei] > 0 else 0
            RTUC_ess_ch.loc[2,ei] = -Supply_TS["RTUC_E1"].loc[2,ei] if Supply_TS["RTUC_E1"].loc[2,ei] <= 0 else 0
            
        for gi in Supply_List["GEN3_SET"]:
            RTUC_PgenResult.loc[2,gi] = Supply_TS["RTUC_G23"].loc[2,gi]
            
        for gi in Supply_List["GEN1_SET"]:
            RTUC_RU_slack.loc[2,gi] = RTUCins.gen_ramp_up_slack[gi,2].value
            RTUC_RD_slack.loc[2,gi] = RTUCins.gen_ramp_dn_slack[gi,2].value
        
        for li in line_list:
            RTUC_CU_slack.loc[2,li] = RTUCins.Ln_Cap_up_Slack[li,2].value
            RTUC_CD_slack.loc[2,li] = RTUCins.Ln_Cap_dn_Slack[li,2].value
            if abs(line_input.loc[li,"Active"] - 1) <= 1e-4:
                RTUC_LineFlow.loc[2,li] = sum(RTUCins.Ln_PTDF[li, RTUCins.Gen_Bus[gi]] * RTUCins.gen_power[gi,2].value for gi in RTUCins.DPGEN_SET) +                                    sum(RTUCins.Ln_PTDF[li, RTUCins.ESS_Bus[ei]]* RTUCins.ess_pow[ei,2].value                                     for ei in RTUCins.DPESS_SET) - sum(RTUCins.Ln_PTDF[li, ldi] * (RTUCins.Load_Bus[ldi,2]                                     - RTUCins.lol[ldi,2].value + RTUCins.sol[ldi,2].value) for ldi in RTUCins.LOAD_BUS_SET)

        RTUC_lol.loc[2,'lol'] = sum(RTUCins.lol[ldi, 2].value for ldi in RTUCins.LOAD_BUS_SET)
        RTUC_sol.loc[2,'sol'] = sum(RTUCins.sol[ldi, 2].value for ldi in RTUCins.LOAD_BUS_SET)
            
        for gi in Supply_List["DPGEN_SET"]:
            RTUC_pfrup_Result.loc[2,gi] = RTUCins.gen_pfr_pos[gi,2].value
            RTUC_pfrdn_Result.loc[2,gi] = RTUCins.gen_pfr_neg[gi,2].value
            RTUC_agcup_Result.loc[2,gi] = RTUCins.gen_agc_pos[gi,2].value
            RTUC_agcdn_Result.loc[2,gi] = RTUCins.gen_agc_neg[gi,2].value
            
        for ei in Supply_List["DPESS_SET"]:
            RTUC_socResult.loc[2,ei] = RTUCins.soc[ei,2].value
            RTUC_relax.loc[2,ei] = RTUCins.soc_relax1[ei,2].value + RTUCins.soc_relax2[ei,2].value
            RTUC_ess_pfr_up.loc[2,ei] = RTUCins.ess_pfr_pos[ei,2].value 
            RTUC_ess_pfr_dn.loc[2,ei] = RTUCins.ess_pfr_neg[ei,2].value 
            RTUC_ess_agc_up.loc[2,ei] = RTUCins.ess_agc_pos[ei,2].value
            RTUC_ess_agc_dn.loc[2,ei] = RTUCins.ess_agc_neg[ei,2].value
                
        # For trajectory modeling, there are still some hard code. 
        # They are related to the time resolution/horizon of the RTUC/RTED.
        # They are hard to remove and we will investigate them later.
        
        Flex_EDPmax = pd.DataFrame(.0,                       columns = ["Pmax"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(2,(RTUC_hor+1)*inter_num)]))
        Flex_EDPmin = pd.DataFrame(.0,                       columns = ["Pmin"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(2,(RTUC_hor+1)*inter_num)]))
                            
        for gi in Supply_List["FLEX_SET"]:
            for ii in range((i-1)*inter_num+2,(i-1)*inter_num+(RTUC_hor+1)*inter_num):
                Flex_EDPmax.loc[(gi,ii),'Pmax'] = gen_input.loc[gi,'InitStatus'] * gen_input.loc[gi,'Pmax']
                Flex_EDPmin.loc[(gi,ii),'Pmin'] = gen_input.loc[gi,'InitStatus'] * gen_input.loc[gi,'Pmin']                                                                          

        for gi in Supply_List["FLEX_SET"]:
            intereq_on = gen_input.loc[gi,'SUTime']/RTED_res
            intereq_off = gen_input.loc[gi,'SDTime']/RTED_res
            for s in range(RTUC_hor):
                if abs(RTUCins.gen_startup[gi,i+1+s].value - 1) <= 1e-4:
                    for n in range(1,inter_num+1):
                        if intereq_on - n > -1e-4:
                            Flex_EDPmax.loc[(gi,(i+s)*inter_num-n),'Pmax'] = (intereq_on - n) / intereq_on * gen_input.loc[gi,'Pmax']
                            Flex_EDPmin.loc[(gi,(i+s)*inter_num-n),'Pmin'] = (intereq_on - n) / intereq_on * gen_input.loc[gi,'Pmin']
                        else:
                            Flex_EDPmax.loc[(gi,(i+s)*inter_num-n),'Pmax'] = 0
                            Flex_EDPmin.loc[(gi,(i+s)*inter_num-n),'Pmin'] = 0
                    for ss in range((i+s)*inter_num, (i+RTUC_hor)*inter_num):
                        Flex_EDPmax.loc[(gi,ss),'Pmax'] = gen_input.loc[gi,'Pmax']
                        Flex_EDPmin.loc[(gi,ss),'Pmin'] = gen_input.loc[gi,'Pmin']  

                if abs(RTUCins.gen_shutdow[gi,i+1+s].value - 1) <= 1e-4:
                    for n in range(1,inter_num+1):
                        if intereq_off - n > -1e-4:
                            Flex_EDPmax.loc[(gi,(i+s)*inter_num+n),'Pmax'] = gen_input.loc[gi,'Pmax'] * (intereq_off-n) / intereq_off
                            Flex_EDPmin.loc[(gi,(i+s)*inter_num+n),'Pmin'] = gen_input.loc[gi,'Pmin'] * (intereq_off-n) / intereq_off   
                        else:
                            Flex_EDPmax.loc[(gi,(i+s)*inter_num+n),'Pmax'] = 0
                            Flex_EDPmin.loc[(gi,(i+s)*inter_num+n),'Pmin'] = 0
                    for ss in range((i+s+1)*inter_num, (i+RTUC_hor)*inter_num):
                        Flex_EDPmax.loc[(gi,ss),'Pmax'] = 0
                        Flex_EDPmin.loc[(gi,ss),'Pmin'] = 0    
            
        # ------------- REMAINING RTED MODULE -------------- #
        
        for e in range(2+(i-1)*12,13+(i-1)*12):
                
            gen_initialPmax = pd.DataFrame(.0, columns = ['Pmax'], index = Supply_List["GEN1_SET"])
            gen_initialPmax.index.names = ['genname']
            gen_initialPmin = pd.DataFrame(.0, columns = ['Pmin'], index = Supply_List["GEN1_SET"])
            gen_initialPmin.index.names = ['genname']
            SOC_initial = pd.DataFrame(.0, columns = ['soc'], index = Supply_List["DPESS_SET"])
            SOC_initial.index.names = ['essname']
            RTED_ess_InitPow = pd.DataFrame(.0, columns = ['Pow0'], index = Supply_List["DPESS_SET"])
            RTED_ess_InitPow.index.names = ['essname']
            gen_initialMW = pd.DataFrame(.0, columns = ['IntPow'], index = Supply_List["GEN1_SET"])
            gen_initialMW.index.names = ['genname']
            
            for gi in Supply_List["INFLEX_SET"]:
                gen_initialPmax.loc[gi,'Pmax'] = Inflex_EDPmax_cur.loc[gi,'Pmax'][e-1]
                gen_initialPmin.loc[gi,'Pmin'] = Inflex_EDPmin_cur.loc[gi,'Pmin'][e-1]
            for gi in Supply_List["FLEX_SET"]:
                gen_initialPmax.loc[gi,'Pmax'] = Flex_EDPmax_cur.loc[gi,'Pmax'][e-1]
                gen_initialPmin.loc[gi,'Pmin'] = Flex_EDPmin_cur.loc[gi,'Pmin'][e-1]
            
            Inflex_EDPmin_cur = pd.DataFrame(Inflex_EDPmin.loc[(Supply_List["INFLEX_SET"],range(e,e+RTED_hor)),'Pmin'])
            Inflex_EDPmax_cur = pd.DataFrame(Inflex_EDPmax.loc[(Supply_List["INFLEX_SET"],range(e,e+RTED_hor)),'Pmax'])
            
            ESS_RTED_ch_cur = pd.DataFrame(ESS_RTED_Ch.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'ch'])
            ESS_RTED_dis_cur = pd.DataFrame(ESS_RTED_Dis.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'dis'])
            ESS_RTED_SOC_LOSS_cur = pd.DataFrame(ESS_RTED_SOC_LOSS.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'loss'])
            for ei in Supply_List["DPESS_SET"]:
                RTED_ess_InitPow.loc[ei,'Pow0'] = EDins.ess_pow[ei,e-1].value
                SOC_initial.loc[ei,'soc'] = EDins.soc[ei,e-1].value

            for gi in Supply_List["GEN1_SET"]:
                gen_initialMW.loc[gi,'IntPow'] = EDins.gen_power[gi,e-1].value
                
            Flex_EDPmax_cur = pd.DataFrame(.0, columns = ["Pmax"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(e,e+RTED_hor)]))
            Flex_EDPmax_cur.index.names = ['genname','inter']
            Flex_EDPmin_cur = pd.DataFrame(.0, columns = ["Pmin"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(e,e+RTED_hor)]))
            Flex_EDPmin_cur.index.names = ['genname','inter']
                    
            for g in Supply_List["FLEX_SET"]:
                for j in range(e,e+RTED_hor):
                    Flex_EDPmin_cur.loc[(g,j),'Pmin'] = Flex_EDPmin.loc[(g,j),'Pmin']
                    Flex_EDPmax_cur.loc[(g,j),'Pmax'] = Flex_EDPmax.loc[(g,j),'Pmax']
            
            RTEDTime1 = time.process_time()
            RTEDdatprev = RTED_create_dat(RTED_DAT_fp, e, inter_num, setting_input, RTED_res, RTED_hor, bus_input, gen_input, ess_input, line_input,                                      PTDF_input, reserve_input, Load_TS["RTED_Load"], Load_TS["RTED_Load_raw"], Supply_TS["RTED_G23"],                                      Supply_TS["RTED_E1"], Supply_List, Inflex_EDPmin_cur, Inflex_EDPmax_cur, Flex_EDPmin_cur, Flex_EDPmax_cur,                                      ESS_RTED_ch_cur, ESS_RTED_dis_cur, ESS_RTED_SOC_LOSS_cur, SOC_initial,                                      gen_initialPmax, gen_initialPmin, gen_initialMW, RTED_ess_InitPow, Reserve_TS)
        
            EDins = EDmdl.create_instance(RTED_DAT_fp + str(e) + '.dat')
            EDins.dual = pe.Suffix(direction = pe.Suffix.IMPORT) # To include the duals if any

            # add load change from OpenDss 
            ## add OpenDss simulation
            # sovle distribution PF to obtain distribution power                             
            Austin.snapshot_run()
            Vmag = Austin.getVmag()
            Vpu = np.array([Vmag[i]/Vbase[i] for i in range(len(Vmag))])
            
            Vpu_ts[:, e-1: e] = Vpu.reshape((len(Vpu), 1))
                
            Feeder_head_power = []
            Feeder_head_power.append(Austin.dssCircuit.TotalPower()[0]/1000)
            Feeder_head_power = np.array(Feeder_head_power)                                            
            EDins.Load_Bus[2,e]=-float(Feeder_head_power)*10
            v1 = Austin.dssCircuit.AllNodeVmagPUByPhase(1) # store phase 1 nodes 
            v1_name = Austin.dssCircuit.AllNodeNamesByPhase(1)  # name that match the voltage   
            v1_all.append(v1) # get all snapshot in the list
            Feeder_total_power.append(Feeder_head_power)
         
            results = opt_ed.solve(EDins, tee=True, keepfiles=True)

            # get gen and load and update ACPF cases.
            # update the load
            kk=0
            for ldi in list([2,3,5,6,8,10,12]): # wenbo notes: update load, Sbase = 100 MVA
                pfss.PQ.p0.v[kk] = EDins.Load_Bus[ldi,e].value/100
                kk=kk+1
            # update the generation from geneators and PV   
            gkk=0    
            for gi in Supply_List["DPGEN_SET"]:
                if gi == 'SOUTHG1': # Slack bus generator
                    pfss.Slack.p0.v =  EDins.gen_power[gi,e].value/100
                else:
                    pfss.PV.p0.v[gkk] =  EDins.gen_power[gi,e].value/100
                    gkk=gkk+1
            # update the generation from ESS         
            for gi in Supply_List["DPESS_SET"]:
                pfss.PV.p0.v[gkk] =  EDins.ess_pow[gi,e].value/100
                gkk=gkk+1    
            
            pfss.PV.cache.refresh() # wenbo notes: necessary 1
            pfss.PQ.cache.refresh() # necessary 2
            # setup system
            pfss.setup()            # necessary 3
            # run power flow
            pfss.PFlow.run()        # run step
            #record bus 2 voltage magnitude
            v1_bus2 = pd.concat([v1_bus2, pd.DataFrame(np.reshape(pfss.Bus.v.v, (1,len(pfss.Bus.v.v))),columns=[list(range(19))])], axis = 0)
            
            #update the feeder head voltage
            if pfss.PFlow.converged == True:
                temp_v =  pfss.Bus.v.v[1]       
                Austin.updateSubVmag(temp_v) 
            else: 
                Austin.updateSubVmag(1) 
            
            
            RTEDTime2 = time.process_time()
            RTED_time += RTEDTime2 - RTEDTime1
            # RTED_solver_wall_time += float(results.Solver.Wall_time)
            
            RTED_gen_cost += EDins.gen_cost[e].value
            RTED_ess_cost += EDins.ess_cost[e].value
            RTED_reserve_cost += EDins.reserve_cost[e].value
            RTED_penalty_cost += EDins.penalty_cost[e].value

            RT_LMP = ExportLMP(EDins, EDins.dual, line_input, [list(EDins.INTER_SET)[0]], EDins.LOAD_BUS_SET, EDins.LINE_SET).Calculate_LMP()
            
            for k in Supply_List["GEN2_SET"]:
                Renew_curtail.loc[e,k] = (Supply_TS["RTED_G23"].loc[e,k] - EDins.gen_power[k,e].value) / 12
                  
            for ei in Supply_List["DPESS_SET"]:
                RTED_ess_dis.loc[e,ei] = EDins.ess_dis[ei,e].value
                RTED_ess_ch.loc[e,ei] = EDins.ess_ch[ei,e].value
                RTED_ess_pow.loc[e,ei] = EDins.ess_pow[ei,e].value
                RTED_socResult.loc[e,ei] = EDins.soc[ei,e].value
                RTED_relax.loc[e,ei] = EDins.soc_relax1[ei,e].value + EDins.soc_relax2[ei,e].value
                RTED_ess_pfr_up.loc[e,ei] = EDins.ess_pfr_pos[ei,e].value 
                RTED_ess_pfr_dn.loc[e,ei] = EDins.ess_pfr_neg[ei,e].value 
                RTED_ess_agc_up.loc[e,ei] = EDins.ess_agc_pos[ei,e].value
                RTED_ess_agc_dn.loc[e,ei] = EDins.ess_agc_neg[ei,e].value
                
            for ei in Supply_List["ESS1_SET"]:
                RTED_ess_ch.loc[e,ei] = -Supply_TS["RTED_E1"].loc[e,ei] if Supply_TS["RTED_E1"].loc[e,ei] <= 0 else 0
                RTED_ess_dis.loc[e,ei] = Supply_TS["RTED_E1"].loc[e,ei] if Supply_TS["RTED_E1"].loc[e,ei] > 0 else 0
                RTED_ess_pow.loc[e,ei] = Supply_TS["RTED_E1"].loc[e,ei]
                
            for gi in Supply_List["DPGEN_SET"]:
                RTED_PgenResult.loc[e,gi] = EDins.gen_power[gi,e].value
            for gi in Supply_List["GEN3_SET"]:
                RTED_PgenResult.loc[e,gi] = Supply_TS["RTED_G23"].loc[e,gi]
            
            for j in RTED_RegionDispatch.columns:
                for gi in Supply_List["DPGEN_SET"]:
                    if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                        RTED_RegionDispatch.loc[e,j] += EDins.gen_power[gi,e].value
                for gi in Supply_List["GEN3_SET"]:
                    if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                        RTED_RegionDispatch.loc[e,j] += Supply_TS["RTED_G23"].loc[e,gi]

                for ei in Supply_List["DPESS_SET"]:
                    if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                        RTED_RegionDispatch.loc[e,j] += EDins.ess_pow[ei,e].value
                for ei in Supply_List["ESS1_SET"]:
                    if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                        RTED_RegionDispatch.loc[e,j] += Supply_TS["RTED_E1"].loc[e,ei]
                    
                
            for gi in Supply_List["GEN1_SET"]:
                RTED_RU_slack.loc[e,gi] = EDins.gen_ramp_up_slack[gi,e].value
                RTED_RD_slack.loc[e,gi] = EDins.gen_ramp_dn_slack[gi,e].value
        
            for li in line_list:
                RTED_CU_slack.loc[e,li] = EDins.Ln_Cap_up_Slack[li,e].value
                RTED_CD_slack.loc[e,li] = EDins.Ln_Cap_dn_Slack[li,e].value
                if abs(line_input.loc[li,"Active"] - 1) <= 1e-4:
                    RTED_LineFlow.loc[e,li] = sum(EDins.Ln_PTDF[li, EDins.Gen_Bus[gi]] * EDins.gen_power[gi,e].value for gi in EDins.DPGEN_SET) +                                    sum(EDins.Ln_PTDF[li, EDins.ESS_Bus[ei]]* EDins.ess_pow[ei,e].value  for ei in EDins.DPESS_SET) - sum(EDins.Ln_PTDF[li, ldi] * (EDins.Load_Bus[ldi,e].value  - EDins.lol[ldi,e].value + EDins.sol[ldi,e].value) for ldi in EDins.LOAD_BUS_SET)
                      
            for bi in bus_list:
                RTED_LMP.loc[e,bi] = RT_LMP.loc[e,bi]
            
            RTED_lol.loc[e,'lol'] = sum(EDins.lol[ldi, e].value for ldi in EDins.LOAD_BUS_SET)
            RTED_sol.loc[e,'sol'] = sum(EDins.sol[ldi, e].value for ldi in EDins.LOAD_BUS_SET)
            
            RTED_pfrup_Insuf.loc[e] = EDins.sys_IR1_pos[e].value
            RTED_pfrdn_Insuf.loc[e] = EDins.sys_IR1_neg[e].value
            RTED_agcup_Insuf.loc[e] = EDins.sys_IR2_pos[e].value
            RTED_agcdn_Insuf.loc[e] = EDins.sys_IR2_neg[e].value
            
            RTED_Total_Load_new.loc[e] = sum(EDins.Load_Bus[ldi,e].value  for ldi in EDins.LOAD_BUS_SET)
            RTED_Gen_cost_interval.loc [e] = EDins.gen_cost[e].value            
            
                
            for gi in Supply_List["DPGEN_SET"]:
                RTED_pfrup_Result.loc[e,gi] = EDins.gen_pfr_pos[gi,e].value
                RTED_pfrdn_Result.loc[e,gi] = EDins.gen_pfr_neg[gi,e].value
                RTED_agcup_Result.loc[e,gi] = EDins.gen_agc_pos[gi,e].value
                RTED_agcdn_Result.loc[e,gi] = EDins.gen_agc_neg[gi,e].value
            
            os.makedirs(os.path.dirname(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str(e) + '.csv'), exist_ok=True)    
            with open(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str(e) + '.csv', 'w') as f:
                f.write('number,Pgen,PFR_up,PFR_dn,AGC_up,AGC_dn, SOC\n')
                for gi in Supply_List["DPGEN_SET"]:
                    f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[e,gi], RTED_pfrup_Result.loc[e,gi],                                                     RTED_pfrdn_Result.loc[e,gi], RTED_agcup_Result.loc[e,gi],                                                     RTED_agcdn_Result.loc[e,gi], np.nan))
                for gi in Supply_List["GEN3_SET"]:
                    f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[e,gi], np.nan, np.nan, np.nan, np.nan, np.nan))
                for ei in Supply_List["DPESS_SET"]:
                    f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[e,ei], RTED_ess_pfr_up.loc[e,ei],                                                     RTED_ess_pfr_dn.loc[e,ei], RTED_ess_agc_up.loc[e,ei],                                                     RTED_ess_agc_dn.loc[e,ei], RTED_socResult.loc[e,ei]))  
                                
                # Should we give the SOC value of the non-dispatchable ESSs to Dynamic Team?
            
                for ei in Supply_List["ESS1_SET"]:
                    f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[e,ei], np.nan, np.nan, np.nan, np.nan, np.nan)) 
            
        UC_prev = pd.DataFrame(.0, columns = ["I"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(i+1,i+4)]))
        shutdow_prev = pd.DataFrame(.0, columns = ["shut"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(i+1,i+4)]))
        for gi in Supply_List["FLEX_SET"]:
            for j in range(3):
                UC_prev.loc[(gi,i+j+1),'I'] = RTUCins.gen_onoff[gi,i+j+1].value
                shutdow_prev.loc[(gi,i+j+1),'shut'] = RTUCins.gen_shutdow[gi,i+j+1].value
            
        Flex_EDPmax_prev = Flex_EDPmax
        Flex_EDPmin_prev = Flex_EDPmin
        
        


# In[ ]:





# In[13]:


for i in range(1,24):
    
    if i != 1:         
            
        # ----------------- FIRST RTED MODULE ------------- #
        
        # Create initial Pmax and Pmin to determine whether is in trajectory
                
        gen_initialMW = pd.DataFrame(.0, columns = ['IntPow'], index = Supply_List["GEN1_SET"])
        gen_initialMW.index.names = ['genname']
        gen_initialPmax = pd.DataFrame(.0, columns = ['Pmax'], index = Supply_List["GEN1_SET"])
        gen_initialPmax.index.names = ['genname']
        gen_initialPmin = pd.DataFrame(.0, columns = ['Pmin'], index = Supply_List["GEN1_SET"])
        gen_initialPmin.index.names = ['genname']
        RTED_ess_InitPow = pd.DataFrame(.0, columns = ['Pow0'], index = Supply_List["DPESS_SET"])
        RTED_ess_InitPow.index.names = ['essname']
        SOC_initial = pd.DataFrame(.0, columns = ['soc'], index = Supply_List["DPESS_SET"])
        SOC_initial.index.names = ['essname']
        
        # if close_loop_flag == 1:
            # Dynamic Chimes in

        # First ED in first hour has no trajectory
        for gi in Supply_List["DPGEN_SET"]:
            gen_initialMW.loc[gi,'IntPow'] = EDins.gen_power[gi,(i-1)*inter_num].value
            if gi in Supply_List["INFLEX_SET"]:
                gen_initialPmax.loc[gi,'Pmax'] = Inflex_EDPmax_cur.loc[gi,'Pmax'][(i-1)*inter_num]
                gen_initialPmin.loc[gi,'Pmin'] = Inflex_EDPmin_cur.loc[gi,'Pmin'][(i-1)*inter_num]
            if gi in Supply_List["FLEX_SET"]:
                gen_initialPmax.loc[gi,'Pmax'] = Flex_EDPmax_cur.loc[gi,'Pmax'][(i-1)*inter_num]
                gen_initialPmin.loc[gi,'Pmin'] = Flex_EDPmin_cur.loc[gi,'Pmin'][(i-1)*inter_num]

        for ei in Supply_List["DPESS_SET"]:
            SOC_initial.loc[ei,'soc'] = EDins.soc[ei,(i-1)*inter_num].value
            RTED_ess_InitPow.loc[ei,'Pow0'] = EDins.ess_pow[ei,(i-1)*inter_num].value

        Inflex_EDPmin_cur = pd.DataFrame(Inflex_EDPmin.loc[(Supply_List["INFLEX_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'Pmin'])
        Inflex_EDPmax_cur = pd.DataFrame(Inflex_EDPmax.loc[(Supply_List["INFLEX_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'Pmax'])
        Flex_EDPmax_cur = pd.DataFrame(.0, columns = ["Pmax"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)]))
        Flex_EDPmax_cur.index.names = ['genname','inter']
        Flex_EDPmin_cur = pd.DataFrame(.0, columns = ["Pmin"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)]))
        Flex_EDPmin_cur.index.names = ['genname','inter']
        
        ESS_RTED_ch_cur = pd.DataFrame(ESS_RTED_Ch.loc[(Supply_List["DPESS_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'ch'])
        ESS_RTED_dis_cur = pd.DataFrame(ESS_RTED_Dis.loc[(Supply_List["DPESS_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'dis'])
        ESS_RTED_SOC_LOSS_cur = pd.DataFrame(ESS_RTED_SOC_LOSS.loc[(Supply_List["DPESS_SET"],range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor)),'loss'])

        for g in Supply_List["FLEX_SET"]:
            for j in range((i-1)*inter_num+1,(i-1)*inter_num+1+RTED_hor):
                Flex_EDPmin_cur.loc[(g,j),'Pmin'] = Flex_EDPmin_prev.loc[(g,j),'Pmin']
                Flex_EDPmax_cur.loc[(g,j),'Pmax'] = Flex_EDPmax_prev.loc[(g,j),'Pmax']                 
                
                
        # Here starts the first ED in the hour
         
        RTEDTime1 = time.process_time()
        RTEDdatprev = RTED_create_dat(RTED_DAT_fp, (i-1)*inter_num+1, inter_num, setting_input, RTED_res, RTED_hor, bus_input, gen_input, ess_input, line_input,                                      PTDF_input, reserve_input, Load_TS["RTED_Load"], Load_TS["RTED_Load_raw"], Supply_TS["RTED_G23"],                                      Supply_TS["RTED_E1"], Supply_List, Inflex_EDPmin_cur, Inflex_EDPmax_cur, Flex_EDPmin_cur, Flex_EDPmax_cur,                                      ESS_RTED_ch_cur, ESS_RTED_dis_cur, ESS_RTED_SOC_LOSS_cur, SOC_initial,                                      gen_initialPmax, gen_initialPmin, gen_initialMW, RTED_ess_InitPow, Reserve_TS)
        
        EDins = EDmdl.create_instance(RTED_DAT_fp + str((i-1)*inter_num+1) + '.dat')
        EDins.dual = pe.Suffix(direction = pe.Suffix.IMPORT) # To include the duals if any

        ## add load change from OpenDss 
        ## add OpenDss simulation
        # add load change from OpenDss 
            ## add OpenDss simulation
            # sovle distribution PF to obtain distribution power  

        if i == 12:
            SLG_fault.create('F1', 'p5udt6490-p5udt747xx', 3)
            # Switch_off.create('l(r:p5udt6490-p5udt747)', 2, 3)
            # Load_perturb.create_single('load_p5ulv58', 1.5)
            # Load_perturb.create_system([1.5] * len(Austin.dssLoad.AllNames()))
                           
        Austin.snapshot_run()
        Vmag = Austin.getVmag()
        Vpu = np.array([Vmag[i]/Vbase[i] for i in range(len(Vmag))])
            
        Vpu_ts[:, (i-1)*inter_num: (i-1)*inter_num+1] = Vpu.reshape((len(Vpu), 1))
                
        Feeder_head_power = []
        Feeder_head_power.append(Austin.dssCircuit.TotalPower()[0]/1000)
        Feeder_head_power = np.array(Feeder_head_power)
                                          
        EDins.Load_Bus[2,(i-1)*inter_num+1]=-float(Feeder_head_power)*10
        v1 = Austin.dssCircuit.AllNodeVmagPUByPhase(1) # store phase 1 nodes 
        v1_name = Austin.dssCircuit.AllNodeNamesByPhase(1)  # name that match the voltage   
        v1_all.append(v1) # get all snapshot in the list
        Feeder_total_power.append(Feeder_head_power)
         
        results = opt_ed.solve(EDins, tee=True, keepfiles=True)
                           
        if i == 12:
            SLG_fault.clean('F1')
            # Switch_off.clean('l(r:p5udt6490-p5udt747)', 2, 3)
            # Load_perturb.clean_single('load_p5ulv58', 1.5)
            # Load_perturb.clean_system([1.5] * len(Austin.dssLoad.AllNames()))
        
        # get gen and load and update ACPF cases.
        # update the load
        kk=0
        for ldi in list([2,3,5,6,8,10,12]):
            pfss.PQ.p0.v[kk] = EDins.Load_Bus[ldi,(i-1)*inter_num+1].value/100
            kk=kk+1
        # update the generation from geneators and PV   
        gkk=0    
        for gi in Supply_List["DPGEN_SET"]: 
            if gi == 'SOUTHG1': # Slack bus generator
                pfss.Slack.p0.v =  EDins.gen_power[gi,(i-1)*inter_num+1].value/100
            else:
                pfss.PV.p0.v[gkk] =  EDins.gen_power[gi,(i-1)*inter_num+1].value/100
                gkk=gkk+1
      # update the generation from ESS         
        for gi in Supply_List["DPESS_SET"]:              
            pfss.PV.p0.v[gkk] =  EDins.ess_pow[gi,(i-1)*inter_num+1].value/100
            gkk=gkk+1   
            
           
        pfss.PV.cache.refresh()
        pfss.PQ.cache.refresh()
        # setup system
        pfss.setup()
        # run power flow
        pfss.PFlow.run()    
        
        
        if pfss.PFlow.converged == True and min(pfss.Bus.v.v)>0.90:
        #record bus 2 voltage magnitude
            v1_bus2 = pd.concat([v1_bus2, pd.DataFrame(np.reshape(pfss.Bus.v.v, (1,len(pfss.Bus.v.v))),columns=[list(range(19))])], axis = 0)
        else:
            pfss.Shunt.b.v = np.array([2.5,6,6,3,3]) 
            # setup system
            pfss.setup()
            # run power flow
            pfss.PFlow.run() 
            v1_bus2 = pd.concat([v1_bus2, pd.DataFrame(np.reshape(pfss.Bus.v.v, (1,len(pfss.Bus.v.v))),columns=[list(range(19))])], axis = 0)
            pfss.Shunt.b.v = switched_shut0 
            
            
        #update the feeder head voltage
        if pfss.PFlow.converged == True:
            temp_v =  pfss.Bus.v.v[1]       
            Austin.updateSubVmag(temp_v) 
        else: 
            Austin.updateSubVmag(1)  
                     
        RTEDTime2 = time.process_time()
        RTED_time += RTEDTime2 - RTEDTime1
        # RTED_solver_wall_time += float(results.Solver.Wall_time)

        # ---- Post-solution data retrieval
        
        RTED_gen_cost += EDins.gen_cost[(i-1)*inter_num+1].value
        RTED_ess_cost += EDins.ess_cost[(i-1)*inter_num+1].value
        RTED_reserve_cost += EDins.reserve_cost[(i-1)*inter_num+1].value
        RTED_penalty_cost += EDins.penalty_cost[(i-1)*inter_num+1].value
        
        RT_LMP = ExportLMP(EDins, EDins.dual, line_input, [list(EDins.INTER_SET)[0]], EDins.LOAD_BUS_SET, EDins.LINE_SET).Calculate_LMP()
        
        for k in Supply_List["GEN2_SET"]:
            Renew_curtail.loc[(i-1)*inter_num+1,k] = (Supply_TS["RTED_G23"].loc[(i-1)*inter_num+1,k] - EDins.gen_power[k,(i-1)*inter_num+1].value) / inter_num

        e = (i-1)*inter_num+1
        for ei in Supply_List["DPESS_SET"]:
            RTED_ess_dis.loc[e,ei] = EDins.ess_dis[ei,e].value
            RTED_ess_ch.loc[e,ei] = EDins.ess_ch[ei,e].value
            RTED_ess_pow.loc[e,ei] = EDins.ess_pow[ei,e].value
            RTED_socResult.loc[e,ei] = EDins.soc[ei,e].value
            RTED_relax.loc[e,ei] = EDins.soc_relax1[ei,e].value + EDins.soc_relax2[ei,e].value
            RTED_ess_pfr_up.loc[e,ei] = EDins.ess_pfr_pos[ei,e].value 
            RTED_ess_pfr_dn.loc[e,ei] = EDins.ess_pfr_neg[ei,e].value 
            RTED_ess_agc_up.loc[e,ei] = EDins.ess_agc_pos[ei,e].value
            RTED_ess_agc_dn.loc[e,ei] = EDins.ess_agc_neg[ei,e].value
                
        for ei in Supply_List["ESS1_SET"]:
            RTED_ess_ch.loc[e,ei] = -Supply_TS["RTED_E1"].loc[e,ei] if Supply_TS["RTED_E1"].loc[e,ei] <= 0 else 0
            RTED_ess_dis.loc[e,ei] = Supply_TS["RTED_E1"].loc[e,ei] if Supply_TS["RTED_E1"].loc[e,ei] > 0 else 0
            RTED_ess_pow.loc[e,ei] = Supply_TS["RTED_E1"].loc[e,ei]
                
        for gi in Supply_List["DPGEN_SET"]:
            RTED_PgenResult.loc[e,gi] = EDins.gen_power[gi,e].value
        for gi in Supply_List["GEN3_SET"]:
            RTED_PgenResult.loc[e,gi] = Supply_TS["RTED_G23"].loc[e,gi]
            
        for j in RTED_RegionDispatch.columns:
            for gi in Supply_List["DPGEN_SET"]:
                if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                    RTED_RegionDispatch.loc[e,j] += EDins.gen_power[gi,e].value
            for gi in Supply_List["GEN3_SET"]:
                if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                    RTED_RegionDispatch.loc[e,j] += Supply_TS["RTED_G23"].loc[e,gi]

            for ei in Supply_List["DPESS_SET"]:
                if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                    RTED_RegionDispatch.loc[e,j] += EDins.ess_pow[ei,e].value
            for ei in Supply_List["ESS1_SET"]:
                if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                    RTED_RegionDispatch.loc[e,j] += Supply_TS["RTED_E1"].loc[e,ei]
            
        for gi in Supply_List["GEN1_SET"]:
            RTED_RU_slack.loc[(i-1)*inter_num+1,gi] = EDins.gen_ramp_up_slack[gi,(i-1)*inter_num+1].value
            RTED_RD_slack.loc[(i-1)*inter_num+1,gi] = EDins.gen_ramp_dn_slack[gi,(i-1)*inter_num+1].value
        
        for li in line_list:
            RTED_CU_slack.loc[(i-1)*inter_num+1,li] = EDins.Ln_Cap_up_Slack[li,(i-1)*inter_num+1].value
            RTED_CD_slack.loc[(i-1)*inter_num+1,li] = EDins.Ln_Cap_dn_Slack[li,(i-1)*inter_num+1].value
            if abs(line_input.loc[li,"Active"] - 1) <= 1e-4:
                e = (i-1)*inter_num+1
                RTED_LineFlow.loc[e,li] = sum(EDins.Ln_PTDF[li, EDins.Gen_Bus[gi]] * EDins.gen_power[gi,e].value for gi in EDins.DPGEN_SET) +                    sum(EDins.Ln_PTDF[li, EDins.ESS_Bus[ei]]* EDins.ess_pow[ei,e].value                     for ei in EDins.DPESS_SET) - sum(EDins.Ln_PTDF[li, ldi] * (EDins.Load_Bus[ldi,e].value  - EDins.lol[ldi,e].value + EDins.sol[ldi,e].value) for ldi in EDins.LOAD_BUS_SET)

        RTED_lol.loc[e,'lol'] = sum(EDins.lol[ldi, e].value for ldi in EDins.LOAD_BUS_SET)
        RTED_sol.loc[e,'sol'] = sum(EDins.sol[ldi, e].value for ldi in EDins.LOAD_BUS_SET)
        
        RTED_pfrup_Insuf.loc[(i-1)*inter_num+1] = EDins.sys_IR1_pos[(i-1)*inter_num+1].value
        RTED_pfrdn_Insuf.loc[(i-1)*inter_num+1] = EDins.sys_IR1_neg[(i-1)*inter_num+1].value
        RTED_agcup_Insuf.loc[(i-1)*inter_num+1] = EDins.sys_IR2_pos[(i-1)*inter_num+1].value
        RTED_agcdn_Insuf.loc[(i-1)*inter_num+1] = EDins.sys_IR2_neg[(i-1)*inter_num+1].value

        RTED_Total_Load_new.loc[(i-1)*inter_num+1] = sum(EDins.Load_Bus[ldi,(i-1)*inter_num+1].value  for ldi in EDins.LOAD_BUS_SET)
        RTED_Gen_cost_interval.loc [(i-1)*inter_num+1] = EDins.gen_cost[(i-1)*inter_num+1].value
            
        for gi in Supply_List["DPGEN_SET"]:
            RTED_pfrup_Result.loc[(i-1)*inter_num+1,gi] = EDins.gen_pfr_pos[gi,(i-1)*inter_num+1].value
            RTED_pfrdn_Result.loc[(i-1)*inter_num+1,gi] = EDins.gen_pfr_neg[gi,(i-1)*inter_num+1].value
            RTED_agcup_Result.loc[(i-1)*inter_num+1,gi] = EDins.gen_agc_pos[gi,(i-1)*inter_num+1].value
            RTED_agcdn_Result.loc[(i-1)*inter_num+1,gi] = EDins.gen_agc_neg[gi,(i-1)*inter_num+1].value
            
        for bi in bus_list:
            RTED_LMP.loc[(i-1)*inter_num+1,bi] = RT_LMP.loc[(i-1)*inter_num+1,bi]
             
        os.makedirs(os.path.dirname(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str((i-1)*inter_num+1) + '.csv'), exist_ok=True)    
        with open(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str((i-1)*inter_num+1) + '.csv', 'w') as f:
            f.write('number,Pgen,PFR_up,PFR_dn,AGC_up,AGC_dn, SOC\n')
            for gi in Supply_List["DPGEN_SET"]:
                f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[(i-1)*inter_num+1,gi], RTED_pfrup_Result.loc[(i-1)*inter_num+1,gi],                                                     RTED_pfrdn_Result.loc[(i-1)*inter_num+1,gi], RTED_agcup_Result.loc[(i-1)*inter_num+1,gi],                                                     RTED_agcdn_Result.loc[(i-1)*inter_num+1,gi], np.nan))
            for gi in Supply_List["GEN3_SET"]:
                f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[(i-1)*inter_num+1,gi], np.nan, np.nan, np.nan, np.nan, np.nan))      
            for ei in Supply_List["DPESS_SET"]:
                f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[(i-1)*inter_num+1,ei], RTED_ess_pfr_up.loc[(i-1)*inter_num+1,ei],                                                     RTED_ess_pfr_dn.loc[(i-1)*inter_num+1,ei], RTED_ess_agc_up.loc[(i-1)*inter_num+1,ei],                                                     RTED_ess_agc_dn.loc[(i-1)*inter_num+1,ei], RTED_socResult.loc[(i-1)*inter_num+1,ei])) 
            for ei in Supply_List["ESS1_SET"]:
                f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[(i-1)*inter_num+1,ei], np.nan, np.nan, np.nan, np.nan, np.nan))
        
        # ------------------ RTUC MODULE ------------------ #
           
        Flex_UC_initial_Stat = pd.DataFrame(.0, columns = ['IntStat'], index = Supply_List["FLEX_SET"])
        Flex_UC_initial_Stat.index.names = ['genname']
        Flex_UC_initial_Hour = pd.DataFrame(.0, columns = ['IntHour'], index = Supply_List["FLEX_SET"])
        Flex_UC_initial_Hour.index.names = ['genname']
        InitialGenMax = pd.DataFrame(.0, columns = ['Pmax'], index = Supply_List["INFLEX_SET"])
        InitialGenMax.index.names = ['genname']
        InitialGenMin = pd.DataFrame(.0, columns = ['Pmin'], index = Supply_List["INFLEX_SET"])
        InitialGenMin.index.names = ['genname']
        
        Inflex_UCPmin_cur = pd.DataFrame(Inflex_UCPmin.loc[(Supply_List["INFLEX_SET"],range(i+1,i+RTUC_hor+1)),'Pmin'])
        Inflex_UCPmax_cur = pd.DataFrame(Inflex_UCPmax.loc[(Supply_List["INFLEX_SET"],range(i+1,i+RTUC_hor+1)),'Pmax'])

        ESS_RTUC_ch_cur = pd.DataFrame(ESS_RTUC_Ch.loc[(Supply_List["DPESS_SET"],range(i+1,i+RTUC_hor+1)),'ch'])
        ESS_RTUC_dis_cur = pd.DataFrame(ESS_RTUC_Dis.loc[(Supply_List["DPESS_SET"],range(i+1,i+RTUC_hor+1)),'dis'])
        RTUC_SOC_init = pd.DataFrame(.0, columns = ['IntSOC'], index = Supply_List["DPESS_SET"])
        RTUC_SOC_init.index.names = ['essname']
        RTUC_ess_InitPow = pd.DataFrame(.0, columns = ['ESS_Pow0'], index = Supply_List["DPESS_SET"])
        RTUC_ess_InitPow.index.names = ['essname']
        for ei in Supply_List["DPESS_SET"]:
            RTUC_SOC_init.loc[ei,'IntSOC'] = EDins.soc[ei,i*inter_num].value
            RTUC_ess_InitPow.loc[ei,'ESS_Pow0'] = EDins.ess_pow[ei,i*inter_num].value

        RTUC_initialMW = pd.DataFrame(.0, columns = ['IntPow'], index = Supply_List["DPGEN_SET"])
        RTUC_initialMW.index.names = ['genname']
        for gi in Supply_List["DPGEN_SET"]:
            RTUC_initialMW.loc[gi,'IntPow'] = EDins.gen_power[gi,i*inter_num].value           
            
        for gi in Supply_List["FLEX_SET"]:
            if RTUCins.gen_startup[gi,i].value >= 1-1e-3:
                Flex_UC_initial_Stat.loc[gi,'IntStat'] = 1
                Flex_UC_initial_Hour.loc[gi,'IntHour'] = 1
            elif RTUCins.gen_shutdow[gi,i].value >= 1-1e-3:
                Flex_UC_initial_Stat.loc[gi,'IntStat'] = 0
                Flex_UC_initial_Hour.loc[gi,'IntHour'] = 1
            else:
                Flex_UC_initial_Stat.loc[gi,'IntStat'] = Flex_UC_initial_Stat_prev.loc[gi,'IntStat']
                Flex_UC_initial_Hour.loc[gi,'IntHour'] = Flex_UC_initial_Hour_prev.loc[gi,'IntHour'] + 1 
            
        for gi in Supply_List["INFLEX_SET"]:
            InitialGenMax.loc[gi, 'Pmax'] = Inflex_UCPmax_prev.loc[(gi,i),'Pmax']
            InitialGenMin.loc[gi, 'Pmin'] = Inflex_UCPmin_prev.loc[(gi,i),'Pmin']         
            
        RTUCTime1 = time.process_time()
        RTUCdat = RTUC_create_dat(RTUC_DAT_fp, i, setting_input, RTUC_res, RTUC_hor, bus_input, gen_input, ess_input, line_input,                                   PTDF_input, reserve_input, Load_TS["RTUC_Load"], Load_TS["RTUC_Load_raw"], Supply_TS["RTUC_G23"],                                   Supply_TS["RTUC_E1"], Supply_List, Inflex_UCPmin_cur, Inflex_UCPmax_cur, ESS_RTUC_ch_cur, ESS_RTUC_dis_cur,                                   RTUC_SOC_init, InitialGenMax, InitialGenMin, Flex_UC_initial_Stat, Flex_UC_initial_Hour, RTUC_initialMW, RTUC_ess_InitPow, Reserve_TS)       
        
        RTUCins = RTUCmdl.create_instance(RTUC_DAT_fp + 'RTUC' + str(i) + '.dat')
        results = opt_uc.solve(RTUCins, tee=True, keepfiles=True)
        RTUCTime2 = time.process_time()
        RTUC_time += RTUCTime2 - RTUCTime1
        
        Flex_UC_initial_Stat_prev = Flex_UC_initial_Stat
        Flex_UC_initial_Hour_prev = Flex_UC_initial_Hour
        Inflex_UCPmin_prev = Inflex_UCPmin_cur
        Inflex_UCPmax_prev = Inflex_UCPmax_cur
        
        ss = 2 if i != 23 else 4
            
        for ii in range(1,ss):
            RTUC_lol.loc[i+ii,'lol'] = sum(RTUCins.lol[ldi, i+ii].value for ldi in RTUCins.LOAD_BUS_SET)
            RTUC_sol.loc[i+ii,'sol'] = sum(RTUCins.sol[ldi, i+ii].value for ldi in RTUCins.LOAD_BUS_SET)
            
            for gi in Supply_List["DPGEN_SET"]:
                RTUC_PgenResult.loc[i+ii,gi] = RTUCins.gen_power[gi,i+ii].value
                
            for ei in Supply_List["DPESS_SET"]:
                RTUC_ess_dis.loc[i+ii,ei] = RTUCins.ess_dis[ei,i+ii].value
                RTUC_ess_ch.loc[i+ii,ei] = RTUCins.ess_ch[ei,i+ii].value
                
            for ei in Supply_List["ESS1_SET"]:
                RTUC_ess_dis.loc[i+ii,ei] = Supply_TS["RTUC_E1"].loc[i+ii,ei] if Supply_TS["RTUC_E1"].loc[i+ii,ei] > 0 else 0
                RTUC_ess_ch.loc[i+ii,ei] = -Supply_TS["RTUC_E1"].loc[i+ii,ei] if Supply_TS["RTUC_E1"].loc[i+ii,ei] <= 0 else 0
            
            for gi in Supply_List["GEN3_SET"]:
                RTUC_PgenResult.loc[i+ii,gi] = Supply_TS["RTUC_G23"].loc[i+ii,gi]
                
            for gi in Supply_List["GEN1_SET"]:
                RTUC_RU_slack.loc[i+ii,gi] = RTUCins.gen_ramp_up_slack[gi,i+ii].value
                RTUC_RD_slack.loc[i+ii,gi] = RTUCins.gen_ramp_dn_slack[gi,i+ii].value
                
            for li in line_list:
                RTUC_CU_slack.loc[i+ii,li] = RTUCins.Ln_Cap_up_Slack[li,i+ii].value
                RTUC_CD_slack.loc[i+ii,li] = RTUCins.Ln_Cap_dn_Slack[li,i+ii].value
                if abs(line_input.loc[li,"Active"] - 1) <= 1e-4:
                    RTUC_LineFlow.loc[i+ii,li] = sum(RTUCins.Ln_PTDF[li, RTUCins.Gen_Bus[gi]] * RTUCins.gen_power[gi,i+ii].value for gi in RTUCins.DPGEN_SET) +                            sum(RTUCins.Ln_PTDF[li, RTUCins.ESS_Bus[ei]]* RTUCins.ess_pow[ei,i+ii].value                             for ei in RTUCins.DPESS_SET) - sum(RTUCins.Ln_PTDF[li, ldi] * (RTUCins.Load_Bus[ldi,i+ii]                             - RTUCins.lol[ldi,i+ii].value + RTUCins.sol[ldi,i+ii].value) for ldi in RTUCins.LOAD_BUS_SET)
            
            for gi in Supply_List["DPGEN_SET"]:
                RTUC_pfrup_Result.loc[i+ii,gi] = RTUCins.gen_pfr_pos[gi,i+ii].value
                RTUC_pfrdn_Result.loc[i+ii,gi] = RTUCins.gen_pfr_neg[gi,i+ii].value
                RTUC_agcup_Result.loc[i+ii,gi] = RTUCins.gen_agc_pos[gi,i+ii].value
                RTUC_agcdn_Result.loc[i+ii,gi] = RTUCins.gen_agc_neg[gi,i+ii].value
            
            for ei in Supply_List["DPESS_SET"]:
                RTUC_socResult.loc[i+ii,ei] = RTUCins.soc[ei,i+ii].value
                RTUC_relax.loc[i+ii,ei] = RTUCins.soc_relax1[ei,i+ii].value + RTUCins.soc_relax2[ei,i+ii].value
                RTUC_ess_pfr_up.loc[i+ii,ei] = RTUCins.ess_pfr_pos[ei,i+ii].value 
                RTUC_ess_pfr_dn.loc[i+ii,ei] = RTUCins.ess_pfr_neg[ei,i+ii].value 
                RTUC_ess_agc_up.loc[i+ii,ei] = RTUCins.ess_agc_pos[ei,i+ii].value
                RTUC_ess_agc_dn.loc[i+ii,ei] = RTUCins.ess_agc_neg[ei,i+ii].value
            
         # For trajectory modeling, there are still some hard code. 
        # They are related to the time resolution/horizon of the RTUC/RTED.
        # They are hard to remove and we will investigate them later.
        
        Flex_EDPmax = pd.DataFrame(.0,                       columns = ["Pmax"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range((i-1)*inter_num+2,(i-1)*inter_num+(RTUC_hor+1)*inter_num)]))
        Flex_EDPmin = pd.DataFrame(.0,                       columns = ["Pmin"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range((i-1)*inter_num+2,(i-1)*inter_num+(RTUC_hor+1)*inter_num)]))
                            
        for gi in Supply_List["FLEX_SET"]:
            for ii in range((i-1)*inter_num+2,(i-1)*inter_num+(RTUC_hor+1)*inter_num):
                if ii <= i*inter_num:
                    if abs(shutdow_prev.loc[(gi,i),'shut'] - 1) <= 1e-3:
                        Flex_EDPmax.loc[(gi,ii),'Pmax'] = Flex_EDPmax_prev.loc[(gi,ii),'Pmax']
                        Flex_EDPmin.loc[(gi,ii),'Pmin'] = Flex_EDPmin_prev.loc[(gi,ii),'Pmin']
                    else:
                        Flex_EDPmax.loc[(gi,ii),'Pmax'] = UC_prev.loc[(gi,i),'I'] * gen_input.loc[gi,'Pmax']
                        Flex_EDPmin.loc[(gi,ii),'Pmin'] = UC_prev.loc[(gi,i),'I'] * gen_input.loc[gi,'Pmin']
                elif ii > i*inter_num and ii <= (i+1)*inter_num:
                    Flex_EDPmax.loc[(gi,ii),'Pmax'] = RTUCins.gen_onoff[gi,i+1].value * gen_input.loc[gi,'Pmax']
                    Flex_EDPmin.loc[(gi,ii),'Pmin'] = RTUCins.gen_onoff[gi,i+1].value * gen_input.loc[gi,'Pmin']        
                elif ii > (i+1)*inter_num and ii <= (i+2)*inter_num:
                    Flex_EDPmax.loc[(gi,ii),'Pmax'] = RTUCins.gen_onoff[gi,i+2].value * gen_input.loc[gi,'Pmax']
                    Flex_EDPmin.loc[(gi,ii),'Pmin'] = RTUCins.gen_onoff[gi,i+2].value * gen_input.loc[gi,'Pmin']   
                else:
                    Flex_EDPmax.loc[(gi,ii),'Pmax'] = RTUCins.gen_onoff[gi,i+3].value * gen_input.loc[gi,'Pmax']
                    Flex_EDPmin.loc[(gi,ii),'Pmin'] = RTUCins.gen_onoff[gi,i+3].value * gen_input.loc[gi,'Pmin'] 

        for gi in Supply_List["FLEX_SET"]:
            intereq_on = gen_input.loc[gi,'SUTime']/RTED_res
            intereq_off = gen_input.loc[gi,'SDTime']/RTED_res
            for s in range(RTUC_hor):
                if abs(RTUCins.gen_startup[gi,i+1+s].value - 1) <= 1e-2:
                    for n in range(1,inter_num+1):
                        if intereq_on - n > -1e-2:
                            Flex_EDPmax.loc[(gi,(i+s)*inter_num-n),'Pmax'] = (intereq_on - n) / intereq_on * gen_input.loc[gi,'Pmax']
                            Flex_EDPmin.loc[(gi,(i+s)*inter_num-n),'Pmin'] = (intereq_on - n) / intereq_on * gen_input.loc[gi,'Pmin']
                        else:
                            Flex_EDPmax.loc[(gi,(i+s)*inter_num-n),'Pmax'] = 0
                            Flex_EDPmin.loc[(gi,(i+s)*inter_num-n),'Pmin'] = 0
                    for ss in range((i+s)*inter_num, (i+RTUC_hor)*inter_num):
                        Flex_EDPmax.loc[(gi,ss),'Pmax'] = gen_input.loc[gi,'Pmax']
                        Flex_EDPmin.loc[(gi,ss),'Pmin'] = gen_input.loc[gi,'Pmin']  

                if abs(RTUCins.gen_shutdow[gi,i+1+s].value - 1) <= 1e-2:
                    for n in range(1,inter_num+1):
                        if intereq_off - n > -1e-2:
                            Flex_EDPmax.loc[(gi,(i+s)*inter_num+n),'Pmax'] = gen_input.loc[gi,'Pmax'] * (intereq_off-n) / intereq_off
                            Flex_EDPmin.loc[(gi,(i+s)*inter_num+n),'Pmin'] = gen_input.loc[gi,'Pmin'] * (intereq_off-n) / intereq_off   
                        else:
                            Flex_EDPmax.loc[(gi,(i+s)*inter_num+n),'Pmax'] = 0
                            Flex_EDPmin.loc[(gi,(i+s)*inter_num+n),'Pmin'] = 0
                    for ss in range((i+s+1)*inter_num, (i+RTUC_hor)*inter_num):
                        Flex_EDPmax.loc[(gi,ss),'Pmax'] = 0
                        Flex_EDPmin.loc[(gi,ss),'Pmin'] = 0    
            
        # ------------- REMAINING RTED MODULE -------------- #
        
        for e in range(2+(i-1)*inter_num,inter_num+1+(i-1)*inter_num):        
        
            gen_initialMW = pd.DataFrame(.0, columns = ['IntPow'], index = Supply_List["GEN1_SET"])
            gen_initialMW.index.names = ['genname']
            gen_initialPmax = pd.DataFrame(.0, columns = ['Pmax'], index = Supply_List["GEN1_SET"])
            gen_initialPmax.index.names = ['genname']
            gen_initialPmin = pd.DataFrame(.0, columns = ['Pmin'], index = Supply_List["GEN1_SET"])
            gen_initialPmin.index.names = ['genname']
            RTED_ess_InitPow = pd.DataFrame(.0, columns = ['Pow0'], index = Supply_List["DPESS_SET"])
            RTED_ess_InitPow.index.names = ['essname']
            SOC_initial = pd.DataFrame(.0, columns = ['soc'], index = Supply_List["DPESS_SET"])
            SOC_initial.index.names = ['essname']                                  
                
            for gi in Supply_List["DPGEN_SET"]:
                gen_initialMW.loc[gi,'IntPow'] = EDins.gen_power[gi,e-1].value
                if gi in Supply_List["INFLEX_SET"]:
                    gen_initialPmax.loc[gi,'Pmax'] = Inflex_EDPmax_cur.loc[gi,'Pmax'][e-1]
                    gen_initialPmin.loc[gi,'Pmin'] = Inflex_EDPmin_cur.loc[gi,'Pmin'][e-1]
                if gi in Supply_List["FLEX_SET"]:
                    gen_initialPmax.loc[gi,'Pmax'] = Flex_EDPmax_cur.loc[gi,'Pmax'][e-1]
                    gen_initialPmin.loc[gi,'Pmin'] = Flex_EDPmin_cur.loc[gi,'Pmin'][e-1]
            
            Inflex_EDPmin_cur = pd.DataFrame(Inflex_EDPmin.loc[(Supply_List["INFLEX_SET"],range(e,e+RTED_hor)),'Pmin'])
            Inflex_EDPmax_cur = pd.DataFrame(Inflex_EDPmax.loc[(Supply_List["INFLEX_SET"],range(e,e+RTED_hor)),'Pmax'])
            Flex_EDPmax_cur = pd.DataFrame(.0, columns = ["Pmax"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(e,e+RTED_hor)]))
            Flex_EDPmax_cur.index.names = ['genname','inter']
            Flex_EDPmin_cur = pd.DataFrame(.0, columns = ["Pmin"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(e,e+RTED_hor)]))
            Flex_EDPmin_cur.index.names = ['genname','inter']
                
            ESS_RTED_ch_cur = pd.DataFrame(ESS_RTED_Ch.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'ch'])
            ESS_RTED_dis_cur = pd.DataFrame(ESS_RTED_Dis.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'dis'])
            ESS_RTED_SOC_LOSS_cur = pd.DataFrame(ESS_RTED_SOC_LOSS.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'loss'])
            for ei in Supply_List["DPESS_SET"]:
                SOC_initial.loc[ei,'soc'] = EDins.soc[ei,e-1].value
                RTED_ess_InitPow.loc[ei,'Pow0'] = EDins.ess_pow[ei,e-1].value                    
            
            # Inherit the flexible unit trajectory
            for g in Supply_List["FLEX_SET"]:
                for j in range(e,e+RTED_hor):
                    Flex_EDPmin_cur.loc[(g,j),'Pmin'] = Flex_EDPmin.loc[(g,j),'Pmin']
                    Flex_EDPmax_cur.loc[(g,j),'Pmax'] = Flex_EDPmax.loc[(g,j),'Pmax']
                    
            RTEDTime1 = time.process_time()
            RTEDdatprev = RTED_create_dat(RTED_DAT_fp, e, inter_num, setting_input, RTED_res, RTED_hor, bus_input, gen_input, ess_input, line_input,                                      PTDF_input, reserve_input, Load_TS["RTED_Load"], Load_TS["RTED_Load_raw"], Supply_TS["RTED_G23"],                                      Supply_TS["RTED_E1"], Supply_List, Inflex_EDPmin_cur, Inflex_EDPmax_cur, Flex_EDPmin_cur, Flex_EDPmax_cur,                                      ESS_RTED_ch_cur, ESS_RTED_dis_cur, ESS_RTED_SOC_LOSS_cur, SOC_initial,                                      gen_initialPmax, gen_initialPmin, gen_initialMW, RTED_ess_InitPow, Reserve_TS)
        
            EDins = EDmdl.create_instance(RTED_DAT_fp + str(e) + '.dat')
            EDins.dual = pe.Suffix(direction = pe.Suffix.IMPORT) # To include the duals if any
 
            ## add load change from OpenDss 
            ## add OpenDss simulation
            # change the load values for cyber events
            if i == 12:
                SLG_fault.create('F1', 'p5udt6490-p5udt747xx', 3)
                # Switch_off.create('l(r:p5udt6490-p5udt747)', 2, 3)
                # Load_perturb.create_single('load_p5ulv58', 1.5)
                # Load_perturb.create_system([1.5] * len(Austin.dssLoad.AllNames()))
            
            Austin.snapshot_run()
            Vmag = Austin.getVmag()
            Vpu = np.array([Vmag[i]/Vbase[i] for i in range(len(Vmag))])
            
            Vpu_ts[:, e-1: e] = Vpu.reshape((len(Vpu), 1))
                    
            Feeder_head_power = []
            Feeder_head_power.append(Austin.dssCircuit.TotalPower()[0]/1000)
            Feeder_head_power = np.array(Feeder_head_power)
                                              
            EDins.Load_Bus[2,e]=-float(Feeder_head_power)*10
            v1 = Austin.dssCircuit.AllNodeVmagPUByPhase(1) # store phase 1 nodes 
            v1_name = Austin.dssCircuit.AllNodeNamesByPhase(1)  # name that match the voltage   
            v1_all.append(v1) # get all snapshot in the list
            Feeder_total_power.append(Feeder_head_power)
       
            results = opt_ed.solve(EDins, tee=True, keepfiles=True)
            
            if i == 12:
                SLG_fault.clean('F1')
                # Switch_off.clean('l(r:p5udt6490-p5udt747)', 2, 3)
                # Load_perturb.clean_single('load_p5ulv58', 1.5)
                # Load_perturb.clean_system([1.5] * len(Austin.dssLoad.AllNames()))
            
            # get gen and load and update ACPF cases.
            # update the load
            kk=0
            for ldi in list([2,3,5,6,8,10,12]):
                pfss.PQ.p0.v[kk] = EDins.Load_Bus[ldi,e].value/100
                kk=kk+1
            # update the generation from geneators and PV   
            gkk=0    
            for gi in Supply_List["DPGEN_SET"]: 
                if gi == 'SOUTHG1': # Slack bus generator
                    pfss.Slack.p0.v =  EDins.gen_power[gi,e].value/100
                else:
                    pfss.PV.p0.v[gkk] =  EDins.gen_power[gi,e].value/100
                    gkk=gkk+1
            # update the generation from ESS         
            for gi in Supply_List["DPESS_SET"]:              
                pfss.PV.p0.v[gkk] =  EDins.ess_pow[gi,e].value/100
                gkk=gkk+1   
            
            pfss.PV.cache.refresh()
            pfss.PQ.cache.refresh()
            # setup system
            pfss.setup()
            # run power flow
            pfss.PFlow.run()             

            if pfss.PFlow.converged == True and min(pfss.Bus.v.v)>0.90:
                #record bus 2 voltage magnitude
                v1_bus2 = pd.concat([v1_bus2, pd.DataFrame(np.reshape(pfss.Bus.v.v, (1,len(pfss.Bus.v.v))),columns=[list(range(19))])], axis = 0)
            else:
                pfss.Shunt.b.v = np.array([2.5,6,6,3,3]) 
                # setup system
                pfss.setup()
                # run power flow
                pfss.PFlow.run() 
                v1_bus2 = pd.concat([v1_bus2, pd.DataFrame(np.reshape(pfss.Bus.v.v, (1,len(pfss.Bus.v.v))),columns=[list(range(19))])], axis = 0)
                pfss.Shunt.b.v = switched_shut0 
                
                
            #update the feeder head voltage
            if pfss.PFlow.converged == True:
                temp_v =  pfss.Bus.v.v[1]       
                Austin.updateSubVmag(temp_v) 
            else: 
                Austin.updateSubVmag(1) 
             
                    
            RTEDTime2 = time.process_time()
            RTED_time += RTEDTime2 - RTEDTime1
            # RTED_solver_wall_time += float(results.Solver.Wall_time)

            # ---- Post-solution data retrieval
            
            RTED_gen_cost += EDins.gen_cost[e].value
            RTED_ess_cost += EDins.ess_cost[e].value
            RTED_reserve_cost += EDins.reserve_cost[e].value
            RTED_penalty_cost += EDins.penalty_cost[e].value
            
            RT_LMP = ExportLMP(EDins, EDins.dual, line_input, [list(EDins.INTER_SET)[0]], EDins.LOAD_BUS_SET, EDins.LINE_SET).Calculate_LMP()
        
            for k in Supply_List["GEN2_SET"]:
                Renew_curtail.loc[e,k] = (Supply_TS["RTED_G23"].loc[e,k] - EDins.gen_power[k,e].value) / inter_num

            for ei in Supply_List["DPESS_SET"]:
                RTED_ess_dis.loc[e,ei] = EDins.ess_dis[ei,e].value
                RTED_ess_ch.loc[e,ei] = EDins.ess_ch[ei,e].value
                RTED_ess_pow.loc[e,ei] = EDins.ess_pow[ei,e].value
                RTED_socResult.loc[e,ei] = EDins.soc[ei,e].value
                RTED_relax.loc[e,ei] = EDins.soc_relax1[ei,e].value + EDins.soc_relax2[ei,e].value
                RTED_ess_pfr_up.loc[e,ei] = EDins.ess_pfr_pos[ei,e].value 
                RTED_ess_pfr_dn.loc[e,ei] = EDins.ess_pfr_neg[ei,e].value 
                RTED_ess_agc_up.loc[e,ei] = EDins.ess_agc_pos[ei,e].value
                RTED_ess_agc_dn.loc[e,ei] = EDins.ess_agc_neg[ei,e].value
                
            for ei in Supply_List["ESS1_SET"]:
                RTED_ess_ch.loc[e,ei] = -Supply_TS["RTED_E1"].loc[e,ei] if Supply_TS["RTED_E1"].loc[e,ei] <= 0 else 0
                RTED_ess_dis.loc[e,ei] = Supply_TS["RTED_E1"].loc[e,ei] if Supply_TS["RTED_E1"].loc[e,ei] > 0 else 0
                RTED_ess_pow.loc[e,ei] = Supply_TS["RTED_E1"].loc[e,ei]
                
            for gi in Supply_List["DPGEN_SET"]:
                RTED_PgenResult.loc[e,gi] = EDins.gen_power[gi,e].value
            for gi in Supply_List["GEN3_SET"]:
                RTED_PgenResult.loc[e,gi] = Supply_TS["RTED_G23"].loc[e,gi]
            
            for j in RTED_RegionDispatch.columns:
                for gi in Supply_List["DPGEN_SET"]:
                    if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                        RTED_RegionDispatch.loc[e,j] += EDins.gen_power[gi,e].value
                for gi in Supply_List["GEN3_SET"]:
                    if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                        RTED_RegionDispatch.loc[e,j] += Supply_TS["RTED_G23"].loc[e,gi]

                for ei in Supply_List["DPESS_SET"]:
                    if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                        RTED_RegionDispatch.loc[e,j] += EDins.ess_pow[ei,e].value
                for ei in Supply_List["ESS1_SET"]:
                    if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                        RTED_RegionDispatch.loc[e,j] += Supply_TS["RTED_E1"].loc[e,ei]
            
            for gi in Supply_List["GEN1_SET"]:
                RTED_RU_slack.loc[e,gi] = EDins.gen_ramp_up_slack[gi,e].value
                RTED_RD_slack.loc[e,gi] = EDins.gen_ramp_dn_slack[gi,e].value
                
            for bi in bus_list:
                RTED_LMP.loc[e,bi] = RT_LMP.loc[e,bi]
        
            for li in line_list:
                RTED_CU_slack.loc[e,li] = EDins.Ln_Cap_up_Slack[li,e].value
                RTED_CD_slack.loc[e,li] = EDins.Ln_Cap_dn_Slack[li,e].value
                if abs(line_input.loc[li,"Active"] - 1) <= 1e-4:
                    RTED_LineFlow.loc[e,li] = sum(EDins.Ln_PTDF[li, EDins.Gen_Bus[gi]] * EDins.gen_power[gi,e].value for gi in EDins.DPGEN_SET) + sum(EDins.Ln_PTDF[li, EDins.ESS_Bus[ei]]* EDins.ess_pow[ei,e].value    for ei in EDins.DPESS_SET) - sum(EDins.Ln_PTDF[li, ldi] * (EDins.Load_Bus[ldi,e].value    - EDins.lol[ldi,e].value + EDins.sol[ldi,e].value) for ldi in EDins.LOAD_BUS_SET)

            RTED_lol.loc[e,'lol'] = sum(EDins.lol[ldi, e].value for ldi in EDins.LOAD_BUS_SET)
            RTED_sol.loc[e,'sol'] = sum(EDins.sol[ldi, e].value for ldi in EDins.LOAD_BUS_SET)
        
            RTED_pfrup_Insuf.loc[e] = EDins.sys_IR1_pos[e].value
            RTED_pfrdn_Insuf.loc[e] = EDins.sys_IR1_neg[e].value
            RTED_agcup_Insuf.loc[e] = EDins.sys_IR2_pos[e].value
            RTED_agcdn_Insuf.loc[e] = EDins.sys_IR2_neg[e].value
            
            RTED_Total_Load_new.loc[e] = sum(EDins.Load_Bus[ldi,e].value  for ldi in EDins.LOAD_BUS_SET)
            RTED_Gen_cost_interval.loc [e] = EDins.gen_cost[e].value
                        
            
            for gi in Supply_List["DPGEN_SET"]:
                RTED_pfrup_Result.loc[e,gi] = EDins.gen_pfr_pos[gi,e].value
                RTED_pfrdn_Result.loc[e,gi] = EDins.gen_pfr_neg[gi,e].value
                RTED_agcup_Result.loc[e,gi] = EDins.gen_agc_pos[gi,e].value
                RTED_agcdn_Result.loc[e,gi] = EDins.gen_agc_neg[gi,e].value
                
             
            os.makedirs(os.path.dirname(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str(e) + '.csv'), exist_ok=True)    
            with open(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str(e) + '.csv', 'w') as f:
                f.write('number,Pgen,PFR_up,PFR_dn,AGC_up,AGC_dn, SOC\n')
                for gi in Supply_List["DPGEN_SET"]:
                    f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[e,gi], RTED_pfrup_Result.loc[e,gi],                                                     RTED_pfrdn_Result.loc[e,gi], RTED_agcup_Result.loc[e,gi],                                                     RTED_agcdn_Result.loc[e,gi], np.nan))
                for gi in Supply_List["GEN3_SET"]:
                    f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[e,gi], np.nan, np.nan, np.nan, np.nan, np.nan))
                for ei in Supply_List["DPESS_SET"]:
                    f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[e,ei], RTED_ess_pfr_up.loc[e,ei],                                                     RTED_ess_pfr_dn.loc[e,ei], RTED_ess_agc_up.loc[e,ei],                                                     RTED_ess_agc_dn.loc[e,ei], RTED_socResult.loc[e,ei]))  
                for ei in Supply_List["ESS1_SET"]:
                    f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[e,ei], np.nan, np.nan, np.nan, np.nan, np.nan)) 
        
            UC_prev = pd.DataFrame(.0, columns = ["I"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(i+1,i+RTUC_hor+1)]))
            shutdow_prev = pd.DataFrame(.0, columns = ["shut"],                      index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(i+1,i+RTUC_hor+1)]))
            for gi in Supply_List["FLEX_SET"]:
                for j in range(RTUC_hor):
                    UC_prev.loc[(gi,i+j+1),'I'] = RTUCins.gen_onoff[gi,i+j+1].value
                    shutdow_prev.loc[(gi,i+j+1),'shut'] = RTUCins.gen_shutdow[gi,i+j+1].value
        
            Flex_EDPmax_prev = Flex_EDPmax
            Flex_EDPmin_prev = Flex_EDPmin
        


# In[14]:


for e in range(277, 289):

    gen_initialMW = pd.DataFrame(.0, columns = ['IntPow'], index = Supply_List["GEN1_SET"])
    gen_initialMW.index.names = ['genname']
    gen_initialPmax = pd.DataFrame(.0, columns = ['Pmax'], index = Supply_List["GEN1_SET"])
    gen_initialPmax.index.names = ['genname']
    gen_initialPmin = pd.DataFrame(.0, columns = ['Pmin'], index = Supply_List["GEN1_SET"])
    gen_initialPmin.index.names = ['genname']
    RTED_ess_InitPow = pd.DataFrame(.0, columns = ['Pow0'], index = Supply_List["DPESS_SET"])
    RTED_ess_InitPow.index.names = ['essname']
    SOC_initial = pd.DataFrame(.0, columns = ['soc'], index = Supply_List["DPESS_SET"])
    SOC_initial.index.names = ['essname']  
                
    for gi in Supply_List["DPGEN_SET"]:
        gen_initialMW.loc[gi,'IntPow'] = EDins.gen_power[gi,e-1].value
        if gi in Supply_List["INFLEX_SET"]:
            gen_initialPmax.loc[gi,'Pmax'] = Inflex_EDPmax_cur.loc[gi,'Pmax'][e-1]
            gen_initialPmin.loc[gi,'Pmin'] = Inflex_EDPmin_cur.loc[gi,'Pmin'][e-1]
        if gi in Supply_List["FLEX_SET"]:
            gen_initialPmax.loc[gi,'Pmax'] = Flex_EDPmax_cur.loc[gi,'Pmax'][e-1]
            gen_initialPmin.loc[gi,'Pmin'] = Flex_EDPmin_cur.loc[gi,'Pmin'][e-1]
            
    Inflex_EDPmin_cur = pd.DataFrame(Inflex_EDPmin.loc[(Supply_List["INFLEX_SET"],range(e,e+RTED_hor)),'Pmin'])
    Inflex_EDPmax_cur = pd.DataFrame(Inflex_EDPmax.loc[(Supply_List["INFLEX_SET"],range(e,e+RTED_hor)),'Pmax'])
    Flex_EDPmax_cur = pd.DataFrame(.0, columns = ["Pmax"],                index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(e,e+RTED_hor)]))
    Flex_EDPmax_cur.index.names = ['genname','inter']
    Flex_EDPmin_cur = pd.DataFrame(.0, columns = ["Pmin"],                index = pd.MultiIndex.from_product([Supply_List["FLEX_SET"],range(e,e+RTED_hor)]))
    Flex_EDPmin_cur.index.names = ['genname','inter']
                
    ESS_RTED_ch_cur = pd.DataFrame(ESS_RTED_Ch.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'ch'])
    ESS_RTED_dis_cur = pd.DataFrame(ESS_RTED_Dis.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'dis'])
    ESS_RTED_SOC_LOSS_cur = pd.DataFrame(ESS_RTED_SOC_LOSS.loc[(Supply_List["DPESS_SET"],range(e,e+RTED_hor)),'loss'])
    for ei in Supply_List["DPESS_SET"]:
        SOC_initial.loc[ei,'soc'] = EDins.soc[ei,e-1].value
        RTED_ess_InitPow.loc[ei,'Pow0'] = EDins.ess_pow[ei,e-1].value                    
            
    # Inherit the flexible unit trajectory
    for g in Supply_List["FLEX_SET"]:
        for j in range(e,e+RTED_hor):
            Flex_EDPmin_cur.loc[(g,j),'Pmin'] = Flex_EDPmin.loc[(g,j),'Pmin']
            Flex_EDPmax_cur.loc[(g,j),'Pmax'] = Flex_EDPmax.loc[(g,j),'Pmax']
        
    RTEDTime1 = time.process_time()            
    RTEDdatprev = RTED_create_dat(RTED_DAT_fp, e, inter_num, setting_input, RTED_res, RTED_hor, bus_input, gen_input, ess_input, line_input,                                      PTDF_input, reserve_input, Load_TS["RTED_Load"], Load_TS["RTED_Load_raw"], Supply_TS["RTED_G23"],                                      Supply_TS["RTED_E1"], Supply_List, Inflex_EDPmin_cur, Inflex_EDPmax_cur, Flex_EDPmin_cur, Flex_EDPmax_cur,                                      ESS_RTED_ch_cur, ESS_RTED_dis_cur, ESS_RTED_SOC_LOSS_cur, SOC_initial,                                      gen_initialPmax, gen_initialPmin, gen_initialMW, RTED_ess_InitPow, Reserve_TS)
        
    EDins = EDmdl.create_instance(RTED_DAT_fp + str(e) + '.dat')
    EDins.dual = pe.Suffix(direction = pe.Suffix.IMPORT) # To include the duals if any

    ## add load change from OpenDss 
    ## add OpenDss simulation
    Austin.snapshot_run()
    Vmag = Austin.getVmag()
    Vpu = np.array([Vmag[i]/Vbase[i] for i in range(len(Vmag))])
            
    Vpu_ts[:, e-1: e] = Vpu.reshape((len(Vpu), 1))
                    
    Feeder_head_power = []
    Feeder_head_power.append(Austin.dssCircuit.TotalPower()[0]/1000)
    Feeder_head_power = np.array(Feeder_head_power)
                                              
    EDins.Load_Bus[2,e]=-float(Feeder_head_power)*10
    v1 = Austin.dssCircuit.AllNodeVmagPUByPhase(1) # store phase 1 nodes 
    v1_name = Austin.dssCircuit.AllNodeNamesByPhase(1)  # name that match the voltage   
    v1_all.append(v1) # get all snapshot in the list
    Feeder_total_power.append(Feeder_head_power)
    # if e == event_start:
    #             # Event1.create()
    #     Event2.create()
    #     # Event3.create(1.3)

    # if e == event_end:
    #             # Event1.clean()
    #     Event2.clean()
    #     # Event3.clean(1.3) 
        
    results = opt_ed.solve(EDins, tee=True, keepfiles=True)
    
    # get gen and load and update ACPF cases.
    # update the load
    kk=0
    for ldi in list([2,3,5,6,8,10,12]):
        pfss.PQ.p0.v[kk] = EDins.Load_Bus[ldi,e].value/100
        kk=kk+1
    # update the generation from geneators and PV   
    gkk=0    
    for gi in Supply_List["DPGEN_SET"]: 
        if gi == 'SOUTHG1': # Slack bus generator
            pfss.Slack.p0.v =  EDins.gen_power[gi,e].value/100
        else:
            pfss.PV.p0.v[gkk] =  EDins.gen_power[gi,e].value/100
            gkk=gkk+1
    # update the generation from ESS         
    for gi in Supply_List["DPESS_SET"]:              
        pfss.PV.p0.v[gkk] =  EDins.ess_pow[gi,e].value/100
        gkk=gkk+1   
            
    pfss.PV.cache.refresh()
    pfss.PQ.cache.refresh()
    # setup system
    pfss.setup()
    # run power flow
    pfss.PFlow.run()        
    #record bus 2 voltage magnitude
    v1_bus2 = pd.concat([v1_bus2, pd.DataFrame(np.reshape(pfss.Bus.v.v, (1,len(pfss.Bus.v.v))),columns=[list(range(19))])], axis = 0)
    
    #update the feeder head voltage
    if pfss.PFlow.converged == True:
        temp_v =  pfss.Bus.v.v[1]       
        Austin.updateSubVmag(temp_v) 
    else: 
        Austin.updateSubVmag(1)      
    
    RTEDTime2 = time.process_time()
    RTED_time += RTEDTime2 - RTEDTime1
    # RTED_solver_wall_time += float(results.Solver.Wall_time)
        
    RTED_gen_cost += EDins.gen_cost[e].value
    RTED_ess_cost += EDins.ess_cost[e].value
    RTED_reserve_cost += EDins.reserve_cost[e].value
    RTED_penalty_cost += EDins.penalty_cost[e].value

    RT_LMP = ExportLMP(EDins, EDins.dual, line_input, [list(EDins.INTER_SET)[0]], EDins.LOAD_BUS_SET, EDins.LINE_SET).Calculate_LMP()
        
    for k in Supply_List["GEN2_SET"]:
        Renew_curtail.loc[e,k] = (Supply_TS["RTED_G23"].loc[e,k] - EDins.gen_power[k,e].value) / inter_num

    for ei in Supply_List["DPESS_SET"]:
        RTED_ess_dis.loc[e,ei] = EDins.ess_dis[ei,e].value
        RTED_ess_ch.loc[e,ei] = EDins.ess_ch[ei,e].value
        RTED_ess_pow.loc[e,ei] = EDins.ess_pow[ei,e].value
        RTED_socResult.loc[e,ei] = EDins.soc[ei,e].value
        RTED_relax.loc[e,ei] = EDins.soc_relax1[ei,e].value + EDins.soc_relax2[ei,e].value
        RTED_ess_pfr_up.loc[e,ei] = EDins.ess_pfr_pos[ei,e].value 
        RTED_ess_pfr_dn.loc[e,ei] = EDins.ess_pfr_neg[ei,e].value 
        RTED_ess_agc_up.loc[e,ei] = EDins.ess_agc_pos[ei,e].value
        RTED_ess_agc_dn.loc[e,ei] = EDins.ess_agc_neg[ei,e].value
                
    for ei in Supply_List["ESS1_SET"]:
        RTED_ess_ch.loc[e,ei] = -Supply_TS["RTED_E1"].loc[e,ei] if Supply_TS["RTED_E1"].loc[e,ei] <= 0 else 0
        RTED_ess_dis.loc[e,ei] = Supply_TS["RTED_E1"].loc[e,ei] if Supply_TS["RTED_E1"].loc[e,ei] > 0 else 0
        RTED_ess_pow.loc[e,ei] = Supply_TS["RTED_E1"].loc[e,ei]
                
    for gi in Supply_List["DPGEN_SET"]:
        RTED_PgenResult.loc[e,gi] = EDins.gen_power[gi,e].value
    for gi in Supply_List["GEN3_SET"]:
        RTED_PgenResult.loc[e,gi] = Supply_TS["RTED_G23"].loc[e,gi]
            
    for j in RTED_RegionDispatch.columns:
        for gi in Supply_List["DPGEN_SET"]:
            if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                RTED_RegionDispatch.loc[e,j] += EDins.gen_power[gi,e].value
        for gi in Supply_List["GEN3_SET"]:
            if str(bus_input.loc[str(gen_input.loc[gi,'busname']), 'Region']) == str(j):
                RTED_RegionDispatch.loc[e,j] += Supply_TS["RTED_G23"].loc[e,gi]

        for ei in Supply_List["DPESS_SET"]:
            if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                RTED_RegionDispatch.loc[e,j] += EDins.ess_pow[ei,e].value
        for ei in Supply_List["ESS1_SET"]:
            if str(bus_input.loc[str(ess_input.loc[ei,'busname']), 'Region']) == str(j):
                RTED_RegionDispatch.loc[e,j] += Supply_TS["RTED_E1"].loc[e,ei]
        
    for bi in bus_list:
        RTED_LMP.loc[e,bi] = RT_LMP.loc[e,bi]
            
    for gi in Supply_List["GEN1_SET"]:
        RTED_RU_slack.loc[e,gi] = EDins.gen_ramp_up_slack[gi,e].value
        RTED_RD_slack.loc[e,gi] = EDins.gen_ramp_dn_slack[gi,e].value
        
    for li in line_list:
        RTED_CU_slack.loc[e,li] = EDins.Ln_Cap_up_Slack[li,e].value
        RTED_CD_slack.loc[e,li] = EDins.Ln_Cap_dn_Slack[li,e].value
        if abs(line_input.loc[li,"Active"] - 1) <= 1e-4:
            RTED_LineFlow.loc[e,li] = sum(EDins.Ln_PTDF[li, EDins.Gen_Bus[gi]] * EDins.gen_power[gi,e].value for gi in EDins.DPGEN_SET) +                sum(EDins.Ln_PTDF[li, EDins.ESS_Bus[ei]]* EDins.ess_pow[ei,e].value                 for ei in EDins.DPESS_SET) - sum(EDins.Ln_PTDF[li, ldi] * (EDins.Load_Bus[ldi,e].value                  - EDins.lol[ldi,e].value + EDins.sol[ldi,e].value) for ldi in EDins.LOAD_BUS_SET)

    RTED_lol.loc[e,'lol'] = sum(EDins.lol[ldi, e].value for ldi in EDins.LOAD_BUS_SET)
    RTED_sol.loc[e,'sol'] = sum(EDins.sol[ldi, e].value for ldi in EDins.LOAD_BUS_SET)
        
    RTED_pfrup_Insuf.loc[e] = EDins.sys_IR1_pos[e].value
    RTED_pfrdn_Insuf.loc[e] = EDins.sys_IR1_neg[e].value
    RTED_agcup_Insuf.loc[e] = EDins.sys_IR2_pos[e].value
    RTED_agcdn_Insuf.loc[e] = EDins.sys_IR2_neg[e].value
    
    RTED_Total_Load_new.loc[e] = sum(EDins.Load_Bus[ldi,e].value  for ldi in EDins.LOAD_BUS_SET)
    RTED_Gen_cost_interval.loc [e] = EDins.gen_cost[e].value        
            
    for gi in Supply_List["DPGEN_SET"]:
        RTED_pfrup_Result.loc[e,gi] = EDins.gen_pfr_pos[gi,e].value
        RTED_pfrdn_Result.loc[e,gi] = EDins.gen_pfr_neg[gi,e].value
        RTED_agcup_Result.loc[e,gi] = EDins.gen_agc_pos[gi,e].value
        RTED_agcdn_Result.loc[e,gi] = EDins.gen_agc_neg[gi,e].value
                   
    os.makedirs(os.path.dirname(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str(e) + '.csv'), exist_ok=True)    
    with open(Dynamic_ex_fp + 'DYNAMIC_INPUT' + str(e) + '.csv', 'w') as f:
        f.write('number,Pgen,PFR_up,PFR_dn,AGC_up,AGC_dn, SOC\n')
        for gi in Supply_List["DPGEN_SET"]:
            f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[e,gi], RTED_pfrup_Result.loc[e,gi],                                             RTED_pfrdn_Result.loc[e,gi], RTED_agcup_Result.loc[e,gi],                                             RTED_agcdn_Result.loc[e,gi], np.nan))
        for gi in Supply_List["GEN3_SET"]:
            f.write('%s,%f,%f,%f,%f,%f,%f\n' % (gi,RTED_PgenResult.loc[e,gi], np.nan, np.nan, np.nan, np.nan, np.nan))
        for ei in Supply_List["DPESS_SET"]:
            f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[e,ei], RTED_ess_pfr_up.loc[e,ei],                                             RTED_ess_pfr_dn.loc[e,ei], RTED_ess_agc_up.loc[e,ei],                                             RTED_ess_agc_dn.loc[e,ei], RTED_socResult.loc[e,ei]))  
        for ei in Supply_List["ESS1_SET"]:
            f.write('%s,%f,%f,%f,%f,%f,%f\n' % (ei,RTED_ess_pow.loc[e,ei], np.nan, np.nan, np.nan, np.nan, np.nan))                 
    


# In[15]:


sum_index = ["RTED elapsed time",
             "Final ED: # of constraints",
             "Final ED: # of variables",
             "RTED Total Cost",
             "RT-Geneneration Cost",
             "RT-ESS Cost",
             "RT-Reserve Cost",
             "RT-Penalty Cost"]
sum_value = [RTED_time, 
             results.Problem.Number_of_constraints, results.Problem.Number_of_variables,
             RTED_gen_cost + RTED_ess_cost + RTED_reserve_cost + RTED_penalty_cost,
             RTED_gen_cost, RTED_ess_cost, RTED_reserve_cost, RTED_penalty_cost]
RTED_summary = pd.DataFrame(.0, index = sum_index, columns = ["value"])
for i in range(8):
    RTED_summary.iloc[i] = sum_value[i]


# In[16]:


RTUCResults = {'Gen_Dispatch': RTUC_PgenResult.copy(),
              'Gen_PFR_up': RTUC_pfrup_Result.copy(),
              'Gen_PFR_dn': RTUC_pfrdn_Result.copy(),
              'Gen_AGC_up': RTUC_agcup_Result.copy(),
              'Gen_AGC_dn': RTUC_agcdn_Result.copy(),
              'Line_Flow': RTUC_LineFlow.copy(),
              'ESS_Dis': ESS_RTUC_Dis.copy(),
              'ESS_Ch': ESS_RTUC_Ch.copy(),
              'ESS_PFR_up': RTUC_ess_pfr_up.copy(),
              'ESS_PFR_dn': RTUC_ess_pfr_dn.copy(),
              'ESS_AGC_up': RTUC_ess_agc_up.copy(),
              'ESS_AGC_dn': RTUC_ess_agc_dn.copy(),
              'LoL': RTUC_lol.copy(),
              'SoL': RTUC_sol.copy(),
              'SOC_Relax': RTUC_relax.copy(),
              'RU Slack': RTUC_RU_slack.copy(),
              'RD Slack': RTUC_RD_slack.copy(),
              'CU Slack': RTUC_CU_slack.copy(),
              'CD Slack': RTUC_CD_slack.copy()}
    
np.save(RTUCResult_fp + "RTUCResult_Dict.npy", RTUCResults)

for i in list(RTUCResults.keys()):
    for j in list(RTUCResults[i].columns):
        if "Dum" in j:
            del RTUCResults[i][j]

with pd.ExcelWriter(RTUCResult_fp + 'RTUCOutput.xlsx') as writer: 
    RTUC_PgenResult.to_excel(writer, sheet_name = "Dispatch")
    RTUC_pfrup_Result.to_excel(writer, sheet_name = "Gen PFRup")
    RTUC_pfrdn_Result.to_excel(writer, sheet_name = "Gen PFRdn")
    RTUC_agcup_Result.to_excel(writer, sheet_name = "Gen AGCup")
    RTUC_agcdn_Result.to_excel(writer, sheet_name = "Gen AGCdn")
    RTUC_LineFlow.to_excel(writer, sheet_name = "Line Flow")
    ESS_RTUC_Dis.to_excel(writer, sheet_name = "ESS Dis")
    ESS_RTUC_Ch.to_excel(writer, sheet_name = "ESS Ch")
    RTUC_socResult.to_excel(writer, sheet_name = "ESS SOC")
    RTUC_ess_pfr_up.to_excel(writer, sheet_name = "ESS PFRup")
    RTUC_ess_pfr_dn.to_excel(writer, sheet_name = "ESS PFRdn")
    RTUC_ess_agc_up.to_excel(writer, sheet_name = "ESS AGCup")
    RTUC_ess_agc_dn.to_excel(writer, sheet_name = "ESS AGCdn")
    RTUC_lol.to_excel(writer, sheet_name = "LoL")
    RTUC_sol.to_excel(writer, sheet_name = "SoL")
    RTUC_relax.to_excel(writer, sheet_name = "SOC Relax")
    RTUC_RU_slack.to_excel(writer, sheet_name = "RU Slack")
    RTUC_RD_slack.to_excel(writer, sheet_name = "RD Slack")
    RTUC_CU_slack.to_excel(writer, sheet_name = "CU Slack")
    RTUC_CD_slack.to_excel(writer, sheet_name = "CD Slack")


# In[17]:


RTEDResults = {'Summary': RTED_summary.copy(),
             'Gen_Dispatch': RTED_PgenResult.copy(),
             'Region_Dispatch': RTED_RegionDispatch.copy(),
             'Gen_PFR_up': RTED_pfrup_Result.copy(),
             'Gen_PFR_dn': RTED_pfrdn_Result.copy(),
             'Gen_AGC_up': RTED_agcup_Result.copy(),
             'Gen_AGC_dn': RTED_agcdn_Result.copy(),
             'Line_Flow': RTED_LineFlow.copy(),
             'RT_LMP': RTED_LMP.copy(),
             'ESS_Dis': RTED_ess_dis.copy(),
             'ESS_Ch': RTED_ess_ch.copy(),
             'ESS_SOC': RTED_socResult.copy(),
             'ESS_PFR_up': RTED_ess_pfr_up.copy(),
             'ESS_PFR_dn': RTED_ess_pfr_dn.copy(),
             'ESS_AGC_up': RTED_ess_agc_up.copy(),
             'ESS_AGC_dn': RTED_ess_agc_dn.copy(),
             'LoL': RTED_lol.copy(),
             'SoL': RTED_sol.copy(),
             'SOC_Relax': RTED_relax.copy(),
             'RU Slack': RTED_RU_slack.copy(),
             'RD Slack': RTED_RD_slack.copy(),
             'CU Slack': RTED_CU_slack.copy(),
             'CD Slack': RTED_CD_slack.copy(),
             'Total_Load_new': RTED_Total_Load_new.copy(),
             'Gen_cost_interval': RTED_Gen_cost_interval.copy()}

np.save(RTEDResult_fp + "RTEDResult_Dict.npy", RTEDResults)

for i in list(RTEDResults.keys()):
    for j in list(RTEDResults[i].columns):
        if "Dum" in j:
            del RTEDResults[i][j]

with pd.ExcelWriter(RTEDResult_fp + 'RTEDOutput.xlsx') as writer: 
    RTEDResults['Summary'].to_excel(writer, sheet_name = "Summary")
    RTEDResults['Gen_Dispatch'].to_excel(writer, sheet_name = "Dispatch")
    RTEDResults['Region_Dispatch'].to_excel(writer, sheet_name = "Region Dispatch")
    RTEDResults['Gen_PFR_up'].to_excel(writer, sheet_name = "Gen PFRup")
    RTEDResults['Gen_PFR_dn'].to_excel(writer, sheet_name = "Gen PFRdn")
    RTEDResults['Gen_AGC_up'].to_excel(writer, sheet_name = "Gen AGCup")
    RTEDResults['Gen_AGC_dn'].to_excel(writer, sheet_name = "Gen AGCdn")
    RTEDResults['RT_LMP'].to_excel(writer, sheet_name = "RT LMP")
    RTEDResults['Line_Flow'].to_excel(writer, sheet_name = "Line Flow")
    RTEDResults['ESS_Dis'].to_excel(writer, sheet_name = "ESS Dis")
    RTEDResults['ESS_Ch'].to_excel(writer, sheet_name = "ESS Ch")
    RTEDResults['ESS_SOC'].to_excel(writer, sheet_name = "ESS SOC")
    RTEDResults['ESS_PFR_up'].to_excel(writer, sheet_name = "ESS PFRup")
    RTEDResults['ESS_PFR_dn'].to_excel(writer, sheet_name = "ESS PFRdn")
    RTEDResults['ESS_AGC_up'].to_excel(writer, sheet_name = "ESS AGCup")
    RTEDResults['ESS_AGC_dn'].to_excel(writer, sheet_name = "ESS AGCdn")
    RTEDResults['LoL'].to_excel(writer, sheet_name = "LoL")
    RTEDResults['SoL'].to_excel(writer, sheet_name = "SoL")
    RTEDResults['SOC_Relax'].to_excel(writer, sheet_name = "SOC Relax")
    RTEDResults['RU Slack'].to_excel(writer, sheet_name = "RU Slack")
    RTEDResults['RD Slack'].to_excel(writer, sheet_name = "RD Slack")
    RTEDResults['CU Slack'].to_excel(writer, sheet_name = "CU Slack")
    RTEDResults['CD Slack'].to_excel(writer, sheet_name = "CD Slack")
    RTEDResults['Total_Load_new'].to_excel(writer, sheet_name = "Total_Load_new")
    RTEDResults['Gen_cost_interval'].to_excel(writer, sheet_name = 'Gen_cost_interval')


# In[18]:


# ---- DAUC Figure Plot
# If you run the code first time, do not uncomment code in this section since you have no results.

DAResult_Dict = np.load(DAUCResult_fp + 'DAResult_Dict.npy', allow_pickle='TRUE').item()

gen_style = 1                                      # 1: Plot all generators explicitly; 2: Plot by generator types
fig_show_flag = 0                                  # 1: Return figure; 2: Do not return figure
fig_size = (15, 15)                                # Figure size. Unit: pt
bar_color = [(0.346678,0.216974,0.135373),         # Gen-1: Brown; Gen-2: Orange; Gen-3: Red; ESS-Ch: Dark Green; 
             (0.985901,0.653587,0.227759),         # ESS-Dis: Light Green; ESS-A/S: Dark Green.
             (0.986246,0.007121,0.027434),
             (0.000000,0.488665,0.000000), 
             (0.000000,0.956004,0.000000),
             (0.000000,0.488665,0.000000),
             (1.000000,0.000000,0.937770),
             (1.000000,0.721648,0.989080)]
font_size = [30, 30, 27, 27, 35, 20]               # Font size. [xlabel, ylabel, xtick, ytick, title, legend]
fig_type = "pdf"                                   # Figure file type. If set as "pdf", "eps", "svg", 
                                                   # figure is lossless but occupy more disk space.
fig_dpi = 100                                      # If figure type is "jpg", "png" etc., this is the dpi.

# Please select one ESS to plot in the following code. E.g., "PV_ESS1"
DAFig_Plot = DAFigurePlot(DAfig_savepath, DAResult_Dict, Supply_List, line_list, bus_input, gen_input, ess_input, Load_TS["DAUC_Load"],                          Load_TS["DAUC_Load_raw"], Supply_TS, reserve_input, fig_show_flag, gen_style, Simulation_len,                           extend_time, "PV_ESS1", fig_size, bar_color, font_size, fig_type, fig_dpi)

# # Dispatch share figure
DAFig_Dispatch_share = DAFig_Plot.Fig_Dispatch()

# # Dispatch share figure
DAFig_Region_share = DAFig_Plot.Fig_Region(1)

# # PFR up share figure
DAFig_PFRup_share = DAFig_Plot.Fig_PFRup()

# # AGC up share figure
DAFig_AGCup_share = DAFig_Plot.Fig_AGCup()

# # AGC dn share figure
DAFig_AGCdn_share = DAFig_Plot.Fig_AGCdn()

# # ESS figure
DAFig_ESS_Pow = DAFig_Plot.Fig_ESS_Pow()


# In[ ]:





# In[19]:


# ---- RTED Figure Plot
# If you run the code first time, do not uncomment code in this section since you have no results.

RTEDResult_Dict = np.load(RTEDResult_fp + 'RTEDResult_Dict.npy', allow_pickle='TRUE').item()

gen_style = 1                                      # 1: Plot all generators explicitly; 0: Plot by generator types
fig_show_flag = 0                                  # 1: Return figures; 0: Do not return figures
fig_size = (15, 15)                                # Figure size. Unit: pt
bar_color = [(0.346678,0.216974,0.135373),         # Gen-1: Brown; Gen-2: Orange; Gen-3: Red; ESS-Ch: Dark Green; 
             (0.985901,0.653587,0.227759),         # ESS-Dis: Light Green; ESS-A/S: Dark Green.
             (0.986246,0.007121,0.027434),
             (0.000000,0.488665,0.000000), 
             (0.000000,0.956004,0.000000),
             (0.000000,0.488665,0.000000),
             (1.000000,0.000000,0.937770),
             (1.000000,0.721648,0.989080)]
font_size = [30, 30, 27, 27, 35, 20]               # Font size. [xlabel, ylabel, xtick, ytick, title, legend]
fig_type = "pdf"                                   # Figure file type. If set as "pdf", "eps", "svg", 
                                                   # figure is lossless but occupy more disk space.
fig_dpi = 100                                      # If figure type is "jpg", "png" etc., this is the dpi.

# Please select one ESS to plot in the following code. E.g., "PV_ESS1"
RTEDFig_Plot = RTEDFigurePlot(RTfig_savepath, RTEDResult_Dict, Supply_List, line_list, bus_input, gen_input, ess_input, Load_TS["RTED_Load"],                              Load_TS["RTED_Load_raw"], Supply_TS, reserve_input, fig_show_flag, gen_style,                               Simulation_len, extend_time, "PV_ESS1", inter_num, fig_size, bar_color, font_size,                               fig_type, fig_dpi)

# # Dispatch share figure
RTEDFig_Dispatch_share = RTEDFig_Plot.Fig_Dispatch()

# # Dispatch share figure
RTEDFig_Region_share = RTEDFig_Plot.Fig_Region(1)

# PFR up share figure
RTEDFig_PFRup_share = RTEDFig_Plot.Fig_PFRup()

# # AGC up share figure
RTEDFig_AGCup_share = RTEDFig_Plot.Fig_AGCup()

# # AGC dn share figure
RTEDFig_AGCdn_share = RTEDFig_Plot.Fig_AGCdn()

# # ESS figure
RTEDFig_ESS_Pow = RTEDFig_Plot.Fig_ESS_Pow()


# plot results the way you like
v1_all = np.array(v1_all)
plt.figure()
plt.plot(v1_all[:,0],'.') # plot a random load
plt.ylabel('Voltage (p.u.)')

# plot results the way you like
pd.DataFrame(Vpu_ts, index=Nodes, columns=range(duration)).to_csv(maindir+"\Output\Vpu.csv")
v1_bus2.to_csv(maindir + '\Output\Transmission_voltage.csv') 



