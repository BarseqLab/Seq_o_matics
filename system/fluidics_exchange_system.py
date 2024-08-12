#!/usr/bin/env python
# coding: utf-8

# In[1]:

from device.Pump import IsmatecPumpDevice
from device.Selector import ElveflowMuxDevice
from device.Relay import KmtronicRelayCh4
from device.Heatingstage import heat_stage_group
import threading
import os
import json
import time
import numpy as np
from front_end.logwindow import *
from pytz import timezone
from datetime import datetime
import shutil
   

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END='\033[0m'


def get_time():
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:19] + "\n"
    return time

class FluidicSourceInfo(object):
    def __init__(self, name="sourceName", indexInComponentList=None, hardwareIndices=None):
        self.name = name
        self.index = indexInComponentList
        self.hardwareId = hardwareIndices

class FluidicsConstants():
    pumpBlockDeviceChannel=1
    vacuumChannel=2
    chamberSelectChannel= 0
    sinkBased=True
    pumpRate = 1.0
    vol = 1e-4
    bufferseconds = 1
    bufferms = 5*bufferseconds

    PUMP_BLOCK_OPEN_STATE = True
    PUMP_BLOCK_CLOSED_STATE = not PUMP_BLOCK_OPEN_STATE

    SELECT_BYPASS_STATE = True
    SELECT_CHAMBER_STATE = not SELECT_BYPASS_STATE

    VACUUM_OPEN_STATE = True
    VACUUM_CLOSED_STATE = not VACUUM_OPEN_STATE
    System_device=['pumpDevice','FluidicSelector','pumpBlockDevice']






