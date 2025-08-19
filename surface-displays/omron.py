#!/usr/bin/env python3
# Omron Serial Data Test Script V3
# Kevin Nikolaus
# November 21st, 2024
#
# — Proper 32-bit two’s-complement decoding for negative values —

import serial
import time
import redis

# Redis connection
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB   = 0
redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

idstr = "omron"  # ID string for printing

# Initialize the serial port
ser = serial.Serial(
    port='COM16',            # Replace with your COM port
    baudrate=9600,           # Baud rate
    bytesize=serial.EIGHTBITS,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    timeout=1                # Timeout in seconds
)

def calculate_bcc(data: bytes) -> int:
    """Calculate the BCC (Block Check Character) for the given data."""
    bcc = 0
    for byte in data:
        bcc ^= byte
    return bcc

def validate_and_clean_response(response: str) -> str:
    """
    Validate the response frame and trim everything after ETX.

    Raises ValueError if STX or ETX are missing.
    """
    if not response or response[0] != '\x02':
        raise ValueError("Missing STX at the beginning of the frame.")
    if '\x03' not in response:
        raise ValueError("Missing ETX in the frame.")

    # Keep only up through the first ETX
    return response[:response.index('\x03') + 1]

import re
HEX_TAIL = re.compile(r"([0-9A-F]{8})$")

def extract_data_section(response: str) -> str:
    # keep only through the first ETX
    trimmed = response[: response.index("\x03") + 1]
    body = trimmed[1:-1]  # drop STX/ETX

    m = HEX_TAIL.search(body)
    if not m:
        raise ValueError(f"No 8-hex tail in frame body: {body!r}")
    return m.group(1)
def twos_comp(val: int, bits: int) -> int:
    if val & (1 << (bits - 1)):
        val -= (1 << bits)
    return val

def decode_signed_value(hex_str: str) -> int:
    raw = int(hex_str, 16)
    return twos_comp(raw, 32)

# CompoWay/F frame components
STX           = 0x02  # Start of Text
ETX           = 0x03  # End of Text
Node          = "01"  # Node Number
SubAddress    = "00"  # Sub-address (always "00")
ServiceID     = "0"   # Service ID (always "0")
MRC           = "01"  # Main Request Code
SRC           = "01"  # Sub Request Code
Variable_Type = "C0"  # PV (measurement value)
Address       = "0002"  # Address for PV
Bit_Position  = "00"    # Always "00"
Number_of_Elements = "0001"  # Read one element

CommandText = Variable_Type + Address + Bit_Position + Number_of_Elements
data_ascii  = Node + SubAddress + ServiceID + MRC + SRC + CommandText

try:
    while True:
        # If no data available, send a read command
        if ser.in_waiting == 0:
            frame = bytearray([STX])
            frame.extend(data_ascii.encode('ascii'))
            frame.append(ETX)
            bcc = calculate_bcc(frame[1:])  # Exclude STX from BCC
            frame.append(bcc)
            ser.write(frame)
            time.sleep(0.1)

        # If data has arrived, read and parse it
        else:
            raw = ser.read(ser.in_waiting).decode('ascii', errors='ignore')
            try:
                print("RAW FRAME:", repr(raw))
                clean = validate_and_clean_response(raw)
                print(" CLEANED:", repr(clean))
                data_hex = extract_data_section(clean)
                print(" DATA HEX :", data_hex)
                raw_val = int(data_hex, 16)
                print(" RAW INT  :", raw_val)
                signed  = twos_comp(raw_val, 32)
                print(" SIGNED   :", signed)
                kg = signed / 10.0
                print(" KG       :", kg)
                redis_conn.set("load-cell", f"{kg:.6f}")
            except ValueError as e:
                print(f"[{idstr}] Error decoding response:", e)

            time.sleep(0.1)

except KeyboardInterrupt:
    print("Exiting…")

finally:
    ser.close()
