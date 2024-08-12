import argparse
from datetime import datetime
import logging
import sys
import time
from time import perf_counter_ns
import traceback
from signal import SIGINT, signal, strsignal
from types import FrameType
import threading
import nidaqmx
import json
import nidaqmx.system
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import queue
import os
from pytz import timezone
from front_end.logwindow import *

def get_time():
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:16] + "\n"
    return time
class heat_stage_group():
    def __init__(self, config_file, temp,pos_path):
        self.heat_stage_id_ls = config_file
        self.heat_mode = False
        self.image_mode = True
        self.ao_port = "Dev3/ao0"
        self.temp = temp
        self.cancel = 0
        self.num_devices = len(self.heat_stage_id_ls)
        self.status=[0]*self.num_devices
        self.pos_path=pos_path
        self.heat_status=0

    def connect_heater_group(self):
        self.do_task = [None] * self.num_devices
        self.ai_task = [None] * self.num_devices
        self.dev_name=[None] * self.num_devices
        self.ao_task = nidaqmx.Task()
        self.ao_task.ao_channels.add_ao_voltage_chan(self.ao_port, min_val=0.0, max_val=5.0)
        self.ao_task.start()
        for i in range(self.num_devices):
            print(i)
            self.dev_name[i]=self.heat_stage_id_ls[i]['heat_stage']
            self.do_task[i] = nidaqmx.Task()
            self.ai_task[i] = nidaqmx.Task()
            do_channel = self.heat_stage_id_ls[i]['DAQ'] + '/' + self.heat_stage_id_ls[i]['do_port'] + '/' + \
                         self.heat_stage_id_ls[i]['do_line']
            ai_channel = self.heat_stage_id_ls[i]['DAQ'] + '/' + self.heat_stage_id_ls[i]['ai_line']
            self.do_task[i].do_channels.add_do_chan(do_channel)
            self.ai_task[i].ai_channels.add_ai_voltage_chan(ai_channel)
            self.do_task[i].write(self.image_mode)



    def disconnect_heater_group(self):
        self.ao_task.close()
        for i in range(self.num_devices):
            self.ai_task[i].close()
            self.do_task[i].close()

    def start_heat(self):
        self.ao_task.write(self.temp)
        for i in range(self.num_devices):
            self.do_task[i].write(self.heat_mode)
        txt=get_time()+"start heat" +"\n"
        print("start heat")
        self.write_log(txt)
        #add_fluidics_reagent(txt)

    def end_heat(self):
        self.ao_task.write(0.1)
        txt = get_time() + "End heat"+"\n"
        print("End heat")
        self.write_log(txt)
        #add_fluidics_reagent(txt)

    def heat_for_3min_single(self, i):
        try:
            temp = self.ai_task[i].read()
            name=self.dev_name[i]
            start_single = datetime.now()
            time_diff_single = 0
            while temp <= self.temp - 0.3 and time_diff_single <= 300 and self.cancel==0:
                time.sleep(5)
                time_diff_single = (datetime.now() - start_single).total_seconds()
                temp = self.ai_task[i].read()
                print(f"device {name} temp: {temp}")
                txt=get_time()+"device "+name+str(temp)+"\n"
                self.write_log(txt)
                with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                    fp.write(txt)
                fp.close()
            if time_diff_single >= 300 and temp <= self.temp - 0.5:
                print(f"Heating stage had an issue: Device {name} is off!")
                txt="Heating stage had an issue: Device "+name+" is off"+"\n"
                self.write_log(txt)
                update_error(txt)
                with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                    fp.write(txt)
                fp.close()
                self.do_task[i].write(self.image_mode)
                self.status[i] = 0
            else:
                print(f"start stable heat for 3 mins for Device {name}")
                txt=get_time()+"start stable heat for 3 mins for Device "+name+"\n"
                self.write_log(txt)
                with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                    fp.write(txt)
                fp.close()
                #add_fluidics_reagent(txt)
                start_heat = datetime.now()
                heat_time_diff = 0
                while heat_time_diff <= 180 and self.cancel == 0:
                    temp = self.ai_task[i].read()
                    txt = "device" + name + " temp: " + str(temp) + "\n"
                    with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                        fp.write(txt)
                    fp.close()
                    print("device" + name + " temp: " + str(temp))
                    heat_time_diff = (datetime.now() - start_heat).total_seconds()
                    time.sleep(10)
                self.do_task[i].write(self.image_mode)
                txt=get_time()+"Device "+name+" is done with heat successfully!"+"\n"
                #add_fluidics_reagent(txt)
                self.write_log(txt)
                self.status[i]=1

        except Exception as e:
            self.do_task[i].write(self.image_mode)
            self.result_queue.put((i, f"Error in device {name}: {str(e)}"))
            txt = get_time() + "Device " + name + " has error!" + "\n"
            self.write_log(txt)
            update_error(txt)

    def heat_for_3min(self):
        threads=[]
        self.start_heat()
        self.result_queue = queue.Queue()
        for i in range(self.num_devices):
            t = threading.Thread(target=self.heat_for_3min_single, args=(i,))
            t.start()
            threads.append(t)
            time.sleep(3)
        for t in threads:
            t.join()

        if sum(self.status)==1*self.num_devices:
            txt = get_time() +"All stages heated successfully"+"\n"
            self.write_log(txt)
            #add_fluidics_reagent(txt)
            self.heat_status=1
        elif sum(self.status)==0:
            txt = get_time() + "All stages has issue" + "\n"
            self.write_log(txt)
            #add_fluidics_reagent()
            self.heat_status = 0
        else:
            txt = get_time() + "One or more stages has issue" + "\n"
            self.write_log(txt)
            #add_fluidics_reagent()
            self.heat_status = 1
        self.end_heat()
        return

    def check_temp(self):
        for i in range(self.num_devices):
            value = self.ai_task[i].read()
            print(value)

    def write_log(self,txt):
        f = open(os.path.join(self.pos_path,"log.txt"), "a")
        f.write(txt)
        f.close()