class FluidicSystem():
    def __init__(self,system_path,pos_path):
        self.system_path = system_path
        with open(os.path.join(system_path,"config_file", "IsmatecPumpDevice_pump.json"), 'r') as r:
            self.pump1_cfg = json.load(r)
        with open(os.path.join(system_path,"config_file", "ElveflowMuxDevice_selector.json"), 'r') as r:
            self.selector_cfg = json.load(r)
        with open(os.path.join(system_path,"config_file", 'Fluidics_Reagent_Components.json'), 'r') as r:
            self.configComponents = json.load(r)
        with open(os.path.join(system_path,"config_file", "Heat_stage.json"), 'r') as r:
            self.Heater_cfg = json.load(r)
        with open(os.path.join(self.system_path,"config_file", "KMtronic_relay.json"), 'r') as r:
            self.Relay_cfg = json.load(r)

        self.start_fluidics =1
        self.sourceInfoList = []
        #self.components = []
        self.currentSpeed = 0.0
        self.currentSource = None
        self.sequenceStatus=0
        self.last_sequenceStatus = -2
        self.sequenceIndex = 0
        self.config_fluidics_sequences = {}
        self.sequenceStateEndTime = 0
        self.pos_path=pos_path
        self.cycle_done=0
        self.start_image=0
        self.mlToPump=0
        self.disconnect_device=0
        self.waiting_time=3
        self.heat_temp=5.7
        self.chamber1=0
        self.chamber2=1
        self.chamber3=2
        with open(os.path.join(self.system_path, "reagent_sequence_file", 'Fluidics_sequence_flush_all.json'), 'r') as r:
            self.FLUSH_ALL_SEQUENCE = json.load(r)
        with open(os.path.join(self.system_path, "reagent_sequence_file", 'Fluidics_sequence_fill_all.json'), 'r') as r:
            self.Fill_ALL_SEQUENCE = json.load(r)




    def write_log(self, txt):
        f = open(os.path.join(self.pos_path, "log.txt"), "a")
        f.write(txt)
        f.close()
    def config_pump(self):
        self.pump = IsmatecPumpDevice(self.pump1_cfg[0])
        self.pump.initialize()
        self.pump.PumpDisconnect()
    def config_heater(self):
        self.Heatingdevice=heat_stage_group(self.Heater_cfg,4,self.pos_path)
        self.Heatingdevice.connect_heater_group()
        self.Heatingdevice.disconnect_heater_group()

    def connect_heater(self):
        self.Heatingdevice = heat_stage_group(self.Heater_cfg, self.heat_temp, self.pos_path)
        self.Heatingdevice.connect_heater_group()
    def disconnect_heater(self):
        self.Heatingdevice.disconnect_heater_group()
    def connect_pump(self):
        self.pump  = IsmatecPumpDevice(self.pump1_cfg[0])
        self.pump.initialize()

    def is_pump_running(self):
        self.pump.isPumpRunning()
        
    def disconnect_pump(self):
        self.pump.PumpDisconnect()
        
    def config_selector(self):
        self.sourceInfoList = []
        for i, j in enumerate(self.configComponents):
            if j["infostring"] in 'source':
                sourceInfoi = FluidicSourceInfo(j["name"], indexInComponentList=i, hardwareIndices=j["address"])
                self.sourceInfoList.append(sourceInfoi)
        self.connect_selector()
        self.setSource("1")
        self.setSource("10")
        self.disconnect_selector()



    def connect_selector(self):
        self.sourceInfoList = []
        for i, j in enumerate(self.configComponents):
            if j["infostring"] in 'source':
                sourceInfoi = FluidicSourceInfo(j["name"], indexInComponentList=i, hardwareIndices=j["address"])
                self.sourceInfoList.append(sourceInfoi)
        self.selector1_1 = ElveflowMuxDevice(self.selector_cfg[0]['port'])
        self.selector1_1.initialize()
        self.selector1_2 = ElveflowMuxDevice(self.selector_cfg[1]['port'])
        self.selector1_2.initialize()
        self.selector_passthrough = self.sourceInfoList[9]

    def disconnect_selector(self):
        self.selector1_1.elveflowmux.disconnect()
        self.selector1_2.elveflowmux.disconnect()


    def config_relay(self):
        self.relay=KmtronicRelayCh4(self.Relay_cfg[0]['port'])
        self.relay.on_connect_requested()
        self.relay.quit()
    def connect_relay(self):
        self.relay=KmtronicRelayCh4(self.Relay_cfg[0]['port'])
        self.relay.on_connect_requested()
        self.relay.change_relay_state(0, True)
    def disconnect_relay(self):
        self.relay.quit()


    
    def isPumpRunning(self):
        return self.pump.isPumpRunning()
    def Get_Response(self):
        try:
            self.pump.GetResponse()
        except:
            txt=get_time()+"pump is not connected correctly \n"
            print("pump is not connected correctly \n")
            update_error(txt)
            self.write_log(txt)
        return 
    
    def select_bypass(self,SELECT_BYPASS_STATE):
        self.relay.change_relay_state(self.chamber1, SELECT_BYPASS_STATE)
        self.relay.change_relay_state(self.chamber2, SELECT_BYPASS_STATE)
        self.relay.change_relay_state(self.chamber3, SELECT_BYPASS_STATE)

    def select_chamber(self,SELECT_CHAMBER_STATE):
        self.relay.change_relay_state(self.chamber1, SELECT_CHAMBER_STATE)
        self.relay.change_relay_state(self.chamber2, SELECT_CHAMBER_STATE)
        self.relay.change_relay_state(self.chamber3, SELECT_CHAMBER_STATE)
    
    def stopPumping(self):
        self.pump.stopPump()

    
    def startPumping(self):
        self.pump.startPump()
    
    def cancelSequence(self):
        self.stopPumping()
        self.Heatingdevice.cancel=1
        self.sequenceStatus = -1
        self.sequenceIndex = 0
        self.cycle_done = 1
        self.start_image=0


    def setPumpRate(self,rate):
        if rate > 0.:
            self.pump.setFlowRate_ml_per_min(rate)
    
    def pumpVol(self,vol,rate):
        self.pump.pumpVolume(vol,rate)

    def setSource(self, sourceName):
        selectList = []
        sourceName = str(sourceName)
        txt = "setSource : " + sourceName + "\n"
        add_fluidics_reagent(txt)
        print("setSource : " + sourceName)
        self.write_log(txt)
        for si in self.sourceInfoList:
            if si.name == sourceName:
                selectList.append(si)

        if len(selectList) > 1:
            txt = "redundant sourceNames!Did not setsource\n"
            update_error(txt)
            self.write_log(txt)
            print("redundant sourceNames!")
            print("Did not setsource " + sourceName + " !!")
            return
        if int(sourceName)>9:
            self.sourceInfoList = []
            for i, j in enumerate(self.configComponents):
                if j["infostring"] in 'source':
                    sourceInfoi = FluidicSourceInfo(j["name"], indexInComponentList=i, hardwareIndices=j["address"])
                    self.sourceInfoList.append(sourceInfoi)
            self.selector1_1.selectSource(self.sourceInfoList[9])
            selectList[0].hardwareId = [int(sourceName) - 9]
            self.selector1_2.selectSource(selectList[0])
            self.currentSource = selectList[0]
            txt = "name:" + selectList[0].name + "\n"
            print(txt)
        else:

            self.selector1_1.selectSource(selectList[0])
            self.currentSource = selectList[0]
            txt = "name:" + selectList[0].name + "\n"
            print(txt)




    def loadSequence(self,fluidicsSequence):
        self.fluidSequence=fluidicsSequence

        
    def updateStatus(self):
        if self.sequenceStatus == -1:
            if self.sequenceStatus != self.last_sequenceStatus:
                txt=get_time()+"Status Check : fluidics sequence was cancelled \n"
                self.write_log(txt)
                add_fluidics_status(txt)
                print(bcolors.OKBLUE+"Status Check: fluidics sequence cancelled"+bcolors.END)
                self.last_sequenceStatus = self.sequenceStatus
                self.last_sequenceStatus=-1
            return
        elif self.sequenceStatus == -2:
            txt=get_time()+"Status Check:sequence finished successfully\n"
            add_fluidics_status(txt)
            self.write_log(txt)
            print(bcolors.OKBLUE+" Status Check:sequence finished successfully"+bcolors.END)
            self.last_sequenceStatus = -2
        elif self.sequenceStatus == 1:
            pass
            return
        
    def startSequence(self):
        if self.sequenceStatus == 1:
            txt="System is still running! \n"
            print('System is still running!')
            self.write_log(txt)
            add_fluidics_status(txt)
            return
        self.cycle_done = 0
        self.start_image=0
        self.idx=100/len(self.fluidSequence)
        update_process_bar(0)
        update_process_label("Fluidics exchanging")
        self.runSequence()

    def finishSequence(self):
        self.cycle_done = 1
        self.start_image=1
        self.sequenceIndex = 0
        self.sequenceStatus = 0
        self.last_sequenceStatus=-2



    def runSequence(self):
        if self.sequenceStatus == -1:
            print("system canceled (from runsequence tread)!")
            update_process_bar(0)
            update_process_label("Process")
            self.updateStatus()
            return
        if self.pump.isPumpRunning() == 1:
            txt = "System is still running!\n"
            print("pump still running. wait ")
            self.write_log(txt)
            add_fluidics_reagent(txt)
            self.run_sequence_thread = threading.Timer(0, self.runSequence)
            self.run_sequence_thread.start()
            return

        if self.sequenceIndex >= len(self.fluidSequence):
            self.sequenceStatus=-2
            txt=get_time()+"sequence finished successfully!"+"\n"
            print(txt)
            self.write_log(txt)
            update_process_bar(0)
            update_process_label("Process")
            add_fluidics_reagent(get_time()+"sequence finished successfully!"+"\n")
            self.long_heat=0
            self.cycle_done = 1
            self.start_image=1
            self.sequenceIndex = 0
            self.sequenceStatus = 0
            self.last_sequenceStatus = -2
            time.sleep(5)
            return

        sequenceIndex = self.sequenceIndex
        sequenceState = self.fluidSequence[sequenceIndex]
        self.idx =self.idx+ 100 / len(self.fluidSequence)
        update_process_bar(self.idx)
        self.sequenceStatus = 1

        if sequenceState["device"] =="pump" :
            pumpRate=sequenceState["flow_rate"]
            expectedTime = int(60 * (sequenceState["volume"] / pumpRate))
            txt = "timer  = " + str(expectedTime + FluidicsConstants.bufferms) + "\n"
            add_fluidics_reagent(txt)
            self.write_log(txt)
            self.setPumpRate(pumpRate)
            self.setSource(sequenceState["source"])
            add_fluidics_reagent("name: "+sequenceState["Solution name"]+"\n")
            print(sequenceState["source"])
            txt=get_time()+"current in step" + str(sequenceIndex+1)+" pumping: "+sequenceState["Solution name"]+" \n"
            add_fluidics_reagent(txt)
            self.write_log(txt)
            print(bcolors.WARNING + txt+bcolors.END)
            self.pumpVol(sequenceState["volume"],pumpRate)
            start=datetime.now()
            time_diff=0
            self.updateStatus()
            self.sequenceIndex += 1
            while time_diff<=expectedTime + FluidicsConstants.bufferms:
                if self.sequenceStatus==-1:
                    break
                time.sleep(2)
                time_diff=(datetime.now()-start).total_seconds()
            if self.sequenceStatus != -1:
                self.run_sequence_thread = threading.Timer(self.waiting_time, self.runSequence)
                self.run_sequence_thread.start()

        elif sequenceState["device"] =="heat_device" :
            txt=get_time()+"current in step" + str(sequenceIndex+1)+" heating: "+str(sequenceState["time"])+" seconds"+"\n"
            add_fluidics_reagent(txt)
            self.write_log(txt)
            print(bcolors.WARNING + txt+bcolors.END)
            self.Heatingdevice.heat_for_3min()
            self.sequenceIndex += 1
            self.updateStatus()
            if self.Heatingdevice.cancel==1 :
                txt = get_time() + "Heater is cancelled "+ "\n"
                add_fluidics_reagent(txt)
                self.write_log(txt)
                print(bcolors.WARNING + txt + bcolors.END)
            elif self.Heatingdevice.heat_status==0:
                txt = get_time() + "Heater is wrong " + "\n"
                add_fluidics_reagent(txt)
                self.write_log(txt)
                print(bcolors.WARNING + txt + bcolors.END)
                return
            else:
                self.run_sequence_thread = threading.Timer(self.waiting_time, self.runSequence)
                self.run_sequence_thread.start()

        elif sequenceState["device"] == "wait":
            txt = get_time() + "Incubating for " + str(sequenceState["time"])+" seconds."+"\n"
            add_fluidics_reagent(txt)
            self.write_log(txt)
            print(bcolors.WARNING + txt + bcolors.END)
            time_diff = 0
            start = datetime.now()
            self.updateStatus()
            self.sequenceIndex += 1
            expectedTime=sequenceState["time"]
            while time_diff <= expectedTime + FluidicsConstants.bufferms:
                if self.sequenceStatus == -1:
                    break
                time.sleep(2)
                time_diff = (datetime.now() - start).total_seconds()
            if self.sequenceStatus != -1:
                self.run_sequence_thread = threading.Timer(self.waiting_time, self.runSequence)
                self.run_sequence_thread.start()
        else:
            self.setSource(sequenceState["source"])
            self.sequenceIndex += 1
            self.run_sequence_thread = threading.Timer(0, self.runSequence)
            self.run_sequence_thread.start()
        return

    def find_protocol(self,type):
        if "geneseq" in type and "01" in type:
            with open(os.path.join("reagent_sequence_file", "Fluidics_sequence_geneseq01.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_geneseq01.json protocol!\n"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_geneseq01.json")):
                shutil.copyfile(os.path.join("reagent_sequence_file", "Fluidics_sequence_geneseq01.json"), os.path.join(self.pos_path, "Fluidics_sequence_geneseq01.json"))
        elif "bcseq" in type and "01" in type:
            with open(os.path.join("reagent_sequence_file", "Fluidics_sequence_bcseq01.json"), 'r') as r:
                protocol = json.load(r)
            txt=get_time()+"load Fluidics_sequence_bcseq01.json protocol!\n"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_bcseq01.json")):
                shutil.copyfile(os.path.join( "reagent_sequence_file", "Fluidics_sequence_bcseq01.json"), os.path.join(self.pos_path, "Fluidics_sequence_bcseq01.json"))
        elif "geneseq" in type  and "01" not in type:
            with open(os.path.join( "reagent_sequence_file", "Fluidics_sequence_geneseq02+.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_geneseq02+.json protocol!\n"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_geneseq02+.json")):
                shutil.copyfile(os.path.join( "reagent_sequence_file", "Fluidics_sequence_geneseq02+.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_geneseq02+.json"))
        elif "bcseq" in type and "01" not in type:
            with open(os.path.join( "reagent_sequence_file", "Fluidics_sequence_bcseq02+.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_bcseq02+.json protocol!\n"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_bcseq02+.json")):
                shutil.copyfile(os.path.join( "reagent_sequence_file", "Fluidics_sequence_bcseq02+.json"), os.path.join(self.pos_path, "Fluidics_sequence_bcseq02+.json"))
        elif "user_defined" in type:
            with open(os.path.join("reagent_sequence_file","Fluidics_sequence_user_defined.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_user_defined protocol\n!"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path,"Fluidics_sequence_user_defined.json")):
                shutil.copyfile(os.path.join("reagent_sequence_file","Fluidics_sequence_user_defined.json"), os.path.join(self.pos_path, "Fluidics_sequence_user_defined.json"))

        elif "HYB" in type and "rehyb" not in type:
            with open(os.path.join("reagent_sequence_file", "Fluidics_sequence_HYB.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_HYB protocol\n!"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_HYB.json")):
                shutil.copyfile(os.path.join( "reagent_sequence_file", "Fluidics_sequence_HYB.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_HYB.json"))
        elif "add_gene_primer" in type and "rehyb" not in type:
            with open(os.path.join( "reagent_sequence_file", "Fluidics_sequence_add_gene_primer.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_add_gene_primer protocol\n!"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_add_gene_primer.json")):
                shutil.copyfile(os.path.join( "reagent_sequence_file", "Fluidics_sequence_add_gene_primer.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_add_gene_primer.json"))
        elif "add_bc_primer" in type and "rehyb" not in type:
            with open(os.path.join("reagent_sequence_file", "Fluidics_sequence_add_bc_primer.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_add_bc_primer protocol\n!"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_add_bc_primer.json")):
                shutil.copyfile(os.path.join( "reagent_sequence_file", "Fluidics_sequence_add_bc_primer.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_add_bc_primer.json"))


        elif "HYB" in type and "rehyb" in type:
            with open(os.path.join( "reagent_sequence_file", "Fluidics_sequence_HYB_rehyb.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_HYB_rehyb protocol\n!"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_HYB_rehyb.json")):
                shutil.copyfile(os.path.join("reagent_sequence_file", "Fluidics_sequence_HYB_rehyb.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_HYB_rehyb.json"))
        elif "add_gene_primer" in type and "rehyb"  in type:
            with open(os.path.join("reagent_sequence_file", "Fluidics_sequence_add_gene_primer_rehyb.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_add_gene_primer_rehyb protocol\n!"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_add_gene_primer_rehyb.json")):
                shutil.copyfile(os.path.join( "reagent_sequence_file", "Fluidics_sequence_add_gene_primer_rehyb.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_add_gene_primer_rehyb.json"))
        elif "add_bc_primer" in type and "rehyb"  in type:
            with open(os.path.join("reagent_sequence_file", "Fluidics_sequence_add_bc_primer_rehyb.json"), 'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_add_bc_primer_rehyb protocol\n!"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_add_bc_primer_rehyb.json")):
                shutil.copyfile(os.path.join( "reagent_sequence_file", "Fluidics_sequence_add_bc_primer_rehyb.json"),
                                os.path.join(self.pos_path, "Fluidics_sequence_add_bc_primer_rehyb.json"))
        elif "strip" in type:
            with open(os.path.join( "reagent_sequence_file", "Fluidics_sequence_strip.json"),
                      'r') as r:
                protocol = json.load(r)
            txt = get_time() + "load Fluidics_sequence_strip protocol\n!"
            print(txt)
            add_fluidics_reagent(txt)
            self.write_log(txt)
            if not os.path.exists(os.path.join(self.pos_path, "Fluidics_sequence_strip.json")):
                shutil.copyfile(
                    os.path.join( "reagent_sequence_file", "Fluidics_sequence_strip.json"),
                    os.path.join(self.pos_path, "Fluidics_sequence_strip.json"))

        return protocol










# In[ ]:



