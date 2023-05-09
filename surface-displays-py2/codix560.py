#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#   Copyright 2012 Aslak Grinsted
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

"""

.. moduleauthor:: Aslak Grinsted <ag@glaciology.net>

Driver for the Kubler Codix 560 counter, for communication via the Modbus RTU protocol.

"""

import minimalmodbus
import redis
import struct
import time
import glob
import sys
import math

__author__  = "Aslak Grinsted and Nicholas Rathmann"
__email__   = "ag@glaciology.net"
__license__ = "Apache License, Version 2.0"

slaveaddress = 1 # this is the address of the unit.

REDIS_HOST = "localhost"
idstr = "codex560" # ID string for printing
searchLoopSleep = 1 # secs between retrying ports


class Codix560Mem():
    """
        When the drill is moving slowly, we need to make a moving average because the depth encoder provides only centimetre resolution.
        "mem" is a constant that controls how much "memory" is in the system when we calculate the velocity.
    """
    def __init__(self):
        self.efolding_time  = 5.0  # Forget history after about 5-10 seconds
        self.efolding_depth = 0.02 # Forget history after moving 2-4 centimetre 
        self.olddepth = 0.0
        self.oldtime  = time.time()
        
    def update(self, curdepth):
        curtime = time.time()        
        dt = curtime - self.oldtime
        dz = curdepth - self.olddepth
        mem = math.exp( - math.fabs(dz)/self.efolding_depth - dt/self.efolding_time)
        # mem = 0 # memoryless
        velocity = dz/dt
        self.oldtime  = (1-mem)*curtime  + mem*self.oldtime
        self.olddepth = (1-mem)*curdepth + mem*self.olddepth
        return velocity       
       

class Codix560(minimalmodbus.Instrument):

    """Instrument class for Codix 560 process controller.

    Communicates via Modbus RTU protocol (via RS232 or RS485), using the *MinimalModbus* Python module.

    Args:
        * portname (str): port name
        * slaveaddress (int): slave address in the range 1 to 247

    """

    def __init__(self, portname, slaveaddress):
        #default is big-endian..
        minimalmodbus.Instrument.__init__(self, portname, slaveaddress)
        self.serial.baudrate = 9600   # Baud
        self.serial.bytesize = 8
        self.serial.parity   = minimalmodbus.serial.PARITY_EVEN
        self.serial.stopbits = 1
        self.serial.timeout = 0.6
        time.sleep(0.05) #dont start reading immediately


    def get_main_counter(self):
        """get main counter"""
        return self.read_float(registeraddress = 0x0000)

    def get_secondary_counter(self):
        """get secondary counter"""
        return self.read_float(registeraddress = 0x0002)

    def get_preset1(self):
        """desc"""
        return self.read_float(registeraddress = 0x0004)

    def get_preset2(self):
        """desc"""
        return self.read_float(registeraddress = 0x0006)

    def get_decimalplaces(self):
        """desc"""
        return self.read_long(registeraddress = 0x8012) >> 24

    def get_status(self):
        """desc"""
        packedbytes=self.read_long(registeraddress = 0x8014)
        return struct.unpack("BBBB",struct.pack("I",packedbytes))


    def reset_main_counter(self):
        """Resets the main counter"""
        self.write_float(registeraddress = 0, value = 0.0);
        return

    def reset_secondary_counter(self):
        """Resets the secondary counter"""
        self.write_float(registeraddress = 2, value = 0.0);
        return

    def set_preset1(self,value):
        """Sets preset 1"""
        self.write_float(registeraddress = 4, value = value);
        return

    def set_preset2(self,value):
        """Sets preset 2"""
        self.write_float(registeraddress = 6, value = value);
        return

    def set_multiplication_factor(self,value):
        """Sets multiplication factor. 0 to 99.99999 """
        self.write_float(registeraddress = 8, value = value);
        return

    def set_division_factor(self,value):
        """Sets division factor. 0 to 99.99999 """
        self.write_float(registeraddress = 0xA, value = value);
        return

    #def store_set_value(self):
    #    self.write_float(registeraddress = 0xC,0.0);
    #    return

    #def perform_set_function(self):
    #    """"""
    #    self.write_float(registeraddress = 0xE,0.0);
    #    return

    #def set_preset_1_sign_setting(self):
    #    self.write_registers(0x8010,????);
    #    return

    #def set_decimal_places(self,value):
    #    """Must be between 0-5 """
    #    self.write_registers(0x8012,????);
    #    return


if __name__ == '__main__':

    redis_conn = redis.StrictRedis(host=REDIS_HOST)
    display = None
            
    while display is None: # instrument search loop
    
        print '%s: Searching for instrument with address %i on... '%(idstr, slaveaddress),
        
        # Is port provided as cmd argument?
        if len(sys.argv) == 2:
            port = sys.argv[1]
            print "%s "%(port), # compact output to not clutter screen
            try:    display = Codix560(port, slaveaddress)
            except: display = None

        else:
            ports = glob.glob("/dev/ttyUSB*")
            if len(ports) == 0: print 'no ports',
            for port in ports:
                print "%s "%(port), # compact output to not clutter screen
                try:
                    display = Codix560(port, slaveaddress)
                    display.get_status()
                    break
                except:
                    display = None

        if display is None:
            print '...failed, trying later.'
            time.sleep(searchLoopSleep)
            continue
        else:
            print '...found!'
            break        

    # Still not found? Then exit            
    if display is None:
        redis_conn.set("depth-encoder", '{"depth": -9999, "velocity": -9999}')
        sys.exit("%s: Failed to find depth encoder."%(idstr))

    ### Read loop

    cmem = Codix560Mem()

    while True:
    
        time.sleep(0.1) #note: sleep at least by 0.01
        curdepth = display.get_main_counter()
        velocity = cmem.update(curdepth)
        redis_conn.set("depth-encoder", "{\"depth\": %f, \"velocity\": %f}" % (curdepth, velocity))

        #a.debug = True
        #minimalmodbus._print_out( 'Main counter:           {0}'.format(  a.get_main_counter()      ))
        #time.sleep(0.01)
        #minimalmodbus._print_out( 'Status:                 {0}'.format(  repr(a.get_status())      ))
        #minimalmodbus._print_out( 'Secondary counter:      {0}'.format(  a.get_secondary_counter()  ))
        #minimalmodbus._print_out( 'Preset 1:               {0}'.format(  a.get_preset1()           ))
        #minimalmodbus._print_out( 'Preset 2:               {0}'.format(  a.get_preset2()           ))
        #time.sleep(0.01)
        #minimalmodbus._print_out( 'Decimal places:         {0}'.format(  a.get_decimalplaces()     ))
        #todo: more tests
        #minimalmodbus._print_out( 'DONE!' )

pass
