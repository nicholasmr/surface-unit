import time, datetime
import redis, json

redis_conn = redis.StrictRedis(host="127.0.0.1")
fp = open('egrip-load-log.csv', 'w')

while True:
    load = json.loads(redis_conn.get('load-cell'))['load']
    line = "%s;%s" % (datetime.datetime.now(), load)

    fp.write("%s\n" % line)
    print(line)

    time.sleep(1)
