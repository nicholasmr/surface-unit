# Nicholas Rathmann, 2022

import redis, json, time
import numpy as np
from settings import *

class SurfaceState():

    depth     = 0
    depthtare = 0
    
    load     = 0
    loadtare = 0
    loadnet  = 0
    
    velocity    = 0 # instantaneous
    velocityavg = 0 # time-average
    
    # For avg velocity calculation
    Navg = 10
    arr_velocity = np.zeros((Navg))  
    arr_time     = np.zeros((Navg))   

    # Redis connection
    rc = None 
    
    ###
    
    def __init__(self, redis_host='127.0.0.1'):
        self.rc = redis.StrictRedis(host=redis_host) # redis connection (rc) object
        self.update()

    def get(self, attr):
        try:    return getattr(self, attr)
        except: return None
            
    def update(self):
    
        try: 
            encoder = json.loads(self.rc.get('depth-encoder'))
            self.depth     = abs(encoder["depth"])
            self.velocity  = abs(encoder["velocity"])
            try:    self.depthtare = float(self.rc.get('depth-tare'))
            except: self.depthtare = self.depth
        except:
            self.depth, self.velocity, self.depthtare = 0,0,0

        self.calc_velocityavg(self.velocity)

        try:
            loadcell = json.loads(self.rc.get('load-cell'))
            self.load = loadcell["load"]
            self.loadnet  = self.load - CABLE_DENSITY*self.depth
            try:    self.loadtare = float(self.rc.get('load-tare'))
            except: self.loadtare = self.load
        except:
            self.load, self.loadnet, self.loadtare = 0,0,0
        
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
        
    def calc_velocityavg(self, velocity_inst):
    
        self.arr_velocity = np.roll(self.arr_velocity, -1); 
        self.arr_velocity[-1] = velocity_inst
    
        self.arr_time = np.roll(self.arr_time, -1); 
        self.arr_time[-1] =  time.time() # seconds stamp
        
        dt = np.diff(self.arr_time)
        T = np.sum(dt)
        self.velocityavg = np.sum(np.multiply(self.arr_velocity[1:],dt))/T

    
