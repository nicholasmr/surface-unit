import serial

s0 = serial.Serial('/dev/ttyUSB0')
s1 = serial.Serial('/dev/ttyUSB1')

while True:
    print('USB0:', s0.readline())
    print('USB1:', s1.readline())
