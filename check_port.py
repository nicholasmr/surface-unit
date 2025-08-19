# check_port.py
import sys, serial, time

port = sys.argv[1]
try:
    s = serial.Serial(port, 9600, timeout=1)
    time.sleep(0.1)      # let the FTDI / CP210x finish enumerating
    s.close()
    sys.exit(0)
except serial.SerialException as exc:
    print(f"ERROR: {exc}")
    sys.exit(1)
