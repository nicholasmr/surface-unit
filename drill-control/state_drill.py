#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2017-

import redis, json, datetime
import numpy as np
import warnings
warnings.filterwarnings('ignore', message='.*Gimbal', )

from settings import *

from scipy.spatial.transform import Rotation
from ahrs.filters import Tilt, SAAM

AHRS_estimators = {
    'Tilt': Tilt(),
    'SAAM': SAAM(),
}

class DrillState():

    rc = None # redis connection object

    """
    Drill sensors
    """

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
    
    downhole_voltage = 0.0
    
    ### Alerts
    
    hammer = 0
    spin   = 0 # = gyroscope_z when close to vertical

    """
    Motor state 
    """
    
    motor_rpm             = 0
    motor_voltage         = 0
    motor_current         = 0
    motor_controller_temp = 0
    motor_duty_cycle      = 0

    tachometer = 0
    
    """
    Orientation
    """
    
    ### Calculated drill orientation

    ei0 = np.eye(3) # Cartesian axes
    
    quat = np.array([0,0,0,1]) # sensor orientation quarternion in scalar-last (x, y, z, w) format
    ei   = [np.zeros(3), np.zeros(3), np.zeros(3)] # corresponding x,y,z axes of sensor
    incl = 0 # 0 = plumb
    azim = 0
    roll = 0
    
    ### BNO055 triaxial values

    accelerometer_x = 0
    accelerometer_y = 0
    accelerometer_z = -9.8
    
    magnetometer_x = 0
    magnetometer_y = 1
    magnetometer_z = 0

    gyroscope_x = 0
    gyroscope_y = 0
    gyroscope_z = 0

    quality_sys   = 0
    quality_gyro  = 0
    quality_accel = 0
    quality_magn  = 0
    
    ### Independent inclinometer reading
    
    inclination_x = 0 # **no longer available**
    inclination_y = 0 # **no longer available**

    ### Other sensors

    linearaccel_x = 0
    linearaccel_y = 0
    linearaccel_z = 0

    gravity_x = 0
    gravity_y = 0
    gravity_z = -9.8
    
    """
    Flags and state 
    """
    
    received        = '2026-01-01 00:00:00'
    islive          = False # True = drill is online (communication active), else offline
    islivethreshold = 8     # seconds before drill state is assumed dead (unless a new state was received)
   
    ######## 
   
    def __init__(self, redis_host=LOCAL_HOST, AHRS_estimator='Tilt', DEBUG=True):
    
        try:    
            if DEBUG: print('DrillState(): Connecting to redis server %s ...'%(redis_host))
            self.rc = redis.StrictRedis(host=redis_host) 
            self.rc.ping() 
        except:
            print('DrillState(): redis connection to %s failed. Using %s instead.'%(redis_host,LOCAL_HOST))
            self.rc = redis.StrictRedis(host=LOCAL_HOST) 

        self.set_AHRS_estimator(AHRS_estimator)
        self.update()
                
    def get(self, attr):
        try:    return getattr(self, attr)
        except: return None

    def update(self):
    
        try:    ds = json.loads(self.rc.get('drill-state')) # redis state
        except: ds = {}
        for key in ds: setattr(self, key, ds[key])
