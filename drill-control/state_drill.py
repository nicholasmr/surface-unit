#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2017-2023

import redis, json, datetime, time, math
import numpy as np
from settings import *
import warnings
warnings.filterwarnings('ignore', message='.*Gimbal', )

from scipy.spatial.transform import Rotation
from ahrs.filters import SAAM
from ahrs import Quaternion
saam = SAAM()

#try: 
#    from scipy.spatial.transform import Rotation
#except: 
#    Rotation = None
#
#try:
#    from ahrs.filters import SAAM
#    from ahrs import Quaternion
#    saam = SAAM()
#except:
#    samm = None

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
    quaternion_x = 1
    quaternion_y = 1
    quaternion_z = 0
    
    # Inclinometer
    inclination_x = 0
    inclination_y = 0

    # Orientation
    inclination, azimuth, roll = 0, 0, 0 
    alpha, beta, gamma = 0, 0, 0 # Euler angles for intrinsic rotations Z-X'-Z'' 

    inclination_ahrs, azimuth_ahrs, roll_ahrs = 0, 0, 0 
    alpha_ahrs, beta_ahrs, gamma_ahrs = 0, 0, 0 # Euler angles for intrinsic rotations Z-X'-Z'' 
        
    quat_calib = Rotation.identity().as_quat()
        
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

        self.set_bnodir(0,0)
        self.update()
        

    def get(self, attr):
        try:    return getattr(self, attr)
        except: return None

    def set_bnodir(self, x0, y0):
        self.BNO_dir = -np.array([x0, y0, np.sqrt(1 - x0**2 - y0**2)]) # assumed BNO sensor orientation (needed for AHRS)
            
    def update(self):
    
        try:    ds = json.loads(self.rc.get('drill-state')) # redis state
        except: ds = {}
        for key in ds: setattr(self, key, ds[key])
#        print(ds)

        ### Orientation
        self.spin = round(abs(self.get_spin()), 2)

        for field in ['magnetometer', 'accelerometer', 'linearaccel', 'gravity', 'gyroscope']:
            vecfield    = '%s_vec'%(field)
            vecfieldmag = '%s_mag'%(field)
            setattr(self, vecfield, np.array([getattr(self, '%s_%s'%(field,i)) for i in ['x','y','z']]))
            setattr(self, vecfieldmag, np.linalg.norm(getattr(self,vecfield)))

        self.quat_calib = self.get_quat_calib()
        q_calib = Rotation.from_quat(self.quat_calib)

        # Quaternion from sensor fuision (SFUSION)
        self.quat = np.array([self.quaternion_x, self.quaternion_y, self.quaternion_z, self.quaternion_w])
        norm = np.linalg.norm(self.quat)
        if norm is not None and norm > 1e-1: self.quat /= norm
        else: self.quat = [1,0,0,0]
        self.quat = (Rotation.from_quat(self.quat)*q_calib).as_quat() # apply calibration
        self.quaternion_x, self.quaternion_y, self.quaternion_z, self.quaternion_w = self.quat # normalized components

        self.alpha, self.beta, self.gamma = quat_to_euler(self.quat)
        self.inclination = self.beta  # pitch (theta)
        self.azimuth     = self.alpha # yaw   (phi)
        self.roll        = self.gamma # roll  (psi)

        # Quaternion from AHRS 
        self.quat_ahrs = self.wxyz_to_xyzw(saam.estimate(acc=self.accelerometer_vec, mag=self.magnetometer_vec)) # saam() returns w,x,y,z
        if np.size(self.quat_ahrs) != 4: self.quat_ahrs = [1,0,0,0]
        self.quat_ahrs = (Rotation.from_quat(self.quat_ahrs)*q_calib).as_quat() # apply calibration
        self.alpha_ahrs, self.beta_ahrs, self.gamma_ahrs = quat_to_euler(self.quat_ahrs)
        self.inclination_ahrs = self.beta_ahrs  # pitch (theta)
        self.azimuth_ahrs     = self.alpha_ahrs # yaw   (phi)
        self.roll_ahrs        = self.gamma_ahrs # roll  (psi)
            
        ### Motor
        self.motor_throttle = 100 * self.motor_duty_cycle

        ### Rename
        if hasattr(self, 'aux_temperature_electronics'):
            self.temperature_auxelectronics = self.aux_temperature_electronics        
            self.temperature_topplug        = self.aux_temperature_topplug
            self.temperature_gear1          = self.aux_temperature_gear1
            self.temperature_gear2          = self.aux_temperature_gear2
        
        ### AUX
        self.hammer      = 100 * self.hammer/HAMMER_MAX
        self.motorconfig = self.rc.get('motor-config')
        
        ### Is live?
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

    def xyzw_to_wxyz(self, q): return np.roll(q,1)
    def wxyz_to_xyzw(self, q): return np.roll(q,-1)
    
    def set_quat_calib(self, qc):
        self.quat_calib = qc # x,y,z,w
        self.rc.set('quat-calib-x',self.quat_calib[0])
        self.rc.set('quat-calib-y',self.quat_calib[1])
        self.rc.set('quat-calib-z',self.quat_calib[2])
        self.rc.set('quat-calib-w',self.quat_calib[3])
        
    def get_quat_calib(self):
        self.quat_calib = [float(self.rc.get('quat-calib-%s'%(i))) for i in ['x','y','z','w']]
        if not np.all(self.quat_calib): self.quat_calib = Rotation.identity().as_quat()
        return self.quat_calib
        

#def get_inclination_ahrs(avec, mvec, sensordir):
#    quat = saam.estimate(acc=avec, mag=mvec)
#    DCM = Quaternion(quat).to_DCM()
#    drilldir = np.matmul(DCM, sensordir)
#    inclination = np.rad2deg(np.arccos(drilldir[2])) 
#    return inclination

def quat_to_euler(quat):

    if Rotation is not None:
        try:    rot = Rotation.from_quat(quat) # might fail if BNO055 is not ready (internal calibration not ready or error) => quat not normalized
        except: rot = Rotation.from_quat([0,0,0,1])
        alpha, beta, gamma = rot.as_euler('ZXZ', degrees=True) # intrinsic rotations
        beta = 180-beta # to inclination
    else:
        alpha, beta, gamma = 0, 0, 0

    return alpha, beta, gamma
    

