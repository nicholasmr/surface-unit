# N. Rathmann <rathmann@nbi.dk>, 2019-2023

import redis, json, datetime, time, math
import numpy as np
from scipy.spatial.transform import Rotation
from settings import *

DEGS_TO_RPM = 1/6 

class DrillState():

    # State variables

    motor_rpm             = 0
    motor_voltage         = 0
    motor_current         = 0
    motor_controller_temp = 0
    motor_duty_cycle      = 0

    temperature_electronics    = 0     
    temperature_auxelectronics = 0
    temperature_topplug        = 0
    temperature_gear1          = 0
    temperature_gear2          = 0
    temperature_baseplate      = 0
    temperature_motor          = 0
#    temperature_vesc           = 0 # = motor_controller_temp
    
    pressure_electronics = 0
    pressure_topplug     = 0
    pressure_gear1       = 0
    pressure_gear2       = 0
    
    hammer = 0
    tachometer = 0
    spin = 0 # = gyroscope_z
    downhole_voltage = 0.0
    
    # BNO055 triaxial values

    accelerometer_x = 0
    accelerometer_y = 0
    accelerometer_z = 0
    magnetometer_x = 0
    magnetometer_y = 0
    magnetometer_z = 0

    linearaccel_x = 0
    linearaccel_y = 0
    linearaccel_z = 0

    gravity_x = 0
    gravity_y = 0
    gravity_z = 0

    gyroscope_x = 0
    gyroscope_y = 0
    gyroscope_z = 0

    quaternion_w = 1 
    quaternion_x = 0
    quaternion_y = 0
    quaternion_z = 0
    
    # Inclinometer
    inclination_x = 0
    inclination_y = 0

    # Orientation
    inclination, azimuth, roll = 0, 0, 0 
    alpha, beta, gamma = 0, 0, 0 # Euler angles for intrinsic rotations Z-X'-Z'' 
    
    # Was the drill state update recently?
    received        = '2022-01-01 00:00:00'
    islive          = False # True = connection is live, else False
    islivethreshold = 15 # seconds before drill state is assumed dead (unless a new state was received)
    
    # Redis connection
    rc = None 
    
    ###
    
    def __init__(self, redis_host=LOCAL_HOST):
    
        # redis connection (rc) object
        try:    
            self.rc = redis.StrictRedis(host=redis_host) 
            self.rc.ping() 
        except:
            print('DrillState(): redis connection to %s failed. Using %s instead.'%(redis_host,LOCAL_HOST))
            self.rc = redis.StrictRedis(host=LOCAL_HOST) 

        #if USE_BNO055_FOR_ORIENTATION: self.saam = SAAM() # https://ahrs.readthedocs.io/en/latest/filters/saam.html
#        self.refdir = np.array([0,0,1]) # BNO055 chip orientation; used to determine orientation with SAAM
        self.update()
        

    def get(self, attr):
        try:    return getattr(self, attr)
        except: return None
            
    def update(self):
    
        try:    ds = json.loads(self.rc.get('drill-state')) # redis state
        except: ds = {}
        for key in ds: setattr(self, key, ds[key])
