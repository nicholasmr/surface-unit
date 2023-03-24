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
import math
import serial
import gc

__author__ = "Aslak Grinsted"
__email__ = "ag@glaciology.net"
__license__ = "Apache License, Version 2.0"


baudrate = 9600
bytesize = serial.EIGHTBITS
parity = serial.PARITY_NONE
stopbits = serial.STOPBITS_ONE
slaveaddress = 1  # this is the address of the unit.

REDIS_HOST = "localhost"

unitname = "CODIX560"  # for printing

# enumerate ports to test...
if len(sys.argv) > 1:
    ports = [sys.argv[1]]
else:
    ports = glob.glob("/dev/ttyUSB*")
    if len(ports) == 0:  # windows
        ports = [f"COM{x:.0f}" for x in range(5, 20)]


def parse_line(line):
    address, maincounter = line.rstrip().split(" ")
    if int(address) != slaveaddress:
        raise Exception("wrong {unitname} address")
    if maincounter[0] == "o":  # overflow value
        return -9999.0
    else:
        return float(maincounter)


def find_and_connect():
    ser = None
    for port in ports:
        try:
            gc.collect()
            ser = serial.Serial(port, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=1)
            line = ser.readline()  # skip first line post-connect as it might be incomplete
            line = ser.readline().decode("ascii")
            testnumber = parse_line(line)
            print(f"Found {unitname} on {port}")
            break
        except Exception as e:
            print(f"no {unitname} on {port}")
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

    print(f"{unitname} Winch encoder script starting")

    try:
        import redis

        redis_conn = redis.StrictRedis(host=REDIS_HOST)
        print(f"{unitname} - script connected to redis")
    except ModuleNotFoundError:
        redis_conn = fake_redis(host=REDIS_HOST)

    serial_connection = None

    # When we the drill is moving slowly then we need to make a moving average
    # because the depthencoder only gives us cm-resolution.
    # memory is a constant that controls how much "memory" is in the system
    # when we calculate the velocity.

    efolding_time = 5.0  # Forget history after about 5-10 seconds.;
    # ------OR------
    efolding_depth = 0.02  # Forget history after moving 2-4cm we should have almost forgotten previous states.

    olddepth = 0.0
    oldtime = time.time()

    while True:
        if (serial_connection is None) or (serial_connection.closed):
            print(f"Trying to connect to {unitname}")
            serial_connection = find_and_connect()

        try:
            line = serial_connection.readline().decode("ascii")
            curdepth = parse_line(line)
            curtime = time.time()
        except Exception as e:
            print(f"Failed to read from {unitname}: {repr(e)}")
            redis_conn.set("depth-encoder", '{"depth": -9999, "velocity": -9999}')
            del serial_connection
            serial_connection = None
            print("waiting 5secs...")
            time.sleep(5.0)
            continue

        dt = curtime - oldtime
        dz = curdepth - olddepth
        memory = math.exp(-math.fabs(dz) / efolding_depth - dt / efolding_time)
        # memory = 0 #forget the past.
        velocity = dz / dt
        redis_conn.set("depth-encoder", '{"depth": %f, "velocity": %f}' % (curdepth, velocity))

        oldtime = curtime * (1 - memory) + oldtime * memory
        olddepth = curdepth * (1 - memory) + olddepth * memory

pass
