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

Driver for the PMD-Strain counter, for communication via the CRLF protocol.

"""

from ast import parse
import time
import glob
import sys
import serial
import gc
import redis

__author__ = "Aslak Grinsted and Nicholas Rathmann"
__email__ = "ag@glaciology.net"
__license__ = "Apache License, Version 2.0"

baudrate = 9600
bytesize = serial.EIGHTBITS
parity = serial.PARITY_NONE
stopbits = serial.STOPBITS_ONE
slaveaddress = 0xF7  # this is the address of the unit.

REDIS_HOST = "localhost"
idstr = sys.argv[0] # ID string for printing
searchLoopSleep = 3 # secs between retrying ports


def parse_line(line, bad=-9999.0):
    if len(line) != 8 + 2: return bad
    number = line.strip()
    if number[-1].upper() == "R": return bad # overflow/underflow/error = OR/UR/Err value
    else: return float(number)


def find_and_connect():

    ser = None
    
    while ser is None:
        print('%s: Searching for instrument with address %i on... '%(idstr, slaveaddress), end='')
        
        if len(sys.argv) > 1: ports = [sys.argv[1]]
        else:                 ports = glob.glob("/dev/ttyUSB*")
        
        if len(ports) == 0: print('no ports', end='')
        
        for port in ports:
            print("%s "%(port), end='') # compact output to not clutter screen
            try:
                gc.collect()
                ser = serial.Serial(port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=0.5)
                line = ser.readline() # skip first line post-connect as it might be incomplete
                line = ser.readline().decode("ascii")
                testnumber = parse_line(line)
                break
            except:
                ser = None

        if ser is None:
            print('...failed, trying later.')
            time.sleep(searchLoopSleep)
            continue
        else:
            print('...found!')
            break        

    return ser

if __name__ == "__main__":

    redis_conn  = redis.StrictRedis(host=REDIS_HOST)
    serial_conn = None

    while True:
    
        if (serial_conn is None) or (serial_conn.closed):
            serial_conn = find_and_connect()

        try:
            line = serial_conn.readline().decode("ascii")
            curload = parse_line(line)
        except:
            print("%s: Read failed. Restarting serial connection."%(idstr))
            curload = -9999
            serial_conn = None
            continue

        redis_conn.set("load-cell", "%f"%(curload))

pass
