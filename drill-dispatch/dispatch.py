"""EastGRIP drill dispatch
Jens Christian Hillerup <hillerup@nbi.ku.dk>

This program publishes the state of an EastGRIP drill to a Redis broker.

Usage:
  dispatch.py [--redis=<url>] [--port=<path>] [--debug]

Options:
  --redis=<url>           Redis host. [default: redis://localhost:6379/0]
  --port=<path>           Serial port for the drill modem. [default: /dev/serial0]
  --debug                 Print debug information on the console
"""

import sys, os, serial, redis, pprint, time, threading, signal
from docopt import docopt
from log import logger
import surface, downhole, uphole

pp = pprint.PrettyPrinter(indent=4)

if __name__ == "__main__":
    arguments = docopt(__doc__, version="EastGRIP drill dispatch 2019")
    logger.info("Dispatch started")

    redis_conn = redis.StrictRedis.from_url(arguments["--redis"])
    try: serial = serial.Serial(arguments["--port"], 600)
    except: print('!!! Serial connection to modem could not be established on %s'%(arguments["--port"]))

    # TODO sanity checks
    print("starting surface thread")
    surface_thread = threading.Thread(target=surface.surface_worker, args=(arguments, redis_conn))
    surface_thread.daemon = True
    surface_thread.start()


    try:
        print("starting downhole thread")
        downhole_thread = threading.Thread(target=downhole.downhole_worker, args=(arguments, redis_conn, serial))
        downhole_thread.daemon = True
        downhole_thread.start()

        
        print("starting uphole thread")
        uphole_thread = threading.Thread(target=uphole.uphole_worker, args=(arguments, redis_conn, serial))
        uphole_thread.daemon = True
        uphole_thread.start()
    except:
        pass

    while True:
        # idling in main thread so we can catch a ctrl+c
        time.sleep(100)

        # TODO: catch the KeyboardException and have the threads
        # close cleanly.

