from serial import *
s = Serial("/dev/ttyAMA0", 600, bytesize=SEVENBITS, parity=PARITY_EVEN, stopbits=STOPBITS_ONE, timeout=1)

def c8bit(s):
    b = bytes(s)

    return (b[0] - 32) * 64 + b[1] - 32 - 2048


def start_motor():
    s.write(bytes(b"Q") + bytes(chr(13), 'ascii'))


def stop_motor():
    s.write(bytes(b"S") + bytes(chr(13), 'ascii'))


def get_readings():
    def parse_reading(packet):
        last_chan_id = packet[11] - 48

        current = c8bit( packet[4:6]) / 32.5
        print ("Current: %f" % current)

        #if last_chan_id == 5:
            # print(packet[12:14])
            
        

    while True:
        s.write(bytes(b"D") + bytes(chr(13), 'ascii'))
        p = s.read(29)
        print(len(p))
        parse_reading(p)


if __name__ == '__main__':
    get_readings()
