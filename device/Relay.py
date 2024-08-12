"""
Author: Ben Sutton
Description: ACQ4 Device for KMtronic 4ch USB Solenoid Relay
Meta: https://info.kmtronic.com/usb-four-channel-relay-controller-pcb.html
"""

from typing import List
from front_end.logwindow import *

import time


from driver.kmtronic_relay import KmtronicRelay

BUTTON_TEXT_TRUE = "Open"
BUTTON_TEXT_FALSE = "Closed"


class KmtronicRelayCh4():

    def __init__(self,port):

        self.block_all_changes = False

        self._kmt_relay = KmtronicRelay(port)

    #@QtCore.pyqtSlot(bool)
    def set_change_blocker(self, value: bool):

          print("adjust relay")
          self.block_all_changes = value


    @property
    def connected(self):
        return self._kmt_relay.connected if self._kmt_relay else False

    # @QtCore.pyqtSlot(int, bool)
    def change_relay_state(self, relay_num: int, relay_state: bool):
        # print("checking connection...")
        if self.block_all_changes:

            print("relay changes blocked in change_relay_state! ")
            return

        if self.connected:
            # print("operating relay...")
            self._kmt_relay.operate_relay(relay_num, relay_state)
            #self.sigRelayChanged.emit(self._kmt_relay.relay_states)
            print(self._kmt_relay.relay_states)

    # @QtCore.pyqtSlot(list)
    def change_relay_states(self, relay_states: List[bool]):

        if self.block_all_changes:


            print("relay changes blocked in change_relay_state! ")
            return

        if self.connected:
            self._kmt_relay.operate_relays(relay_states)
            # self.sigRelayChanged.emit(self._kmt_relay.relay_states)
            print(self._kmt_relay.relay_states)

    # @QtCore.pyqtSlot()
    def on_connect_requested(self):
        if self._kmt_relay and self._kmt_relay.connect():
            print(self._kmt_relay.relay_states)
        else:
            #logging.error(f"Relay not able to connect with configuraion: {self.config}")
            print("relay config wrong")

    def quit(self):
        print(f"DEBUG... cleaning up Relay")
        if self._kmt_relay:
            self._kmt_relay.disconnect()
            print("disconeect relay, close the port!")