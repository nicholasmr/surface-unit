#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2017-2024

import redis, json, datetime, time, math
import numpy as np
from settings import *
import warnings
warnings.filterwarnings('ignore', message='.*Gimbal', )

from scipy.spatial.transform import Rotation
import ahrs
from ahrs.filters import SAAM, FLAE, QUEST, OLEQ, FQA
from ahrs import Quaternion

egrip_N, egrip_E, egrip_height = 75.63248, -35.98911, 2.6

wmm = ahrs.utils.WMM(datetime.datetime.now(), latitude=egrip_N, longitude=egrip_E, height=egrip_height) 
mag_dip = wmm.I # Inclination angle (a.k.a. dip angle) -- https://ahrs.readthedocs.io/en/latest/wmm.html
mag_ref = np.array([wmm.X, wmm.Y, wmm.Z])
#print('mag_ref = (%.1f, %.1f, %.1f) %.1f'%(mag_ref[0],mag_ref[1],mag_ref[2], np.linalg.norm(mag_ref)))
frame = 'NED'

AHRS_estimators = {
    'SAAM': SAAM(),
    'FLAE': FLAE(magnetic_dip=mag_dip),
    'OLEQ': OLEQ(magnetic_ref=mag_ref, frame=frame),
    'FQA' : FQA(mag_ref=mag_ref)
}


class DrillState():

    ### State variables

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
    
    ### BNO055 triaxial values

    accelerometer_x = 0
    accelerometer_y = 0
    accelerometer_z = -9.8
    
    magnetometer_x = 0
    magnetometer_y = 1
    magnetometer_z = 0

    linearaccel_x = 0
    linearaccel_y = 0
    linearaccel_z = 0

    gravity_x = 0
    gravity_y = 0
    gravity_z = 9.82

    gyroscope_x = 0
    gyroscope_y = 0
    gyroscope_z = 0

    quaternion_x = 0
    quaternion_y = 0
    quaternion_z = 0
    quaternion_w = 1
            
    quality_sys   = 0
    quality_gyro  = 0
    quality_accel = 0
    quality_magn  = 0
    
    ### Inclinometer
    inclination_x = 0
    inclination_y = 0

    ### Derived orientation
    azimuth_sfus, inclination_sfus, roll_sfus = 0, 0, 0 
    azimuth_ahrs, inclination_ahrs, roll_ahrs = 0, 0, 0 
        
    # sensor raws
    quat0_ahrs = np.array([0,0,0,1]) # scalar-last (x, y, z, w) format
    quat0_sfus = np.array([0,0,0,1]) # scalar-last (x, y, z, w) format

    # ... with offsets applied
    quat_ahrs = quat0_ahrs
    quat_sfus = quat0_sfus

    # sensor axes
    xi0 = np.eye(3) # cartesian axes
    xi0_sfus = [np.zeros(3), np.zeros(3), np.zeros(3)] # x,y,z axis of sensor
    xi_sfus  = [np.zeros(3), np.zeros(3), np.zeros(3)] # x,y,z axis of sensor, with offset
    
    # calibration rotation
    oricalib_ahrs = np.array([0,0,0]) # incl, azim, roll
    oricalib_sfus = np.array([0,0,0]) # incl, azim, roll
    
    ### Communication status 
    # Was the drill state update recently?
    received        = '2022-01-01 00:00:00'
    islive          = False # True = connection is live, else False
    islivethreshold = 15 # seconds before drill state is assumed dead (unless a new state was received)
    
    ### Redis connection
    rc = None 
    
    
    def __init__(self, redis_host=LOCAL_HOST, AHRS_estimator='SAAM', DEBUG=True):
    
        # redis connection (rc) object
        try:    
            if DEBUG: print('Connecting to redis server %s ...'%(redis_host))
            self.rc = redis.StrictRedis(host=redis_host) 
            self.rc.ping() 
        except:
            print('DrillState(): redis connection to %s failed. Using %s instead.'%(redis_host,LOCAL_HOST))
            self.rc = redis.StrictRedis(host=LOCAL_HOST) 

        self.AHRS_estimator = AHRS_estimator
        self.update()
                

    def get(self, attr):
        try:    return getattr(self, attr)
        except: return None


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

        # Quaternion from sensor fuision (SFUS)
        self.quat0_sfus = np.array([self.quaternion_x, self.quaternion_y, self.quaternion_z, self.quaternion_w], dtype=np.float64)
