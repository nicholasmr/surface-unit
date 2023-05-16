#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2017-2023

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
print('mag_ref = (%.1f, %.1f, %.1f) %.1f'%(mag_ref[0],mag_ref[1],mag_ref[2], np.linalg.norm(mag_ref)))
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
        
    ### Inclinometer
    inclination_x = 0
    inclination_y = 0

    ### Derived orientation
    azimuth_sfus, inclination_sfus, roll_sfus = 0, 0, 0 
    azimuth_ahrs, inclination_ahrs, roll_ahrs = 0, 0, 0 
        
    quat0_ahrs = np.array([0,0,0,1]) # x,y,z,w
    quat0_sfus = np.array([0,0,0,1])

    oricalib_ahrs = np.array([0,0,0]) # azim, incl, roll
    oricalib_sfus = np.array([0,0,0])
    
    ### Communication status 
    # Was the drill state update recently?
    received        = '2022-01-01 00:00:00'
    islive          = False # True = connection is live, else False
    islivethreshold = 15 # seconds before drill state is assumed dead (unless a new state was received)
    
    ### Redis connection
    rc = None 
    
    
    def __init__(self, redis_host=LOCAL_HOST, AHRS_estimator='SAAM'):
    
        # redis connection (rc) object
        try:    
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

        self.update_oricalib('sfus')
        self.update_oricalib('ahrs')

        # Quaternion from sensor fuision (SFUS)
        if 1:
            self.quat0_sfus = np.array([self.quaternion_x, self.quaternion_y, self.quaternion_z, self.quaternion_w], dtype=np.float64)
            norm = np.linalg.norm(self.quat0_sfus)
            if norm is not None and norm > 1e-1: self.quat0_sfus /= float(norm) # normalize just in case
            else: self.quat0_sfus = np.array([1,0,0,0])
        else: 
            # debug
            self.quat0_sfus = Rotation.from_euler('ZXZ', [60, 90+4 + 1*50, 68], degrees=True).as_quat()
      
        self.quat_sfus = self.apply_oricalib(self.quat0_sfus, self.oricalib_sfus) # apply calibration
#        self.quat_sfus = self.quat0_sfus # no calibration
        alpha, beta, gamma = quat_to_euler(self.quat_sfus)
        self.inclination_sfus = beta  # pitch (theta)
        self.azimuth_sfus     = alpha # yaw   (phi)
        self.roll_sfus        = gamma # roll  (psi)

        # Quaternion from AHRS 
        self.quat0_ahrs = wxyz_to_xyzw(AHRS_estimators[self.AHRS_estimator].estimate(acc=self.accelerometer_vec, mag=self.magnetometer_vec)) # note estimate() returns w,x,y,z ordered quats
        self.quat0_ahrs = np.array(self.quat0_ahrs, dtype=np.float64)
        if np.size(self.quat0_ahrs) != 4 or np.any(np.isnan(self.quat0_ahrs)): self.quat0_ahrs = np.array([0,0,0,-1])
        self.quat0_ahrs *= -1 # follow SFUS sign convention

        self.quat_ahrs = self.apply_oricalib(self.quat0_ahrs, self.oricalib_ahrs) # apply calibration
#        self.quat_ahrs = self.quat0_ahrs # no calibration
#        self.quat_ahrs = np.matmul(np.diag([1,1,-1,-1]),self.quat_ahrs)
        alpha,beta,gamma = quat_to_euler(self.quat_ahrs)
        self.inclination_ahrs = beta  # pitch (theta)
        self.azimuth_ahrs     = alpha # yaw   (phi)
        self.roll_ahrs        = gamma # roll  (psi)
            
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
    
    def set_oricalib_horiz(self, quat0, method):
        if quat0 is None:
            azim, roll = 0, 0
        else:
            Rsensor = Rotation.from_quat(quat0) 
            azim, incl, roll = Rsensor.as_euler('ZYZ', degrees=True)
        self.rc.set('oricalib-%s-azim'%(method), -azim)
        self.rc.set('oricalib-%s-roll'%(method), -roll)
    
    def set_oricalib_vert(self, quat0, method):
        if quat0 is None:
            incl = 0
        else:
            Rsensor = Rotation.from_quat(quat0) 
            azim, incl, roll = Rsensor.as_euler('ZYZ', degrees=True)
            incl = 180-incl
        self.rc.set('oricalib-%s-incl'%(method), incl)
    
    def update_oricalib(self, method):
        oricalib = np.array([self.rc.get('oricalib-%s-%s'%(method,ang)) for ang in ['azim','incl','roll']], dtype=np.float64)
        if np.any(np.isnan(oricalib)): oricalib = np.array([0,0,0])
        setattr(self, 'oricalib_%s'%(method), oricalib)                    
            
    def apply_oricalib(self, quat0, oricalib):

        azim, incl, roll = oricalib
        q0 = Rotation.from_quat(quat0)
        
        # apply rotation around z-axis so drill azimuth zero is along tower
        qz = Rotation.from_rotvec(np.deg2rad(azim)*np.array([0,0,1]))
        
        # rotate drill around drill-axis to zero the roll when spring pointing away from driller's cabin
        q1 = qz*q0 # new drill orientation, aligned with tower
        drillax = q1.apply(np.array([0,0,1])) # drill axis
        qroll = Rotation.from_rotvec(np.deg2rad(roll)*drillax)
        
        # adjust inclination so zero when plumb, as measured on tower. 
        q2 = qroll*qz*q0
        springax = q2.apply(np.array([0,1,0])) # drill axis
        qtilt = Rotation.from_rotvec(np.deg2rad(incl)*springax)
        
        # combine all rotations
        q_calib = qtilt * qroll * qz * q0
        return q_calib.as_quat()
        
    def set_AHRS_estimator(self, name):
        self.AHRS_estimator = name


    def get_spin(self):
        # z-component of angular velocity vector, i.e. spin about drill (z) axis (deg/s)
        DEGS_TO_RPM = 1/6 
        return self.gyroscope_z * DEGS_TO_RPM # convert deg/s to RPM (will be zero if USE_BNO055_FOR_ORIENTATION is false)


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
        alpha, beta, gamma = rot.as_euler('ZXZ', degrees=True) # intrinsic rotations
        beta = 180-beta # to inclination
    else:
        alpha, beta, gamma = 0, 0, 0

    return alpha, beta, gamma
    
def xyzw_to_wxyz(q): return np.roll(q,1)
def wxyz_to_xyzw(q): return np.roll(q,-1)
    
