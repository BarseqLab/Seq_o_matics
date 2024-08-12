# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-

from driver.elveflow_mux import ElveflowMux as ElveflowDriver
from front_end.logwindow import *

class ElveflowMuxDevice():
    def __init__(self,com):
        self.port=com
    def initialize(self):
        print("intializing HamiltonSelectorDevice!")
        self.elveflowmux = ElveflowDriver(self.port)
        pass

    def selectSource(self,fluidicSourceInfo):
        '''selectSource
        passes device and valve position to the Elveflow Mux Device
        positions 0 are mapped to the `0A`hex character for daisy chained devices.
        '''
        txt="selectSource!"+"Relay is ready!\n"
        print("selectSource!")
        for portId in range(len(fluidicSourceInfo.hardwareId)):
            self.elveflowmux.activate(portId, fluidicSourceInfo.hardwareId[portId])

# #