
from driver.ismatec_ipc import Ismatec as IsmatecDriver
from front_end.logwindow import *
class IsmatecPumpDevice():
    def __init__(self, config):
        self.config = config

    def initialize(self):
        #print("intializing ismatec pump!")
        IPD_COM_CONFIG = self.config['port']
        self.driver = IsmatecDriver(serPort=IPD_COM_CONFIG, tubingDiameter=self.config['tubingDiameter'],
                                    expectedPumpID=self.config['pumpID'])
        # try:
        #     flowReversed = self.config["flowReversed"]
        # except:
        #     flowReversed = False
        # self.driver.flip_flow_direction = flowReversed
        #self.driver.setFlowDirection(True)
        print("initialized ismatecdriver!")
    def pumpVolume(self, volumeToPump, rate=None):

        if rate is None:
            rate = self.driver.speed

        if not self.driver.setFlowVolumeAndRate(volumeToPump, float(volumeToPump) / (rate)):
            # try slightly longer time if rounding/truncation of long times has screwed things up
            self.driver.setFlowVolumeAndRate(volumeToPump, (1.1 * float(volumeToPump) / (rate)))
        self.driver.startPump()

    def setFlowRate_ml_per_min(self, flowRate):
        return self.driver.setFlowRate(flowRate)

    def stopPump(self):

        self.driver.stopPump()
    def startPump(self):

        self.driver.startPump()
    def get_speed(self):
        return self.driver.speed

    def isPumpRunning(self):
        return self.driver.isPumpRunning()
    def PumpDisconnect(self):
        return self.driver.pumpDisconnect()
    
    def GetResponse(self):
        return self.driver.checkPumpIdentification()
    
     