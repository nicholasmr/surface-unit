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

Driver for the  PMD-Strain counter, for communication via the Modbus RTU protocol.

"""

import minimalmodbus
import struct
import glob
import sys
import redis
import time

__author__  = "Aslak Grinsted"
__email__   = "ag@glaciology.net"
__license__ = "Apache License, Version 2.0"

slaveaddress = 0xF7 # ------ this is the address of the unit.
REDIS_HOST = "localhost"

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


    #
    #            GETTER METHODS
    #

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
    print "Load cell"
    if (len(sys.argv) > 1):
        print(sys.argv[1])
        loadcellDisplay = None
        while loadcellDisplay is None:
            try:
                print "'loadcellDisplay is None', sleeping and trying again..."
                loadcellDisplay = PMDStrain(sys.argv[1], slaveaddress)
                loadcellDisplay.debug=False
                time.sleep(1)
            except:
                pass
    else:
        ports=glob.glob("/dev/ttyUSB*")
        loadcellDisplay = None
        for port in ports:
            try:
                print("- testing for pmdstrain with adress {0} on {1}".format(slaveaddress,port))
                loadcellDisplay = PMDStrain(port, slaveaddress)
                loadcellDisplay.debug=False
                loadcellDisplay.serial.readall()
                loadcellDisplay.get_decimalpoint()
                print("Load cell found on {0}".format(port))
                break
            except Exception as e:
                loadcellDisplay = None

        if loadcellDisplay is None:
            redis_conn.set("load-cell", '-9999')
            sys.exit("No port found for PMD-Strain (load cell display)!")


    redis_conn = redis.StrictRedis(host=REDIS_HOST)

    while True:
        try:
            loadcellDisplay.serial.readall() #note: sleep at least by 0.01
            time.sleep(0.05)
            loadcellDisplay.get_decimalpoint()
            redis_conn.set("load-cell", loadcellDisplay.get_displayvalue())
        except IOError:
            pass
        except ValueError:
            pass
	except TypeError:
            pass


pass
