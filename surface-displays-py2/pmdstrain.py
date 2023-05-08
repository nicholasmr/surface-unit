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

Driver for the PMD-Strain counter, for communication via the Modbus RTU protocol.

"""

import minimalmodbus
import struct
import glob
import sys
import redis
import time

__author__  = "Aslak Grinsted and Nicholas Rathmann"
__email__   = "ag@glaciology.net"
__license__ = "Apache License, Version 2.0"

slaveaddress = 0xF7 # ------ this is the address of the unit.

REDIS_HOST = "localhost"
idstr = sys.argv[0] # ID string for printing
searchLoopSleep = 3 # secs between retrying ports


class PMDStrain( minimalmodbus.Instrument ):

    """Instrument class for PMD-Strain process controller.

    Communicates via Modbus RTU protocol (via RS232 or RS485), using the *MinimalModbus* Python module.

    Args:
        * portname (str): port name
        * slaveaddress (int): slave address in the range 1 to 247

    """

    valuemultiplier = 1.0

    def __init__(self, portname, slaveaddress):
        #default is big-endian..
        minimalmodbus.Instrument.__init__(self, portname, slaveaddress, mode = minimalmodbus.MODE_ASCII )
        self.serial.baudrate = 9600   # Baud
        self.serial.bytesize = 8
        self.serial.parity   = minimalmodbus.serial.PARITY_NONE
        self.serial.stopbits = 1
        time.sleep(0.2)
        self.get_decimalpoint()


    def get_displayvalue(self):
        """get main counter"""
        registers = self.read_registers(registeraddress = 0x0000, numberOfRegisters=2)
        registers = struct.pack("HH",registers[0],registers[1])
        registers = struct.unpack("i",registers)
        return "{\"load\": %f}" % (registers[0] * self.valuemultiplier)


    def get_decimalpoint(self):
        """Get decimal places (between 0-3)"""
        decimalpoint = self.read_register(registeraddress = 0x001E) & 0x00FF
        self.valuemultiplier = 10.0**-float(decimalpoint)
        return decimalpoint


if __name__ == '__main__':

    redis_conn = redis.StrictRedis(host=REDIS_HOST)
    display = None
            
    while display is None: # instrument search loop
    
        print '%s: Searching for instrument with address %i on... '%(idstr, slaveaddress),
        
        # Is port provided as cmd argument?
        if len(sys.argv) == 2:
            port = sys.argv[1]
            print "%s "%(port), # compact output to not clutter screen
            try:    display = PMDStrain(port, slaveaddress)
            except: display = None

        else:
            ports = glob.glob("/dev/ttyUSB*")
            if len(ports) == 0: print 'no ports',
            for port in ports:
                print "%s "%(port), # compact output to not clutter screen
                try:
                    display = PMDStrain(port, slaveaddress)
                    display.debug=False
                    display.serial.readall()
                    display.get_decimalpoint()
                    break
                except:
                    display = None

        if display is None:
            print '...failed, trying later.'
            time.sleep(searchLoopSleep)
            continue
        else:
            print '...found!'%(port)
            break        

    # Still not found? Then exit            
    if display is None:
        redis_conn.set("load-cell", '-9999')
        sys.exit("%s: Failed to find depth encoder."%(idstr))

    ### Read loop

    while True:
        try:
            display.serial.readall() #note: sleep at least by 0.01
            time.sleep(0.05)
            display.get_decimalpoint()
            redis_conn.set("load-cell", display.get_displayvalue())
        except IOError:
            pass
        except ValueError:
            pass
	except TypeError:
            pass

pass
