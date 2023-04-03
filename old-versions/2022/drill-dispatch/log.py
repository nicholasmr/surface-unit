import logging
from logging.handlers import TimedRotatingFileHandler
from settings import *

LOG_FILE = "%s/drill.log" % WORKING_DIR

logging.basicConfig(format='%(asctime)s;%(module)s;%(message)s', level=0)
logger = logging.getLogger('dispatch')
try:
    handler = TimedRotatingFileHandler(LOG_FILE, when='midnight', interval=1, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s;%(module)s;%(message)s'))
    handler.setLevel(0)
    logger.addHandler(handler)
except:
    print("DRILL DISPATCH NOT LOGGING")
logger.propagate = False

def tohex(buf):
    return ":".join(["%02x" % ord(a) for a in list(buf)])
