# N. Rathmann <rathmann@nbi.dk>, 2019-2022

import redis, json, time
import numpy as np
from settings import *

class SurfaceState():

    depth     = 0.0 # current
    depthtare = 0.0
    
    load     = 0.0
    loadprev = 0.0 # used for running smoothed load average
    loadtare = 0.0 # reference value to subtract from "load"
    loadnet  = 0.0 # load - cable weight

    # For speed calculation    
    speedinst = 0.0 # instantaneous
    speed     = 0.0 # time-average
    speedprev = 0.0
    
    # Are sensors live?
    islive_depthcounter = False
    islive_loadcell     = False 
    
    # Redis connection
    rc = None 
    
    ###
    
    def __init__(self, tavg, dt_intended, redis_host=LOCAL_HOST):
    
        # redis connection (rc) object
        try:    
            self.rc = redis.StrictRedis(host=redis_host) 
            self.rc.ping() 
        except:
            print('SurfaceState(): redis connection to %s failed. Using %s instead.'%(redis_host,LOCAL_HOST))
            self.rc = redis.StrictRedis(host=LOCAL_HOST) 

        self.dt_intended = dt_intended
        self.Navg = int(np.round(tavg/dt_intended))
        self.depth_list = np.zeros((self.Navg))
        self.time_list = np.zeros((self.Navg))

        np.seterr(divide='ignore', invalid='ignore')
        self.update()

    def get(self, attr):
        try:    return getattr(self, attr)
        except: return None
            
    def update(self, smoothload=True):

        ### Depth and speed
        try: 
            now = time.time()
            encoder = json.loads(self.rc.get('depth-encoder'))
            depth = encoder["depth"]
            self.islive_depthcounter = not (int(depth) == 9999 or int(depth) == -9999) 
            
            if self.islive_depthcounter:

                self.depth = depth
                self.speedinst = 100*encoder["velocity"] # cm/s
                if np.abs(self.speedinst) > 200: self.speedinst = 0 # if depth display falls out, a large negative value may be reported and the speed is unphysical.

                if 0: # Running mean?
                    self.depth_list = np.roll(self.depth_list, -1); 
                    self.depth_list[-1] = self.depth

                    self.time_list = np.roll(self.time_list, -1); 
                    self.time_list[-1] = now # new time stamp (seconds)
                    
                    self.speedprev = self.speed
                    speednew = np.nanmean(np.divide( np.diff(self.depth_list), np.diff(self.time_list) ))
                    speednew *= 100 # m/s -> cm/s 
                    alpha = 0.125
                    self.speed = alpha*speednew + (1-alpha)*self.speedprev
                else:
                    self.speed = self.speedinst

            try:    self.depthtare = float(self.rc.get('depth-tare'))
            except: self.depthtare = self.depth
            
        except:
            # probably because not connected?
            self.depth, self.depthtare = 0.0, 0.0 
            self.speedinst, self.speed = 0.0, 0.0
            self.islive_depthcounter = False

        ### Load
        self.loadprev = self.load
        try:
            loadcell = json.loads(self.rc.get('load-cell'))
#            loadnew = float(loadcell["load"])
            loadnew = float(loadcell) # new version (2023)
            self.islive_loadcell = (int(loadnew) != -9999)
            if self.islive_loadcell:
                self.load = loadnew if not smoothload else (self.loadprev+loadnew)/2
                self.loadnet  = self.load - CABLE_DENSITY*self.depth
        except:
            # probably because not connected?
            self.load, self.loadnet = 0.0, 0.0
            self.islive_loadcell = False
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
        
#    def calc_avgspeed(self, speedinst, dt):

#        self.dt_list = np.roll(self.dt_list, -1); 
#        self.dt_list[-1] = dt # seconds stamp
#        
#        self.speed_list = np.roll(self.speed_list, -1); 
#        self.speed_list[-1] = speedinst

#        T = np.sum(self.dt_list)       
#        speed_avg = np.sum(np.multiply(self.speed_list, self.dt_list))/T
#        return speed_avg
    
