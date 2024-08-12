#!/usr/bin/python
# ----------------------------------------------------------------------------------------
# The basic I/O class for a Ismatec IPC peristaltic pump
# ----------------------------------------------------------------------------------------
# George Emanuel with modifications by Jeff Moffitt, Rusty Nicovich
# 05/15/17
# rustyn@alleninstitute.org

# Brian Long brianl@alleninstitute.org
# add defaultRate attribute
# 2017
# 2020 modify for python3
# ----------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------
# Import
# ----------------------------------------------------------------------------------------
import serial, struct, time, collections
import numpy as np
from front_end.logwindow import *
class TimeoutError(Exception):
    pass



acknowledge = '\x06'
start = '\x0A'
stop = '\x0D'

#expectedPumpID_string = 'IPC 405'


# Outstanding issue with pump tubing diameter.  Not all are accepted when input using "+----" command.
# Acceptable values:
#    
#    1.02 mm
#    1.14 mm
#    1.52 mm ~ 1/16th inch
#    3.17 mm ~ 1/8th inch

# ----------------------------------------------------------------------------------------
# Ismatec-IPC pump class
# ----------------------------------------------------------------------------------------
class Ismatec(object):
    def __init__(self, serPort, tubingDiameter = 1.52, expectedPumpID = 'IPC 405'): #trycom5
        #print("serport=" +str(serPort))
        # Define attributes
        self.com_port = serPort
        self.pump_ID= "1"
        self.tubingDiameter = tubingDiameter # 3.17 # diameter in mm (1/8" ID)
        self.flip_flow_direction = False
        self.expectedPumpID = expectedPumpID
        # Create serial port
        self.serial = serial.Serial(port = self.com_port, 
                baudrate = 9600, 
                parity= serial.PARITY_NONE, 
                bytesize=serial.EIGHTBITS, 
                stopbits=serial.STOPBITS_ONE, 
                timeout=0.1)
        # Define initial pump status
        self.flow_status = "Stopped"
        self.speed = 0.0
        self.direction = "Forward"
        
        IDcheck = self.checkPumpIdentification()
        if IDcheck:
            statRC = self.enableRemoteControl(0)
            statTube = self.setTubingDiameter(self.tubingDiameter)
            setZeroCycles = self.sendToPump('"0000')
            
            stat = statRC and statTube and statusCheck(setZeroCycles)
            
            if not(stat):
                print( "Initialization error! Disconnecting!\n")
                #self.pumpDisconnect()
        else:
            #Log_window.log_stw.insert("Incorrect ID returned. Disconnecting\n", 'warning')
            print( "Incorrect ID returned. Disconnecting\n")
            self.pumpDisconnect()
        self.defaultRate = float(str.split(self.sendToPump("!").strip())[0]) # set flow rate at max rotational speed in mL/min
        self.speed = float(str.split(self.sendToPump("!").strip())[0])


    def pumpDisconnect(self):
        self.sendToPump('I') # stop pump
        self.enableRemoteControl(0) # set to manual control
        self.serial.close() # close out serial
        print("disconnect pump,close the port!")
        
    def checkPumpIdentification(self):
        pumpIDRead = self.sendToPump("#")
        print( "Pump " + pumpIDRead.rstrip() + " Identified\n")
        return 1
        
    def isPumpRunning(self):
        status = self.sendToPump("E")
        if (status == "+"):
            return 1
        elif (status == "-"):
            return 0
        else:
            print("Return from pump \n Got "+status)
            return -1

    def enableRemoteControl(self, remote):
        if (remote == 1):
            status = self.sendToPump("B")
            status = self.sendToPump("DA-PC-")
            
        else:
            status = self.sendToPump("A")
            
        return statusCheck(status)
            
    def setTubingDiameter(self, tubingDiameter):

        status = self.sendToPump("+" + str('%04d' % (int(tubingDiameter*100))))

        return statusCheck(status)

    def setFlowRate(self, flowRate):
        """ 
        flowRate: float sent to pump after translation to percentage of maximum flow rate
        
        #TODO brianl verify that this is the best way to set the speed on the IPC 501

        """ 
        clearReturn = self.getResponse()
        del clearReturn
        self.defaultRate = float(str.split(self.sendToPump("!").strip())[0]) # set flow rate at max rotational speed in mL/min
        pctRate = np.floor(10000.*flowRate/self.defaultRate)/100.
        print(pctRate)
        if pctRate > 100.:
            #Log_window.log_stw.insert("Calculated flow rate too high! reducing to max.\n", 'warning')
            #update_log_warning("Calculated flow rate too high! reducing to max.\n")
            print( 'Calculated flow rate too high! reducing to max.\n')
            #statusFlowRate = '#'
            pctRate = 100.
        
    
        statusFlowRate = self.sendToPump("S"+str(int(pctRate*100)).zfill(6)) # set flow rate as pct of max rate with this tubing
