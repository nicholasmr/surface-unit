import struct, json, datetime, serial
import pyvesc
from packets import *

from log import logger, tohex
from termcolor import colored

def uphole_worker(arguments, redis, transport):
    logger.info("Uphole worker started")
    
    redis_conn = redis
    redis_pubsub = redis_conn.pubsub()
    rx_buffer = bytes()

    def parse_packet(packet):
        packet_type = packet.__class__
        
        if packet_type == DownholeState:
            # HACK: piggyback the current depth and load on the packet. Motivation
            # for that design choice in packets.py ;-)
            #
            # A "proper" way to do it would be to listen on the `uphole' Redis
            # queue, and at the recipt of a packet from downhole, gather the
            # load, depth, and put it all in something like a CSV file.
            try:
                packet.depth_encoder = json.loads(redis.get('depth-encoder'))
            except:
                pass
            
            try:
                packet.load_cell = json.loads(redis.get('load-cell'))
            except:
                pass

            redis_conn.set("drill-state", packet.as_json())

        try:
            logger.info(packet.as_json())
        except:
            print("Couldn't log packet %s" % packet_type.__name__)
            
        redis_conn.publish("uphole", packet_type.__name__)


    try:
        logfile = open("/home/packet_log.txt" , "a")
    except:
        print("Couldn't open packet log")

    streng = ''

    while True:
        rx_buffer += transport.read()
        msg, consumed = pyvesc.decode(rx_buffer)

        if consumed > 0:
            if arguments["--debug"]:
                if msg is None:
                    print(colored("%s %d stray bytes" % (datetime.datetime.now(), consumed), 'green'))
                    logfile.write( '{} {} {}'.format(datetime.datetime.now(), consumed), '\n')
                else:
                    print(colored("%s %s" % (datetime.datetime.now(), msg.__class__.__name__), 'green'))
                    logfile.write( '{} {} {}'.format(datetime.datetime.now(), msg.__class__.__name__, '\n'))
                    dir(type(msg))

            if msg is not None:
                parse_packet(msg)
                rx_buffer = rx_buffer[consumed:]