#        print(ds)

        self.spin = round(abs(self.get_spin()), 2)

        for field in ['magnetometer', 'accelerometer', 'linearaccel', 'gravity', 'gyroscope']:
            vecfield    = '%s_vec'%(field)
            vecfieldmag = '%s_mag'%(field)
            setattr(self, vecfield, np.array([getattr(self, '%s_%s'%(field,i)) for i in ['x','y','z']]))
            setattr(self, vecfieldmag, np.linalg.norm(getattr(self,vecfield)))

        ### Orientation

        if self.AHRS_estimator == 'Tilt':
            
            # BNO055 measurement
            (self.quat, self.ei, self.incl, self.azim, self.roll) = self.get_tiltquat(self.accelerometer_vec)

            # Alt. instrument
            (self.quat_alt, self.ei_alt, self.incl_alt, self.azim_alt, self.roll_alt) = self.get_tiltquat(self.gravity_vec)

        elif self.AHRS_estimator == 'SAAM': 
            pass
        else:
            raise ValueError('DrillState(): AHRS_estimator "%s"not supported'%(self.AHRS_estimator))
            
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
        
        ### Is drill online?
        
        lastreceived = datetime.datetime.strptime(self.received, '%Y-%m-%d %H:%M:%S')
        dt = (datetime.datetime.now() - lastreceived).total_seconds()
        self.islive = dt < self.islivethreshold # online/offline flag

    """
    Orientation routines
    """
    
    def get_tiltquat(self, acc):
        quat = wxyz_to_xyzw(AHRS_estimators[self.AHRS_estimator].estimate(acc=acc, mag=None)) # note estimate() returns w,x,y,z ordered quats
        if np.size(quat) != 4 or np.any(np.isnan(quat)): quat = np.array([0,0,0,-1]) # if estimator is bad, ignore result
        ei, incl, azim, roll = self.quat2ang(quat)
        roll, azim = azim, roll # swap
        roll = 360-roll # adjust
        return (quat, ei, incl, azim, roll)
        
    def quat2ang(self, quat):
        q = Rotation.from_quat(quat)
        ei = [np.zeros(3), np.zeros(3), np.zeros(3)]
        for ii in range(3): ei[ii] = q.apply(self.ei0[ii]) # sensor x,y,z axes
        x1,x2,x3 = ei[0] # sensor x axis 
        z1,z2,z3 = ei[2] # sensor z axis (drill axis)
        incl = 180 - np.rad2deg(np.arccos(np.clip(z3,-1,1))) # pitch (theta)
        azim = np.rad2deg(np.arctan2(z2,z1)) # yaw (phi)
        roll = np.rad2deg(np.arctan2(x2,x1)) # roll (psi)
        return (ei, incl, azim, roll)

    def set_AHRS_estimator(self, AHRS_estimator):
        self.AHRS_estimator = AHRS_estimator

    def get_spin(self):
        # z-component of angular velocity vector, i.e. spin about drill (z) axis (deg/s)
        DEGS_TO_RPM = 1/6 
        return self.gyroscope_z * DEGS_TO_RPM # convert deg/s to RPM

#    def save_bno055_calibration(self, slot):
#        print('state_drill.py: Saving calibration in slot %i'% slot)
#        self.rc.publish('downhole','bno055-calibrate:%d,%d' %(1, slot))
#    
#    def load_bno055_calibration(self, slot):
#        print('state_drill.py: Loading calibration from slot %i'% slot)
#        self.rc.publish('downhole','bno055-calibrate:%d,%d' %(0, slot))

    """
    Motor routines
    """

    def stop_motor(self):
        print('DrillState(): Stopping motor')
        self.rc.publish('downhole','motor-stop')

    def start_motor__throttle(self, throttle_pct):
        print('DrillState(): Starting motor at %i pct throttle'%(throttle_pct))
        self.rc.publish('downhole','motor-pwm:%d'%(self.throttle_to_PWM(throttle_pct)))
    
    def start_motor__degrees(self, degrees, throttle_pct=10):
        print('DrillState(): Starting motor, rotating %i deg at %i pct throttle'%(degrees,throttle_pct))
        self.rc.publish('downhole', 'motor-rotate-by: %d, %d,'%(degrees, self.throttle_to_PWM(throttle_pct)))

    def throttle_to_PWM(self, throttle_pct):
        PWM = int(throttle_pct/100 * 255)
        if -255 <= PWM <= 255: # formal bounds
            return PWM
        else:          
            print("DrillState() error: argument throttle_pct must be between -100% and 100%")
            return 0

    def set_tacho(self, tacho_index):
        self.rc.publish('downhole', 'motor-set-tachometer: %d'%(tacho_index))
    
    def set_motorconfig(self, motor_id):
        if   motor_id == 0: self.rc.publish('downhole','motor-config:parvalux')
        elif motor_id == 1: self.rc.publish('downhole','motor-config:skateboard')
        elif motor_id == 2: self.rc.publish('downhole','motor-config:hacker')
        elif motor_id == 3: self.rc.publish('downhole','motor-config:plettenberg')

### Change order of quarternion components

def xyzw_to_wxyz(q): return np.array(np.roll(q,1),  dtype=np.float64)
def wxyz_to_xyzw(q): return np.array(np.roll(q,-1), dtype=np.float64)

