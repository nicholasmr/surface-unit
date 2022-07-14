import socket, time, threading, redis, json
from serial import *

ser = Serial("/dev/ttyAMA0", 600, bytesize=SEVENBITS, parity=PARITY_EVEN, stopbits=STOPBITS_ONE)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("0.0.0.0", 5556))
sock.listen(1) # backlog of 1

depth = 190.5

class DrillContainer():

    listeners = []
    redis = None
    
    def __init__(self):
        self.redis = redis.Redis() 
    
    def send(self, data):
        ser.write(data)
        
    def listen(self):
        while True:
            p = ser.readline()[:-2]

            depth = json.loads(self.redis.get('depth-encoder'))
            ds = '%06f' % depth["depth"]
            p += bytes(ds[:6], 'ascii')

            p += bytes([13])
            p += bytes([10])

            print("UP:   %s" % p)
            
            for listener in self.listeners:
                listener(p)

dc = DrillContainer()

t = threading.Thread(target=dc.listen, daemon=True)
t.start()

while True:
    client, address = sock.accept()

    print("Got a client")
    
    dc.listeners.append(client.send)
    
    while True:
        from_uphole = client.recv(1)

        if from_uphole == b'':
            break

        if from_uphole == b'\n':
            from_uphole = b'\r'
            
        print("DOWN: %s" % from_uphole)
        dc.send(from_uphole)

