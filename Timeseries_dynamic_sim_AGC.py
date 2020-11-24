#!/usr/bin/env python
# coding: utf-8

# In[1]:


import andes
import numpy as np
#andes.prepare()
andes.main.config_logger(stream_level=20)
Load_timeseries = np.random.normal(1, 0.00, 30)
import matplotlib.pyplot as plt


# In[16]:


#ieee14_raw = andes.get_case("ieee14/ieee14.raw")
#ieee14_dyr = andes.get_case("ieee14/ieee14.dyr")
#ss = andes.load(ieee14_raw, addfile=ieee14_dyr, setup=False)

#ieee14 = andes.get_case('ieee14/ieee14_full.xlsx')
ieee14 = andes.get_case('ieee14/ieee14_pvd1_2DistBus.xlsx')
ss = andes.load(ieee14, setup=False, no_output=True)

ss.add("Toggler", dict(model='SynGen', dev="GENROU_3", t=10.0))
# Call setup manually

ss.setup()
#ss.Toggler.u.v[[2]] = 0
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

ss.PFlow.run()

ss.TDS.init()

ss.TDS.config.tf = 1

ss.TDS.run()

shed_buses = ss.PQ.bus.v
pq_shed_idx = ss.PQ.find_idx(keys='bus', values=shed_buses)
pq_shed_idx

pq_p = ss.PQ.get(src='Ppf', idx=pq_shed_idx, attr='v')


# In[17]:


print(ss.GENROU.doc())


# In[7]:


ss.Toggler.as_df()


# In[3]:


tg_idx=list(ss.TurbineGov._idx2model.keys())
paux0_new = np.zeros(5) - ss.ACEc.ace.v*0.2
ss.TurbineGov.set(src='paux0',idx=tg_idx, attr='v', value=paux0_new)


# In[4]:


PVD_names = ss.PVD1.idx.v
PVD_AGC_idx = ss.PVD1.find_idx(keys='idx', values=PVD_names)
PVD_AGC_idx
PVD_AGC_response = ss.PVD1.get(src='Pext', idx=PVD_AGC_idx, attr='v')


# In[17]:


paux0_new = np.zeros(5)
PVD_AGC_response = np.zeros(20)
for i in range(1,len(Load_timeseries)):
    
    
    pq_p_new = pq_p*Load_timeseries[i]
    ss.PQ.set(src='Ppf', idx=pq_shed_idx, attr='v', value=pq_p_new)
    
    if i<10 and (i+1)%2==0:
        paux0_new = paux0_new  - ss.ACEc.ace.v*0.196
        ss.TurbineGov.set(src='paux0',idx=tg_idx, attr='v', value=paux0_new)
    
        PVD_AGC_response = PVD_AGC_response - ss.ACEc.ace.v*0.001
        ss.PVD1.set(src='Pext0', idx=PVD_AGC_idx, attr='v', value=PVD_AGC_response)
    elif i>=10 and (i+1)%2==0:
        paux0_new = paux0_new - ss.ACEc.ace.v*0.245
        ss.TurbineGov.set(src='paux0',idx=tg_idx, attr='v', value=paux0_new)
    
        PVD_AGC_response = PVD_AGC_response - ss.ACEc.ace.v*0.001
        ss.PVD1.set(src='Pext0', idx=PVD_AGC_idx, attr='v', value=PVD_AGC_response)        
    
    ss.TDS.config.tf = 1*(i+1)
    ss.TDS.run()
    if ss.exit_code !=0:
        raise ValueError(i)
    
ss.TDS.load_plotter()

ss.TDS.plt.plot(ss.ACEc.f,ytimes=60,ylabel='Frequency (Hz)')
ss.TDS.plt.plot(ss.ACEc.ace,ytimes=100,ylabel='ACE (MW)')
ss.TDS.plt.plot(ss.Bus.v, a=(0,1,2,6),ylabel='Voltage (p.u.)') 
#ss.TDS.plt.plot(ss.GENROU.omega,
#                a=(0, 2, 3, 4),
#                ytimes=60,
#               ) 


# In[46]:


ss.TDS.plt.plot(ss.GENROU.omega, a=(4,),ytimes=60)


# In[64]:


ss.TDS.plt.plot(ss.ACEc.ace,ytimes=100,ylabel='ACE (MW)')


# In[60]:


ss.TDS.plt.plot(ss.ACEc.ace,ytimes=100,ylabel='ACE (MW)')


