# N. Rathmann <rathmann@nbi.dk>, 2019-2022

import redis, json, time
import numpy as np
from settings import *

class SurfaceState():

    updatetime     = 0 # current 
    updatetimeprev = 0 # previous

    depth     = 0.0 # current
    depthprev = 0.0 # previous
    depthtare = 0.0
    
    load     = 0.0
#    loadprev = 0.0
    loadtare = 0.0 # reference value to subtract from "load"
    loadnet  = 0.0 # load - cable weight

    # For speed calculation    
    speedinst  = 0.0 # instantaneous
    speed      = 0.0 # time-average
    Navg       = 20 # length of array used to calculate time averaged 
    speed_list = np.zeros((Navg)) # array of speed estimates
    dt_list    = np.zeros((Navg)) # array of dt
    
    # Are sensors live?
    isdepthcounterdead = False
    isloadcelldead     = False 
    
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

        ### Time
        self.updatetimeprev = self.updatetime 
        self.updatetime = time.time() # new time stamp (seconds)
        self.dt = self.updatetime - self.updatetimeprev
        
        ### Depth and speed
        self.depthprev = self.depth # for speed calculation
        try: 
            encoder = json.loads(self.rc.get('depth-encoder'))
            self.depth = abs(encoder["depth"])
            self.speedinst = (self.depth-self.depthprev)/self.dt
            self.speed = self.calc_avgspeed(self.speedinst, self.dt)
            try:    self.depthtare = float(self.rc.get('depth-tare'))
            except: self.depthtare = self.depth
            self.isdepthcounterdead = False
        except:
            # probably because not connected?
            self.depth, self.depthtare = 0.0, 0.0 
            self.speedinst, self.speed = 0.0, 0.0
            self.isdepthcounterdead = True

        ### Load
        try:
            loadcell = json.loads(self.rc.get('load-cell'))
            self.load = float(loadcell["load"])
            self.loadnet  = self.load - CABLE_DENSITY*self.depth
            self.isloadcelldead = False
        except:
            # probably because not connected?
            self.load, self.loadnet = 0.0, 0.0
            self.isloadcelldead = True
#            self.load = np.random.rand()  + 10 # debug

        try:    self.loadtare = float(self.rc.get('load-tare'))
        except: self.loadtare = 0.0
                    
        ### AUX
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
        
    def calc_avgspeed(self, speedinst, dt):

        self.dt_list = np.roll(self.dt_list, -1); 
        self.dt_list[-1] = dt # seconds stamp
        
        self.speed_list = np.roll(self.speed_list, -1); 
        self.speed_list[-1] = speedinst

        T = np.sum(self.dt_list)       
        speed_avg = np.sum(np.multiply(self.speed_list, self.dt_list))/T
        return speed_avg
    
