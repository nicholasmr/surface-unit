import datetime, threading
from termcolor import colored
from log import logger
from settings import WORKING_DIR

def get_run_id_from_storage():
    try:
        return int(open("%s/run.id" % WORKING_DIR, "r").read())
    except:
        return 0

def write_run_id(id_):
    try:
        open("%s/run.id" % WORKING_DIR, "w").write(str(id_))
    except:
        print(colored("ERROR: Could not write current run to disk.", "green"))

def surface_worker(arguments, redis_conn):
    logger.info("Surface worker started")
    
    is_running = False
    current_run = None
    depth_encoder_idx = 0
    load_cell_idx = 0
    
    redis_pubsub = redis_conn.pubsub()
    redis_pubsub.subscribe("surface")
    redis_pubsub.subscribe("__keyspace@0__:run-data")
    redis_pubsub.subscribe("__keyspace@0__:depth-encoder")
    redis_pubsub.subscribe("__keyspace@0__:load-cell")
    
    current_run = get_run_id_from_storage();
    redis_conn.set('current-run', current_run);
    
    for item in redis_pubsub.listen():
        if (item["type"] == "message" and item["channel"] == "surface"):
            data = item["data"].split(":")

            if (data[0] == "start-run"):

                if is_running:
                    print(colored("Stopping run: %d" % current_run, "green"))
                    logger.info("Stopping run: %d" % current_run)

                current_run = redis_conn.incr('current-run')
                write_run_id(current_run)
                logger.info("Starting run: %d"   % current_run)
                print(colored("Starting run: %d" % current_run, "green"))
                
                is_running = True

            if (data[0] == "stop-run"):

                if is_running:
                    print(colored("Stopping run: %d" % current_run, "green"))
                    logger.info("Stopping run: %d"   % current_run)
                else:
                    print(colored("No run to stop", "green"))

                is_running = False

            redis_conn.set('is-running', is_running)

            

        if (item["type"] == "message" and item["channel"] == "__keyspace@0__:depth-encoder"):
            if depth_encoder_idx % 10 == 0:
                logger.info("Depth: %s" % redis_conn.get('depth-encoder'))
            
            depth_encoder_idx += 1

        if (item["type"] == "message" and item["channel"] == "__keyspace@0__:load-cell"):
            if load_cell_idx % 10 == 0:
                logger.info("Load: %s" % redis_conn.get('load-cell'))

            load_cell_idx += 1

        