# In[65]:


ss.TDS.plt.plot(ss.ACEc.f,ytimes=60,ylabel='ACE (MW)')


# In[61]:


ss.TDS.plt.plot(ss.ACEc.f,ytimes=60,ylabel='ACE (MW)')


# In[13]:


ss.TDS.plt.plot(ss.ESST3A.vf)


# In[6]:


ss.TDS.plt.plot(ss.PVD1.Pext, a=(0,1,2,6),ytimes=100,ylabel='AGC signal (MW)')


# In[22]:


ss.dae.ts.get_data([ss.TGOV1.paux],a=[0,])


# In[7]:


ss.TDS.plt.plot(ss.TGOV1N.paux, a=(4,),ytimes=100,ylabel='Generation AGC (MW)')


# In[52]:


ss.TDS.plt.plot(ss.TGOV1N.LAG_y, a=(4,),ylabel='Generation AGC (MW)')


# In[53]:


ss.TDS.plt.plot(ss.ACEc.f,ytimes=60,ylabel='Frequency (Hz)')


# In[8]:


ss.TDS.plt.plot(ss.ACEc.ace,ytimes=100,ylabel='ACE (MW)')


# In[11]:


ss.dae.ts.get_data([ss.ACEc.f,ss.ACEc.ace])*[60,100]


# In[31]:


a=ss.dae.ts.get_data([ss.Bus.v,ss.Bus.a],a=[3,8,])


# In[32]:


a[-1,:]


# In[25]:


ss.dae.ts.y[0,ss.Bus.a.a]


# In[15]:





# In[17]:


ss.TDS.plt.plot(ss.GENROU.omega,
                a=(0, ),
                ytimes=60,
               ) 


# In[9]:


ss.dae.ts.y[:,ss.PVD1.Pext.a[11]]


# In[10]:


ss.PVD1.Pext.a


# In[12]:


ss.PVD1.Pext.v


# In[18]:


import matplotlib.pyplot as plt
plt.plot(ss.dae.ts.t,ss.dae.ts.y[:,ss.GENROU.te.a[1]]/ss.dae.ts.x[:,ss.GENROU.omega.a[1]]*100)


# In[8]:


import matplotlib.pyplot as plt
plt.plot(ss.dae.ts.t,ss.dae.ts.y[:,ss.GENROU.te.a[1]]/ss.dae.ts.x[:,ss.GENROU.omega.a[1]]*100)


# In[19]:


plt.plot(ss.dae.ts.t,ss.dae.ts.y[:,ss.GENROU.te.a[0]]/ss.dae.ts.x[:,ss.GENROU.omega.a[0]]*100)


# In[9]:


plt.plot(ss.dae.ts.t,ss.dae.ts.y[:,ss.GENROU.te.a[0]]/ss.dae.ts.x[:,ss.GENROU.omega.a[0]]*100)


# In[16]:


ss.ACEc.ace.v


# In[17]:


ss.ACEc.ace.v


# In[18]:


(1-ss.ACEc.f.v)*60


# In[54]:


ss.dae.ts.y[-1,ss.GENROU.te.a[4]]/ss.dae.ts.x[-1,ss.GENROU.omega.a[4]]*100-25 + ss.dae.ts.y[-1,ss.GENROU.te.a[3]]/ss.dae.ts.x[-1,ss.GENROU.omega.a[3]]*100-30 + ss.dae.ts.y[-1,ss.GENROU.te.a[1]]/ss.dae.ts.x[-1,ss.GENROU.omega.a[1]]*100-40 + ss.dae.ts.y[-1,ss.GENROU.te.a[0]]/ss.dae.ts.x[-1,ss.GENROU.omega.a[0]]*100-81.442 + 20*(ss.dae.ts.x[-1,ss.PVD1.Ipout_y.a[2]]*ss.dae.ts.y[-1,ss.PVD1.v.a[2]]*100-0.5)


# In[42]:


ss.dae.ts.y[-1,ss.GENROU.te.a[3]]/ss.dae.ts.x[-1,ss.GENROU.omega.a[3]]*100-30


# In[43]:


ss.dae.ts.y[-1,ss.GENROU.te.a[1]]/ss.dae.ts.x[-1,ss.GENROU.omega.a[1]]*100-40


# In[44]:


ss.dae.ts.y[-1,ss.GENROU.te.a[0]]/ss.dae.ts.x[-1,ss.GENROU.omega.a[0]]*100-81.442


