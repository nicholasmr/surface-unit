# N. Rathmann <rathmann@nbi.dk>, 2019-2022

import redis, json, time
import numpy as np
from settings import *

class SurfaceState():

    depth     = 0.0
    depthtare = 0.0
    
    load     = 0.0
    loadtare = 0.0
    loadnet  = 0.0

    # For speed calculation    
    speed = 0.0 # instantaneous
    Navg = 20
    arr_speed = np.zeros((Navg))  
    arr_time  = np.zeros((Navg))   
    depthprev = 0.0

    # Redis connection
    rc = None 
    
    ###
    
    def __init__(self, redis_host=LOCAL_HOST):
    
        # redis connection (rc) object
        try:    
            self.rc = redis.StrictRedis(host=redis_host) 
            self.rc.ping() 
        except:
            print('SurfaceState(): redis connection to %s failed. Using %s instead.'%(redis_host,LOCAL_HOST))
            self.rc = redis.StrictRedis(host=LOCAL_HOST) 

        self.update()

    def get(self, attr):
        try:    return getattr(self, attr)
        except: return None
            
    def update(self):
    
        self.depthprev = self.depth # for speed calculation
    
        try: 
            encoder = json.loads(self.rc.get('depth-encoder'))
            self.depth = abs(encoder["depth"])
            try:    self.depthtare = float(self.rc.get('depth-tare'))
            except: self.depthtare = self.depth
        except:
            self.depth, self.depthtare = 0.0, 0.0

        self.speed = self.calc_speed(self.depth, self.depthprev)

        try:
            loadcell = json.loads(self.rc.get('load-cell'))
            self.load = float(loadcell["load"])
            self.loadnet  = self.load - CABLE_DENSITY*self.depth
            try:    self.loadtare = float(self.rc.get('load-tare'))
            except: self.loadtare = self.load
        except:
            self.load, self.loadnet, self.loadtare = 0.0, 0.0, 0.0
        
        try:    self.alertloggers = int(self.rc.get('alert-loggers'))
        except: self.alertloggers = 0
        
    def set_loadtare(self,tare):
        self.rc.set('load-tare', tare)
        
    def set_depthtare(self,tare):
        self.rc.set('depth-tare', tare)
        
    def set_alertloggers(self, flag):
        self.rc.set('alert-loggers', int(flag))

    def toggle_alertloggers(self):
        self.set_alertloggers(not self.alertloggers)
        
    def calc_speed(self, depth, depthprev):

        self.arr_time = np.roll(self.arr_time, -1); 
        self.arr_time[-1] =  time.time() # seconds stamp
    
        speed_inst = (depth-depthprev)/(self.arr_time[-1]-self.arr_time[-2])
    
        self.arr_speed = np.roll(self.arr_speed, -1); 
        self.arr_speed[-1] = speed_inst
       
        dt = np.diff(self.arr_time)
        T = np.sum(dt)
        speed_avg = np.sum(np.multiply(self.arr_speed[1:],dt))/T
        
        return speed_avg
    
