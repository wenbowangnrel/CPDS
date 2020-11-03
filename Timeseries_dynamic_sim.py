#!/usr/bin/env python
# coding: utf-8

# In[1]:


import andes
import numpy as np

andes.main.config_logger(stream_level=20)


# In[2]:


#ieee14_raw = andes.get_case("ieee14/ieee14.raw")
#ieee14_dyr = andes.get_case("ieee14/ieee14.dyr")
#ss = andes.load(ieee14_raw, addfile=ieee14_dyr, setup=False)

#load the case in andes specific case folder
ieee14 = andes.get_case('ieee14/ieee14_full.xlsx')
ss = andes.load(ieee14, setup=False)

# Call setup manually
ss.setup()

# disable existing line switches
# The IEEE 14-bus system contains predefined line switches. Disabling them to study generator trip only.

#ss.Toggler.u.v[[0, 1]] = 0

# calculate power flow

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
ss.TDS.config.tf = 0.1

# start the 0.1 second dynamic simulation
ss.TDS.run()


# In[3]:

# obtain the system load bus (PQ bus) set
shed_buses = ss.PQ.bus.v
pq_shed_idx = ss.PQ.find_idx(keys='bus', values=shed_buses)
pq_shed_idx

# record the initial system load
pq_p = ss.PQ.get(src='Ppf', idx=pq_shed_idx, attr='v')


# In[4]:


#print(ss.ACE.doc())


# In[4]:

# define the load profile: here the load profile is randomly created. We can load this profile with predetermined file
Load_timeseries = np.random.normal(1, 0.01, 150)

#start the dynamic simulation. Here the step is 2 seconds
for i in range(len(Load_timeseries)):
    # change the PQ load with the load profile
    pq_p_new = pq_p*Load_timeseries[i]
    ss.PQ.set(src='Ppf', idx=pq_shed_idx, attr='v', value=pq_p_new)
    
    # start the 2 seconds dynamic simulation
    ss.TDS.config.tf = 2*(i+1)
    ss.TDS.run()
    # if dynamic simulation can't converge, terminate the simulation
    if ss.exit_code !=0:
        raise ValueError(i)
 
#plot the dynamic simulation results    
ss.TDS.load_plotter()

#plot the system frequency
ss.TDS.plt.plot(ss.ACEc.f,ytimes=60,ylabel='Frequency (Hz)')

#plot the system ACE
ss.TDS.plt.plot(ss.ACEc.ace,ytimes=100,ylabel='ACE (MW)')

#plot the bus voltage magnitude
ss.TDS.plt.plot(ss.Bus.v, a=(0,1,2,6),ylabel='Voltage (p.u.)') 
#ss.TDS.plt.plot(ss.GENROU.omega,
#                a=(0, 2, 3, 4),
#                ytimes=60,
#               ) 


# In[18]:


#help(ss.TDS.plt.plot)


# In[19]:


# obtain the system latest voltage magnitude: the last row in the voltage data
ss.dae.ts.xy[:,ss.Bus.v.a[0]+ss.dae.n]



ss.Bus.v.a[0]


# In[6]:


ss.dae.n


# In[7]:


Load_timeseries


# In[30]:


#obtain the frequency timeseries data
ss.dae.ts.y[:,ss.ACEc.f.a]*60


# In[11]:


#obtain the ACE timeseries data
ss.dae.ts.y[:,ss.ACEc.ace.a]*100


# In[32]:


#obtain the timeseries bus voltage data
ss.dae.ts.y[:,ss.Bus.v.a]


# In[11]:


len(ss.dae.ts.xy[:,i+ss.dae.n])


# In[25]:


ss.dae.ts.t