# In[53]:


ss.dae.ts.x[-1,ss.PVD1.Ipout_y.a[11]]*ss.dae.ts.y[-1,ss.PVD1.v.a[11]]*100-0.5


# In[20]:


import matplotlib.pyplot as plt
plt.plot(ss.dae.ts.t,ss.dae.ts.x[:,ss.PVD1.Ipout_y.a[12]]*ss.dae.ts.y[:,ss.PVD1.v.a[12]]*100)
plt.xlabel("Time (s)")
plt.ylabel("Power output (MW)")


# In[10]:


import matplotlib.pyplot as plt
plt.plot(ss.dae.ts.t,ss.dae.ts.x[:,ss.PVD1.Ipout_y.a[12]]*ss.dae.ts.y[:,ss.PVD1.v.a[12]]*100)
plt.xlabel("Time (s)")
plt.ylabel("Power output (MW)")


# In[47]:


plt.plot(ss.dae.ts.t,ss.dae.ts.y[:,ss.PQ.bus.v]*100)
plt.xlabel("Time (s)")
plt.ylabel("Total load (MW)")


# In[45]:


ss.PQ.bus.v


# In[46]:


ss.PQ.Ppf.v


# In[35]:


print(ss.PQ.doc())


# In[21]:


import matplotlib.pyplot as plt
plt.plot(ss.dae.ts.t,ss.dae.ts.x[:,ss.PVD1.Iqout_y.a[2]]*ss.dae.ts.y[:,ss.PVD1.v.a[2]]*100)
plt.xlabel("Time (s)")


# In[15]:


import matplotlib.pyplot as plt
plt.plot(ss.dae.ts.t,ss.dae.ts.y[:,ss.PVD1.v.a[2]])
plt.xlabel("Time (s)")


# In[16]:


import matplotlib.pyplot as plt
plt.plot(ss.dae.ts.t,ss.dae.ts.y[:,ss.PVD1.Qsum.a[2]]*100)
plt.xlabel("Time (s)")


# In[ ]:


print()


# In[7]:


ss.TDS.plt.plot(ss.PVD1.Pext,
                a=(0, ),
                ytimes=100,
               ) 


# In[69]:


ss.dae.ts.x[:,ss.PVD1.Ipout_y.a[1]]


# In[17]:


ss.PVD1.DB_y


# In[72]:


ss.dae.ts.y[:,ss.PVD1.v.a[1]]


# In[75]:


ss.PVD1.v.a


# In[10]:


ss.ACEc.imva.v


# In[8]:


print(ss.ACEc.doc())


# In[33]:


ss.PVD1.Dfdbd.v


# In[112]:


print(ss.PVD1.doc())


# In[14]:


ss.dae.ts.y[:,ss.GENROU.te.a[0]]


# In[18]:


ss.dae.ts.x[:,ss.GENROU.omega.a]


# In[10]:


ss.GENROU.te


# In[18]:


help(ss.TDS.plt.plot)


# In[9]:


# obtain the system latest voltage magnitude: the last row in the voltage data
ss.dae.ts.y[-1,ss.Bus.v.a]


# In[21]:


ss.dae.ts.xy[:,ss.Bus.v.a[0]+ss.dae.n]


# In[34]:


ss.TDS.plt.plot(ss.Bus.v,
                a=(0,13),
                ylabel='Voltage (p.u.)'
               ) 


# In[18]:


ss.Bus.v.a[0]


# In[6]:


ss.dae.n


# In[7]:


Load_timeseries


# In[18]:


np.std(ss.dae.ts.y[:,ss.ACEc.f.a]*60)


# In[19]:


np.mean(ss.dae.ts.y[:,ss.ACEc.f.a]*60)


# In[13]:


#obtain the frequency timeseries data
np.std(ss.dae.ts.y[:,ss.ACEc.f.a]*60)


# In[14]:


np.mean(ss.dae.ts.y[:,ss.ACEc.f.a]*60)


# In[12]:


#obtain the ACE timeseries data
ss.dae.ts.y[:,ss.ACEc.ace.a]*100


# In[19]:


#obtain the timeseries bus voltage data
ss.dae.ts.y[-1,ss.Bus.v.a]


# In[11]:


len(ss.dae.ts.xy[:,i+ss.dae.n])


# In[25]:


ss.dae.ts.t

