# -*- coding: utf-8 -*-
# TODO add 13Bus test feeder simulator
import cmath
import json
import math
import re
import os
import sys
import numpy
import helics as h
import opendssdirect as odd
#NEW
import pandas

PUBLICATIONS = {}
SUBSCRIPTIONS = {}

sys.path.append(os.getcwd().split('Distribution')[0]+'PyDSS')
sys.path.append(os.getcwd().split('Distribution')[0]+'PyDSS/PyDSS')

def countList(lst1, lst2): 
    return [sub[item] for item in range(len(lst2)) 
                      for sub in [lst1, lst2]] 

def get_value(pub,val_tmp):
    class_name = pub["element_type"]
    element_name = pub["element_name"]
    fn = pub["value"]
    fold = pub.get("fold", "sum")
    start_index = pub.get("start_index", 1) - 1
    end_index = pub.get("end_index", 0)

    odd.Circuit.SetActiveClass(class_name)
    odd.Circuit.SetActiveElement(element_name)

    assert (
        odd.CktElement.Name().lower() == f"{class_name}.{element_name}".lower()
    ), f"Got {odd.CktElement.Name()} but expected {class_name}.{element_name}"

    # v = getattr(odd.CktElement, fn)()
    v=val_tmp
    # print(start_index)
    # print(end_index)
    if end_index == 0:
        end_index = int(round(len(v) / 2))
    v = v[start_index:end_index]
    if fold == "sum":
        # print('Power from get value')
        # print(v)
        v = (sum(v[0 : len(v) : 2]), sum(v[1 : len(v) : 2]))
        # print('summed')
        # print(v)
    elif fold == "cavg":
        # print('voltages from get value')
        # print(v)
        vcl = [
            cmath.polar(complex(x, y))
            for x, y in zip(v[0 : len(v) : 2], v[1 : len(v) : 2])
        ]
        v = sum(c[0] for c in vcl) / len(vcl), sum(c[1] for c in vcl) / len(vcl)
        
        # print('averaged')
        # print(v)
    elif fold == "list":
        # return list
        pass
    else:
        raise NotImplementedError(f"Unknown fold type: {fold}")

    return v


def set_value(sub, value):
    class_name = sub["element_type"]
    element_name = sub["element_name"]
    fn = sub["value"]

    odd.Circuit.SetActiveClass(class_name)
    odd.Circuit.SetActiveElement(element_name)

    if class_name == "Vsource" and element_name == "source":
        assert (
            odd.CktElement.Name().lower() == f"{class_name}.{element_name}".lower()
        ), f"Got {odd.CktElement.Name()} but expected {class_name}.{element_name}"

        if value[0] != 0:
            odd.Vsources.PU(value[0] / (odd.Vsources.BasekV() * 1 * 1))
            odd.Vsources.AngleDeg(value[1])
    elif class_name == "Load" and fn == "Powers":
        odd.Loads.Name(element_name)
        odd.Loads.kW(value[0])
        odd.Loads.kvar(value[1])
    else:
        if odd.CktElement.Name().lower() == f"{class_name}.{element_name}".lower():
            getattr(odd.CktElement, fn)(value)
        else:
            print(
                f"Warning: Unable to find CktElement {class_name}.{element_name} and unable to set value ({value}) for `{fn}`"
            )


