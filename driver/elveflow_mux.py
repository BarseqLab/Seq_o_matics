#!/usr/bin/python
# ----------------------------------------------------------------------------------------
# The basic I/O class for serial communication with the Elveflow MUX distributor
# ----------------------------------------------------------------------------------------



import serial







#   baud_rate: 19200
#   timeout: 0.5
#   pass_through: 9





class TimeoutError(Exception):
    pass




class ElveflowMux():
#class ElveflowMux(config ):
    def __init__(self,com):
        self.devices = []
        baud_rate=19200
        timeout= 0.5
        self.devices.append(serial.Serial(port=com, baudrate=baud_rate, timeout=timeout))
        #self.devices.append(serial.Serial(port=config['port'], baudrate=baud_rate, timeout=timeout))
        print("port set for selector")
        #
        #self.devices.append(serial.Serial(port="COM6", baudrate=baud_rate, timeout=timeout))
        self.daisy_chain_position = "P0A\r"
        self.end_cmd = '\r'
        self.valves = list(range(1, len(self.devices)*10+1))
        self.read_buffer = []
    def disconnect(self):
         for dev in self.devices:
                dev.close()
                print("disconnect selector,close the port!")
    def connect(self):
        for dev in self.devices:
                dev.open()
    def write(self, dev, command):
        cmd = command + self.end_cmd
        cmd_encoded = cmd.encode("ascii")

        if "P" in command: # activate valve, pushing "0" valves to `0A`
            if ("00" in command) or ("10" in command):
                dev.write(self.daisy_chain_position.encode("ascii"))
            else:
                dev.write(cmd_encoded)

        elif "S" in command: # get valve status
            dev.write(cmd_encoded)
            output = self.read(dev)
            return output 

    def status(self, dev_index):
        return self.write(self.devices[dev_index],"S")

    def activate(self, dev, valve):
        return self.write(self.devices[dev],"P"+str(valve).zfill(2))

    def read(self, dev):
        while True:
            if dev.is_open:
                output = dev.read(size=1)
                output = output.decode()
                if len(self.read_buffer) == 0 and output == '\r':
                    dev.flush()
                    continue
                if output == "\r":
                    ret_val = "".join(self.read_buffer)
                    dev.flush()
                    self.read_buffer = []
                    return ret_val
                else:
                    self.read_buffer.append(output)