#
        if statusCheck(statusFlowRate):
            self.speed = pctRate*self.defaultRate/100.
            print( "Set flow rate to " + str(self.speed) + " ml per min.")
            return True
        else:
            return False

    def setFlowVolumeAndRate(self, flowVolume, flowTime):
        
        # flowVolume in mL
        # flowTime in min
        # dispenseRate in mL/min worked out here
        
        clearReturn = self.getResponse()
        del clearReturn
        
        status = self.sendToPump("N") # Set to 'time dispense' mode
        status = self.resetVolumeCounter()
        
        # Check flow time
        # If less than 16 minutes, will enter in 100 ms increments
        # If over 16 minutes and less than 16 hours, in integer minutes
        # If over 16 hours, in integer hours
        # Volume takes precidence over time, but volume implied in pump.  
        # So take nominal specified time, work out what what integer time is 
        # close enough, then use that.
        
        # Convert from nominal time to correct time in defined precision
        if (0 < flowTime < 16):
            # Flow time in tenths of a second
            flowTimeNow = float(int(flowTime*600))/600
            flowTimeStr = str('V' + '%04d' % int(flowTime*600))
            statusTime = self.sendToPump(flowTimeStr)
            
            
        elif (16 <= flowTime < 960):
            # Flow time in minutes
            flowTimeNow = int(flowTime)
            flowTimeStr = str('VM' + '%03d' % int(flowTime))
            statusTime = self.sendToPump(flowTimeStr)
            
        elif (960 <= flowTime < 59940):
            # Flow time in hours
            flowTimeNow = int(float(flowTime)/60)
            flowTimeStr = str('VH' + '%03d' % int(float(flowTime)/60))
            statusTime = self.sendToPump(flowTimeStr)
            
        else:
            flowTimeStr = 'V0000'
            print( 'Flow time undefined!\n')

        print( flowTimeNow)

#        # Send volume information
#        flowVolumeStr = str('[' + '%04d' % int(float(flowVolume)*100))
#        statusVolume = self.sendToPump(flowVolumeStr)

        # Given actual flow rate
        dispenseRate = float(flowVolume)/float(flowTimeNow)
        #update_log_normal("dispenseRate is "+str(dispenseRate)+"\n")
        print("dispenseRate is "+str(dispenseRate))
        self.defaultRate = float(str.split(self.sendToPump("!").strip())[0]) # set flow rate at max rotational speed in mL/min

        print(self.defaultRate)
        pctRate = np.floor(10000.*dispenseRate/self.defaultRate)/100.
        print(pctRate)
        if pctRate > 100.:

            print( 'Calculated flow rate too high! reducing to max.\n')
            #statusFlowRate = '#'
            pctRate = 100.
        
        # this is

        print("sending to pump for flow rate: "+"S"+str(int(pctRate*100)).zfill(6))
        statusFlowRate = self.sendToPump("S"+str(int(pctRate*100)).zfill(6)) # set flow rate as pct of max rate with this tubing

        n_digits = str.split(self.sendToPump("[").strip())[0]
        print("got digits from pump "+str(n_digits))

        if (statusCheck(statusTime) and statusCheck(statusFlowRate)):
            print( "Set to dispense " + str(flowVolume) + " mL in " + str(flowTimeNow) + " minutes.\n")
        self.speed = pctRate*self.defaultRate/100.
        self.flowTime = flowTimeNow
        return (statusCheck(statusTime) and statusCheck(statusFlowRate))
    
    def resetVolumeCounter(self):
        return self.sendToPump("W")
    
    def inquireVolumeCounter(self):
        return self.sendToPump(":")
    
    def inquireDefaultFlowRate(self):
        return self.sendToPump("?")
    
    def inquireCalibratedFlowRate(self):
        return self.sendToPump("!")
    
    def inquireDigitsAfterDecimal(self):
        return self.sendToPump("[")
        
    def startPump(self):
        status = self.sendToPump("H") 
        return statusCheck(status)
        
    def stopPump(self):
        status = self.sendToPump("I")
        return statusCheck(status)
        

    def setFlowDirection(self, forward):
        if self.flip_flow_direction:
            if forward:
               status = self.sendToPump("J")
            else:
               status = self.sendToPump("K")
        else:
            if forward:
               status = self.sendToPump("K")
            else:
                status = self.sendToPump("J")
        return statusCheck(status)
    
    def stopFlow(self):
        status = self.sendToPump("I")
        return statusCheck(status)


    def sendToPump(self, commandString):
        self.sendString(self.pump_ID + commandString + stop)
        lineOut = self.getResponse()
        
        return lineOut
            

    def sendString(self, string):
        self.serial.write(string.encode())

    def getResponse(self):
        return self.serial.readline().decode('utf-8')
    
    #########################################################################
    
def statusCheck(strIn):
    if strIn.rstrip() == '*':
        return 1
    else:
        return 0



