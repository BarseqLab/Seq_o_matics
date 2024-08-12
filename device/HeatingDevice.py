import serial
import numpy as np
from datetime import datetime
import os
import time
from pytz import timezone
from front_end.logwindow import *
#%%
def get_time():
    time_now = timezone('US/Pacific')
    time = str(datetime.now(time_now))[0:16] + "\n"
    return time

class heating_device():
    def __init__(self, com,pos_path):
        self.com = com
        self.turn_off_request=0
        self.finish=1
        self.pos_path=pos_path
        self.cancel = 0

    def connect_heater(self):
        self.heater = serial.Serial(self.com, 9600, timeout=2)

    def disconnect_heater(self):
        self.heater.close()
        print("disconnect_heater,close the port!")

    def start_heater(self):
        self.heater.write(b'GUN\r\n')
        HeaterRead = self.heater.readline().decode('utf-8').strip()
        if HeaterRead=='Gun on':
            self.heater_on = 1
            print("heater is on")
        else:
            print("turn on heater status is wrong")
    def stop_heater(self):
        self.heater.write(b'GUN\r\n')
        HeaterRead = self.heater.readline().decode('utf-8').strip()
        if HeaterRead=='Gun off':
            self.heater_on = 0
            print("heater is off")
        else:
            print("turn off heater status is wrong")


    def emergency_stop(self):
        self.heater.write(b'ESTOP\r\n')

    def check_temp(self):
        self.heater.write(b'TEMP\r\n')
        s = str(self.heater.readline().decode('utf-8').strip())
        return s
    #
    def start_heating(self,timer,low_temp,high_temp):
        start = datetime.now()
        time_diff = 0
        timer_time = []
        try:
            with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                fp.write("lower bound: "+str(low_temp) + " higher bound: "+str(high_temp)+'\n')
            fp.close()
        except:
            pass
        self.start_heater()
        if self.heater_on == 1:
            while time_diff<=1200 and self.cancel==0 :
                s = self.check_temp()
                with open(os.path.join(self.pos_path, 'temp.txt'), 'a') as fp:
                    fp.write(str(s) + '\n')
                fp.close()
                if len(timer_time)>=timer/2:
                    print("Heat is enough")
                    break
                else:
                    try:
                        temp = np.round(float(s))
                        print(temp)
                        if temp >= low_temp:
                            timer_time.append(1)
                        if self.heater_on == 1 and temp >= high_temp:
                            self.stop_heater()
                        elif self.heater_on == 0 and temp <= low_temp:
                            self.start_heater()
                        else:
                            pass
                    except Exception as e:
                        print(e)
                        pass
                    time.sleep(2)
                    now = datetime.now()
                    time_diff = (now - start).total_seconds()
            if self.cancel==1:
                txt=get_time() + "break while loop, heater cancelled!"+"\n"
                add_fluidics_reagent(txt)
                self.write_log(txt)
                print("break while loop, heater cancelled!")
            if self.heater_on == 1:
                print("I am here to finally close heater")
                self.stop_heater()
                self.heat_status = 1
            if len(timer_time)<timer/2:
                self.heat_status=0
                print("Doesn't have enough heat time")
            else:
                self.heat_status = 1
                print("The heat is complete")
                txt = get_time() + "The heat is complete" + "\n"
                add_fluidics_reagent(txt)
                self.write_log(txt)
        else:
            self.heat_status = 0


    def write_log(self,txt):
        f = open(os.path.join(self.pos_path,"log.txt"), "a")
        f.write(txt)
        f.close()