#        print(ds)

        # orientation
        self.spin = round(abs(self.get_spin()), 2)
        self.accelerometer_magnitude = np.sqrt(self.accelerometer_x**2 + self.accelerometer_y**2 + self.accelerometer_z**2)
        self.magnetometer_magnitude  = np.sqrt(self.magnetometer_x**2  + self.magnetometer_y**2  + self.magnetometer_z**2)
        self.linearaccel_magnitude   = np.sqrt(self.linearaccel_x**2  + self.linearaccel_y**2  + self.linearaccel_z**2)
        self.gravity_magnitude       = np.sqrt(self.gravity_x**2  + self.gravity_y**2  + self.gravity_z**2)
        self.gyroscope_magnitude     = np.sqrt(self.gyroscope_x**2     + self.gyroscope_y**2     + self.gyroscope_z**2)

        self.quat = [self.quaternion_x, self.quaternion_y, self.quaternion_z, self.quaternion_w]
        try:    rot = Rotation.from_quat(self.quat) # might fail if BNO055 is not ready (internal calibration not ready or error) => quat not normalized
        except: rot = Rotation.from_quat([0,0,0,1])
	    #... apply calibration here if needed (BNO auto calibrates if put into extreme orientations)
	    
        self.alpha, self.beta, self.gamma = rot.as_euler('ZXZ', degrees=True) # intrinsic rotations 
        
        self.beta = 180 - self.beta # uncomment if upside down
	
        self.inclination = self.beta  # pitch (theta)
        self.azimuth     = self.alpha # yaw   (phi)
        self.roll        = self.gamma # roll  (psi)

        # motor 
        self.motor_throttle = 100 * self.motor_duty_cycle

        # rename
        if hasattr(self, 'aux_temperature_electronics'):
            self.temperature_auxelectronics = self.aux_temperature_electronics        
            self.temperature_topplug        = self.aux_temperature_topplug
            self.temperature_gear1          = self.aux_temperature_gear1
            self.temperature_gear2          = self.aux_temperature_gear2
        
        # aux
        self.hammer      = 100 * self.hammer/HAMMER_MAX
        self.motorconfig = self.rc.get('motor-config')
        
        # Is live?
        now = datetime.datetime.now()
        lastreceived = datetime.datetime.strptime(self.received, '%Y-%m-%d %H:%M:%S')
        dt = (now - lastreceived).total_seconds()
        self.islive = dt < self.islivethreshold
#        print(self.received, lastreceived, now, dt, self.islivethreshold)
#        self.islive = 1
#        print('ds: dt=%f'%dt)

    ### Motor control

    def stop_motor(self):
        print('DrillState: Stopping motor')
        self.rc.publish('downhole','motor-stop')

    def start_motor__throttle(self, throttle_pct):
        print('DrillState: Starting motor at %i pct throttle'%(throttle_pct))
        self.rc.publish('downhole','motor-pwm:%d'%(self.throttle_to_PWM(throttle_pct)))
    
    def start_motor__degrees(self, degrees, throttle_pct=10):
        print('DrillState: Starting motor, rotating %i deg at %i pct throttle'%(degrees,throttle_pct))
        self.rc.publish('downhole', 'motor-rotate-by: %d, %d,'%(degrees, self.throttle_to_PWM(throttle_pct)))

    def throttle_to_PWM(self, throttle_pct):
        PWM = int(throttle_pct/100 * 255)
        if -255 <= PWM <= 255: # formal bounds
            return PWM
        else:          
            print("DrillState error: argument throttle_pct must be between -100% and 100%")
            return 0
    
    def set_motorconfig(self, motorid):
        motor_id = motorid
        if   motor_id == 0: self.rc.publish('downhole','motor-config:parvalux')
        elif motor_id == 1: self.rc.publish('downhole','motor-config:skateboard')
        elif motor_id == 2: self.rc.publish('downhole','motor-config:hacker')
        elif motor_id == 3: self.rc.publish('downhole','motor-config:plettenberg')

    def set_tacho(self, tacho_index):
        self.rc.publish('downhole', 'motor-set-tachometer: %d'%(tacho_index))

    ### Orientation
    
    def get_spin(self):
        # z-component of angular velocity vector, i.e. spin about drill (z) axis (deg/s)
        return self.gyroscope_z * DEGS_TO_RPM # convert deg/s to RPM (will be zero if USE_BNO055_FOR_ORIENTATION is false)

#    def quat2rotmat(self, q):
#        s = 1
#        qr,qi,qj,qk=q
#        return np.array([ \
#            [1-2*s*(qj**2+qk**2), 2*s*(qi*qj-qk*qr), 2*s*(qi*qk+qj*qr) ], \
#            [2*s*(qi*qj+qk*qr), 1-2*s*(qi**2+qk**2), 2*s*(qj*qk-qi*qr) ], \
#            [2*s*(qi*qk-qj*qr), 2*s*(qj*qk+qi*qr), 1-2*s*(qi**2+qj**2) ], \
#        ])

#    def euler_from_quaternion(self, x, y, z, w):
#        rot = Rotation.from_quat([x,y,z,w])
#        return rot.as_euler('ZXZ', degrees=True)