def main(filename,pydss_path,sim_path,sim_file):
    with open(filename) as f:
        data = json.loads(f.read())

    federate_name = data["name"]
    filename = data["filename"]
    total_time = data["total_time"]
    step_time = data["step_time"]
    subscriptions = data["subscriptions"]
    publications = data["publications"]
    dir_multi=data["direction_multiplier"]
    ami_nodes=data['AMI_nodes']
    g2020_nodes=data['Grid2020_nodes']

    # odd.run_command(f"Redirect {filename}")

    file_tmp=open(os.getcwd()+'/DSSfiles/Master.dss','rt')
    contents=file_tmp.read()
    file_tmp.close()
    basekVval=float(re.findall('basekV=[\d.]*',contents)[0].split('=')[1])
    print('Base kV being used: '+str(basekVval),flush=True)

    #NEW
    # Get list of load data
    list_of_load_names=[]
    list_of_load_buses=[]
    load_names=[]
    load_names_master=[]
    load_phases=[]
    load_bus_names=[]
    load_kW_peak=[]
    load_kvar_peak=[]
    try:
        with open(os.getcwd()+'/DSSfiles/Loads.dss','rt') as fp:
            lines = fp.read().splitlines()
        for line in lines:
            if "Load" in line and '!' not in line:
                print(line,flush=True)
                tmp=line.split(' ')
                tmp2=tmp[1].split('.')
                load_names_master.append(tmp2[1])
                load_phases.append(int(re.findall('hases=[1-3]',line)[0].split('=')[1]))
                load_kW_peak.append(re.findall('kW=[-e.0-9]*',line)[0].split('=')[1])
                load_kvar_peak.append(re.findall('kvar=[-e.0-9]*',line)[0].split('=')[1])
                #load_bus_names_master.append(re.findall('bus1=[.a-zA-Z0-9_-]*',line)[0].split('=')[1].split('.')[0])
                tmp=re.findall('bus1=[.a-zA-Z0-9_-]*',line)[0].split('=')[1].split('.')
                for k in range(0,len(tmp)-1):
                    load_bus_names.append(tmp[0]+'.'+str(tmp[k+1]))
                    load_names.append(tmp2[1])
        df=pandas.read_csv(os.getcwd()+'/DSSfiles/' + federate_name + '_load_4sec.csv',index_col=0)
        load_col_names=df.columns
    except:
        print('No loads in this feeder')

    fedinfo = h.helicsCreateFederateInfo()

    h.helicsFederateInfoSetCoreName(fedinfo, f"{federate_name}")
    h.helicsFederateInfoSetCoreTypeFromString(fedinfo, "zmq")
    h.helicsFederateInfoSetCoreInitString(fedinfo, "--federates=1")
    h.helicsFederateInfoSetTimeProperty(fedinfo, h.helics_property_time_delta, 1.0)

    fed = h.helicsCreateCombinationFederate(f"{federate_name}", fedinfo)
    print(f"{federate_name}: Combination federate created",flush=True)
    

    for k, v in publications.items():
        pub = h.helicsFederateRegisterTypePublication(fed, v["topic"], "complex", "")
        PUBLICATIONS[k] = pub
    for k, v in subscriptions.items():
        sub = h.helicsFederateRegisterSubscription(fed, v["topic"], "")
        SUBSCRIPTIONS[k] = sub

    epid = h.helicsFederateRegisterGlobalEndpoint(fed, federate_name+"_ep", "")

    h.helicsFederateEnterExecutingMode(fed)
    print(f"{federate_name}: Entering execution mode",flush=True)

    currenttime = 0.0
    x = {}  # can I do nothing?
    #NEW
    for i,n in enumerate(load_names_master):
        x['Load.'+n]={}
        x['Load.'+n]['kW']=df[load_col_names[i]][int(currenttime/4)]*float(load_kW_peak[i])
        x['Load.'+n]['kvar']=df[load_col_names[i]][int(currenttime/4)]*float(load_kvar_peak[i])

    # pydss_path='/Users/ikrad/Documents/GitHub/PyDSS'  
    # sim_path='/Users/ikrad/Desktop/reduced-heco-ikrad-pydss2/HECO_Reduced_Model/Distribution/KAHE1_1pydss/PyDSS Scenarios'
    # sim_file='igms_test.toml'
    sys.path.append(pydss_path)
    sys.path.append(os.path.join(pydss_path, 'PyDSS'))
    from pyDSS import instance as dssInstance
    a = dssInstance()
    sim_args = a.update_scenario_settigs(os.path.join(sim_path, sim_file))
    dssInstance = a.create_dss_instance(sim_args)

    for request_time in range(0, total_time, step_time):

        while currenttime < request_time:
            currenttime = h.helicsFederateRequestTime(fed, request_time)

        

        # odd.run_command(f"Solve t={currenttime}")
        # print('updated values command',flush=True)
        # print(x,flush=True)
        results = dssInstance.RunStep(currenttime, x)
        #NEW
        x={}
        # print('PyDSS results')
        # print(results)

        #NEW
        for i,n in enumerate(load_names_master):
            x['Load.'+n]={}
            x['Load.'+n]['kW']=df[load_col_names[i]][int(currenttime/4)]*float(load_kW_peak[i])
            x['Load.'+n]['kvar']=df[load_col_names[i]][int(currenttime/4)]*float(load_kvar_peak[i])

        for key, pub in PUBLICATIONS.items():
            unit=''
            if publications[key]['value'] == 'Powers':
                val_tmp1=results[publications[key]['element_type']+'.'+publications[key]['element_name']]['Powers']['E']['value']
                val_tmp1 = [x * int(dir_multi) for x in val_tmp1]
                val_tmp2=results[publications[key]['element_type']+'.'+publications[key]['element_name']]['Powers']['O']['value']
                val_tmp2 = [x * int(dir_multi) for x in val_tmp2]
                unit='kW,kVAr'
            if publications[key]['value'] == 'Voltages':
                val_tmp1=results[publications[key]['element_type']+'.'+publications[key]['element_name']]['Voltages']['E']['value']
                val_tmp2=results[publications[key]['element_type']+'.'+publications[key]['element_name']]['Voltages']['O']['value']
            val_tmp=countList(val_tmp1,val_tmp2)
            val = get_value(publications[key],val_tmp)
            if publications[key]['value'] == 'Voltages':
                val=((val[0]/1000*cmath.sqrt(3)).real,val[1])

            print(f"Sending {val} {unit} at time {currenttime} from {publications[key]['element_type']} {publications[key]['element_name']} in feeder {federate_name}",flush=True)
            typ = "complex"
            if typ == "complex":
                h.helicsPublicationPublishComplex(pub, val[0], val[1])
            else:
                raise NotImplementedError(f"Unknown type of data {typ}")

        for key, sub in SUBSCRIPTIONS.items():
            val = h.helicsInputGetComplex(sub)
            unit=''
        #     set_value(subscriptions[key], val)
            if subscriptions[key]['value']=='Powers':
                x[subscriptions[key]['element_type']+'.'+subscriptions[key]['element_name']]={'kW':val[0],'kvar':val[1]}
                unit='kW,kVar'
            if subscriptions[key]['value']=='Voltage':
                # if currenttime < 16.1:
                #     val=[basekVval,0]
                # basekVval=43.8
                tmp1=cmath.sqrt(val[0]*val[0]+val[1]*val[1]).real
                unit='kV'
                try:
                    tmp2=(cmath.tan(val[1]/val[0])*180/cmath.pi).real
                except:
                    tmp2=0
                x[subscriptions[key]['element_type']+'.'+subscriptions[key]['element_name']]={'pu':tmp1/basekVval,'AngleDeg':tmp2}
            print(f"Received {val} {unit} at time {currenttime} for {subscriptions[key]['element_type']} {subscriptions[key]['element_name']} in feeder {federate_name}",flush=True)
            
        if currenttime < 1:
            x={}
        # print(x)

        # Send data to controller stack
        if len(ami_nodes) > 0:
            NodeNames=results['Circuit.network_'+federate_name]['YNodeOrder']['A']['value']
            V=results['Circuit.network_'+federate_name]['YNodeVArray']['A']['value']
            I=results['Circuit.network_'+federate_name]['YCurrents']['A']['value']
            for n in range(0,len(ami_nodes)):
                idx=NodeNames.index(ami_nodes[n].upper())
                busV=V[idx*2:idx*2+2]
                busV=busV[0]+1j*busV[1]
                busI=I[idx*2:idx*2+2]
                busI=busI[0]+1j*busI[1]
                busS=busV*numpy.conj(busI)
                busP=numpy.real(busS)
                busQ=numpy.imag(busS)
                busVmag=numpy.abs(busV)
                control_message={}
                control_message[ami_nodes[n]]={}
                control_message[ami_nodes[n]]['data_type']='AMI'
                control_message[ami_nodes[n]]['DSS_idx']=idx
                control_message[ami_nodes[n]]['V']=busVmag
                control_message[ami_nodes[n]]['P']=busP
                control_message_str=json.dumps(control_message)
                # h.helicsEndpointSendMessageRaw(epid, "GoSolarStack_"+federate_name+"_endpoint", f"Sending {busVmag} kV and {busP} kW for node {ami_nodes[n]} at time {currenttime}")
                h.helicsEndpointSendMessageRaw(epid, "GoSolarStack_"+federate_name+"_endpoint",control_message_str)
                # print(f'sending message to endpoint at {currenttime}',flush=True)
        if len(g2020_nodes) > 0:
            NodeNames=results['Circuit.network_'+federate_name]['YNodeOrder']['A']['value']
            V=results['Circuit.network_'+federate_name]['YNodeVArray']['A']['value']
            I=results['Circuit.network_'+federate_name]['YCurrents']['A']['value']
            for m in range(0,len(g2020_nodes)):
                idx=NodeNames.index(g2020_nodes[m].upper())
                busV=V[idx*2:idx*2+2]
                busV=busV[0]+1j*busV[1]
                busI=I[idx*2:idx*2+2]
                busI=busI[0]+1j*busI[1]
                busS=busV*numpy.conj(busI)
                busP=numpy.real(busS)
                busQ=numpy.imag(busS)
                busVmag=numpy.abs(busV)
                control_message={}
                control_message[g2020_nodes[m]]={}
                control_message[g2020_nodes[m]]['data_type']='G2020'
                control_message[g2020_nodes[m]]['DSS_idx']=idx
                control_message[g2020_nodes[m]]['V']=busVmag
                control_message[g2020_nodes[m]]['P']=busP
                control_message[g2020_nodes[m]]['Q']=busQ
                control_message_str=json.dumps(control_message)
                # h.helicsEndpointSendMessageRaw(epid, "GoSolarStack_"+federate_name+"_endpoint", f"Sending {busVmag} kV and {busP} kW for node {ami_nodes[n]} at time {currenttime}")
                h.helicsEndpointSendMessageRaw(epid, "GoSolarStack_"+federate_name+"_endpoint",control_message_str)
                # print(f'sending message to endpoint at {currenttime}',flush=True)

        while h.helicsEndpointHasMessage(epid):
            m = h.helicsEndpointGetMessageObject(epid)
            message_recv = h.helicsMessageGetString(m)
            received_data=json.loads(message_recv)
            print(received_data,flush=True)


    h.helicsFederateFinalize(fed)
    print(f"{federate_name}: Federate finalized",flush=True)

    h.helicsFederateFree(fed)
    h.helicsCloseLibrary()


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="json filename that describes OpenDSS feeder")
    parser.add_argument("pydss_path", help="path to cloned PyDSS directory")
    parser.add_argument("sim_path", help="path to PyDSS project scenario directory")
    parser.add_argument("sim_file", help="path to toml simulation file")
    args = parser.parse_args()

    main(args.filename,args.pydss_path,args.sim_path,args.sim_file)