#            norm = np.linalg.norm(self.quat0_sfus)
#            if norm is not None and norm > 1e-1: self.quat0_sfus /= float(norm) # normalize just in case
#            else: self.quat0_sfus = np.array([1,0,0,0])

        self.update_oricalib('sfus')
        self.quat_sfus = self.quat0_sfus # no calibration
        self.quat_sfus = self.apply_oricalib(self.quat0_sfus, self.oricalib_sfus) # apply calibration

        q = Rotation.from_quat(self.quat0_sfus)
        for ii in range(3): self.xi0_sfus[ii] = q.apply(self.xi0[ii]) # sensor x,y,z axis 

        q = Rotation.from_quat(self.quat_sfus)
        for ii in range(3): self.xi_sfus[ii] = q.apply(self.xi0[ii]) # calibrated sensor x,y,z axis 

        x1,x2,x3 = self.xi_sfus[0] # sensor x axis 
        z1,z2,z3 = self.xi_sfus[2] # sensor z axis (drill axis)
        self.inclination_sfus = 180 - np.rad2deg(np.arccos(z3)) # pitch (theta)
        self.azimuth_sfus     = np.rad2deg(np.arctan2(z2,z1)) # yaw (phi)
        self.roll_sfus        = np.rad2deg(np.arctan2(x2,x1)) # roll (psi)

        # DEBUG: CHECK INCL, AZIM, ROLL CALCULATIONS
        if 0:
            self.inclination_sfus_r, self.azimuth_sfus_r, self.roll_sfus_r = quat_to_euler(self.quat_sfus)
            print(self.inclination_sfus,   self.azimuth_sfus,   self.roll_sfus)
            print(self.inclination_sfus_r, self.azimuth_sfus_r, self.roll_sfus_r)

        #-----------------

        #self.update_oricalib('ahrs')

        # Quaternion from AHRS 
#        self.quat0_ahrs = wxyz_to_xyzw(AHRS_estimators[self.AHRS_estimator].estimate(acc=self.accelerometer_vec, mag=self.magnetometer_vec)) # note estimate() returns w,x,y,z ordered quats
#        self.quat0_ahrs = np.array(self.quat0_ahrs, dtype=np.float64)
#        if np.size(self.quat0_ahrs) != 4 or np.any(np.isnan(self.quat0_ahrs)): self.quat0_ahrs = np.array([0,0,0,-1])
##        self.quat0_ahrs *= -1 # follow SFUS sign convention
#        self.quat_ahrs = self.quat0_ahrs # no calibration

#        self.quat_ahrs = self.apply_oricalib(self.quat0_ahrs, self.oricalib_ahrs) # apply calibration
##        self.quat_ahrs = self.quat0_ahrs # no calibration
##        self.quat_ahrs = np.matmul(np.diag([1,1,-1,-1]),self.quat_ahrs)
#        alpha,beta,gamma = quat_to_euler(self.quat_ahrs)
#        self.inclination_ahrs = beta  # pitch (theta)
#        self.azimuth_ahrs     = alpha # yaw   (phi)
#        self.roll_ahrs        = gamma # roll  (psi)
            
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


    ### Orientation

    def set_oricalib(self, xi, method):
        incl, azim, roll = 0, 0, 0
        if xi is not None:
            x1,x2,x3 = xi[0] # sensor x-axis
            roll = np.rad2deg(np.arctan2(x2,x1))
        print('state_drill.py: setting oricalib horiz (%s):'%(method), incl, azim, roll)
        self.rc.set('oricalib-%s-roll'%(method), -roll)
        self.rc.set('oricalib-%s-azim'%(method), 0)
        self.rc.set('oricalib-%s-incl'%(method), 0)
    
    def update_oricalib(self, method):
        oricalib = np.array([self.rc.get('oricalib-%s-%s'%(method,ang)) for ang in ['incl','azim','roll']], dtype=np.float64)
        if np.any(np.isnan(oricalib)): oricalib = np.array([0,0,0])
        setattr(self, 'oricalib_%s'%(method), oricalib)                    

    def apply_oricalib(self, quat0, oricalib):
        incl, azim, roll = oricalib
        q0 = Rotation.from_quat(quat0)
        # apply rotation around z-axis so drill roll is zero when spring in trench (x) direction for plumb position
        qz = Rotation.from_rotvec(np.deg2rad(roll)*np.array([0,0,1]))
        q_calib = qz * q0
        return q_calib.as_quat()
        
    def set_AHRS_estimator(self, name):
        self.AHRS_estimator = name

    def get_spin(self):
        # z-component of angular velocity vector, i.e. spin about drill (z) axis (deg/s)
        DEGS_TO_RPM = 1/6 
        return self.gyroscope_z * DEGS_TO_RPM # convert deg/s to RPM (will be zero if USE_BNO055_FOR_ORIENTATION is false)

    def save_bno055_calibration(self, slot):
        print('state_drill.py: Saving calibration in slot %i'% slot)
        self.rc.publish('downhole','bno055-calibrate:%d,%d' %(1, slot))
    
    def load_bno055_calibration(self, slot):
        print('state_drill.py: Loading calibration from slot %i'% slot)
        self.rc.publish('downhole','bno055-calibrate:%d,%d' %(0, slot))

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
        

def quat_to_euler(quat):

    if Rotation is not None:
        try:    rot = Rotation.from_quat(quat) # might fail if BNO055 is not ready (internal calibration not ready or error) => quat not normalized
        except: rot = Rotation.from_quat([0,0,0,1])
        alpha, beta, gamma = rot.as_euler('ZYZ', degrees=True) # intrinsic rotations, this order gives the correct inclination and azimuth values for drill axis "r" (see above)
    else:
        alpha, beta, gamma = 0, 0, 0

    incl = 180-beta  # pitch (theta)
    azim = alpha # yaw   (phi)
    roll = gamma # roll  (psi)

    return incl, azim, roll
    
def xyzw_to_wxyz(q): return np.roll(q,1)
def wxyz_to_xyzw(q): return np.roll(q,-1)
    
