import redis, json, time

r = redis.StrictRedis()

fp = open('drill.log', 'r')

for line in fp.readlines():
    ts, direction, data = line.rstrip().split(";")

    if direction == 'uphole':
        
        try:
            d = json.loads(data)
            if d['inclination_x'] != 0.0 and d['inclination_x'] != 22.12:
                r.set('drill-state', data)
                r.set('depth-encoder', json.dumps(d['depth_encoder']))
                r.set('load-cell', json.dumps({"load": d['load_cell']}))
                print(data)
                time.sleep(1)
        except json.decoder.JSONDecodeError:
            pass
            
