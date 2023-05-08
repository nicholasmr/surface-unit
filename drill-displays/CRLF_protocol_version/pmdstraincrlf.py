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
#
#

"""

.. moduleauthor:: Aslak Grinsted <ag@glaciology.net>

Driver for the Kübler Codex 560 counter, for communication via the CRLF protocol.

"""


from ast import parse
import time
import glob
import sys
import serial
import gc

__author__ = "Aslak Grinsted"
__email__ = "ag@glaciology.net"
__license__ = "Apache License, Version 2.0"


baudrate = 9600
bytesize = serial.EIGHTBITS
parity = serial.PARITY_NONE
stopbits = serial.STOPBITS_ONE
slaveaddress = 0xF7  # this is the address of the unit.

REDIS_HOST = "localhost"
unitname = "PMD-Strain"  # for printing

delay = 0.5 # delay (secs) if serial lineread() failed
DEBUG = 1 # print verbose etc.

# enumerate ports to test...
if len(sys.argv) > 1:
    ports = [sys.argv[1]]
else:
    ports = glob.glob("/dev/ttyUSB*")
    if len(ports) == 0:  # windows
        ports = [f"COM{x:.0f}" for x in range(5, 20)]


def parse_line(line):
    if len(line) != 8 + 2:
        # the meter should always send 8 chars/line +CR/LF if it is in C1 mode.
        if DEBUG: raise Exception(f"{unitname} data must be 8chars per line!")
    number = line.strip()
    if number[-1].upper() == "R":  # overflow/underflow/error = OR/UR/Err value
        return -9999.0
    else:
        return float(number)


def find_and_connect():
    if DEBUG: print(f"Trying to connect to {unitname}... ", end='')
    ser = None
    for port in ports:
        try:
            gc.collect()
            ser = serial.Serial(port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=0.5)
            line = ser.readline()  # skip first line post-connect as it might be incomplete
            line = ser.readline().decode("ascii")
            parse_line(line)
            if DEBUG: print(f"Found {unitname} on {port}")
            break
        except Exception as e:
            if DEBUG: print(f"No {unitname} on {port}")
            pass
    return ser


class fake_redis:
    # this is just for testing when no local redis is available
    def __init__(self, host):
        self.host = host
        print(f"{unitname}: No redis found. Using fake redis (print)...")

    def set(self, key, value):
        print(f"FAKEREDIS SET: {key}: {value}")


if __name__ == "__main__":

    print(f"{unitname} script starting")

    try:
        import redis

        redis_conn = redis.StrictRedis(host=REDIS_HOST)
        print(f"{unitname} - script connected to redis")
    except ModuleNotFoundError:
        redis_conn = fake_redis(host=REDIS_HOST)

    serial_connection = None

    while True:
        if (serial_connection is None) or (serial_connection.closed):
            serial_connection = find_and_connect()

        try:
            line = serial_connection.readline().decode("ascii")
            curload = parse_line(line)
        except Exception as e:
            print(f"Failed to read from {unitname}: {repr(e)} ... waiting {delay} secs")
            redis_conn.set("load-cell", "-9999")
            del serial_connection
            serial_connection = None
            time.sleep(delay)
            continue

        redis_conn.set("load-cell", "%f" % (curload))

pass
