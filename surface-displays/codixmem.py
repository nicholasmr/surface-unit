#!/usr/bin/env python
# -*- coding: utf-8 -*-
# N. Rathmann

import time, math

class Codix560Mem():
    """
        When the drill is moving slowly, we need to make a moving average because the depth encoder provides only centimetre resolution.
        "mem" is a constant that controls how much "memory" is in the system when we calculate the velocity.
    """
    def __init__(self):
        self.efolding_time  = 5.0  # Forget history after about 5-10 seconds
        self.efolding_depth = 0.02 # Forget history after moving 2-4 centimetre 
        self.olddepth = 0.0
        self.oldtime  = time.time()
        
    def update(self, curdepth):
        curtime = time.time()        
        dt = curtime - self.oldtime
        dz = curdepth - self.olddepth
        mem = math.exp( - math.fabs(dz)/self.efolding_depth - dt/self.efolding_time)
        # mem = 0 # memoryless
        velocity = dz/dt
        self.oldtime  = (1-mem)*curtime  + mem*self.oldtime
        self.olddepth = (1-mem)*curdepth + mem*self.olddepth
        return velocity  
