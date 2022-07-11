# N. Rathmann <rathmann@nbi.dk>, 2019-2022

import redis, json, datetime, time
import numpy as np
from settings import *

try: 
    # might fail if module not available or clock is incorrect set and reference magnetic field geoid (for a given date) is therefore unavailable.
    from ahrs.filters import SAAM
    from ahrs import Quaternion
except: 
    USE_BNO055_FOR_ORIENTATION = False

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
    temperature_vesc           = 0
    
    pressure_electronics = 0
    pressure_topplug     = 0
    pressure_gear1       = 0
    pressure_gear2       = 0
    
    hammer = 0
    tachometer = 0
    
    inclination = 0 # calculated value, not direct sensor value
    azimuth     = 0 # calculated value, not direct sensor value
    spin        = 0 # = gyroscope_z
    quat        = [0,0,0,0] # calculated using AHRS
    drilldir    = [0,0,1]   # calculated using AHRS
    
    downhole_voltage = 0.0
    
    # BNO055 triaxial values
    accelerometer_x = 0
    accelerometer_y = 0
    accelerometer_z = 0
    magnetometer_x = 0
    magnetometer_y = 0
    magnetometer_z = 0
    gyroscope_x = 0
    gyroscope_y = 0
    gyroscope_z = 0
    
    # Inclinometer
    inclination_x = 0
    inclination_y = 0
    
    # Was the drill state update recently?
    recieved        = '2022-01-01 00:00:00'
    islive          = False # True = connection is live, else False
    islivethreshold = 10 # seconds before drill state is assumed dead (unless a new state was recieved)
    
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

        if USE_BNO055_FOR_ORIENTATION: self.saam = SAAM() # https://ahrs.readthedocs.io/en/latest/filters/saam.html
        self.refdir = np.array([0,0,1]) # BNO055 chip orientation; used to determine orientation with SAAM
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
        self.inclination, self.azimuth = self.get_orientation() # might be heavy calculation, allowing skipping it if requested.
        self.accelerometer_magnitude = np.sqrt(self.accelerometer_x**2 + self.accelerometer_y**2 + self.accelerometer_z**2)
        self.magnetometer_magnitude  = np.sqrt(self.magnetometer_x**2  + self.magnetometer_y**2  + self.magnetometer_z**2)
        self.gyroscope_magnitude     = np.sqrt(self.gyroscope_x**2     + self.gyroscope_y**2     + self.gyroscope_z**2)

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
        lastrecieved = datetime.datetime.strptime(self.recieved, '%Y-%m-%d %H:%M:%S')
        dt = (now - lastrecieved).total_seconds()
        self.islive = dt < self.islivethreshold
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
        if   motor_id == 0: self.rc.publish('downhole','motor-config:parvalux')
        elif motor_id == 1: self.rc.publish('downhole','motor-config:skateboard')
        elif motor_id == 2: self.rc.publish('downhole','motor-config:hacker')
        elif motor_id == 3: self.rc.publish('downhole','motor-config:plettenberg')

    def set_tacho(self, tacho_index):
        self.rc.publish('downhole', 'motor-set-tachometer: %d'%(tacho_index))

    ### Orientation
    
    def get_spin(self):
        # z-component of angular velocity vector, i.e. spin about drill (z) axis (deg/s)
        return self.gyroscope_z * 1/6 # convert deg/s to RPM (will be zero if USE_BNO055_FOR_ORIENTATION is false)

    def get_orientation(self, USE_AHRS=True):
    
        azi, incl = 0, 0

        if USE_BNO055_FOR_ORIENTATION:
            
            if USE_AHRS:
                avec = np.array([self.accelerometer_x, self.accelerometer_y, self.accelerometer_z])
                mvec = np.array([self.magnetometer_x,  self.magnetometer_y,  self.magnetometer_z])
                if np.linalg.norm(avec) > 0 and np.linalg.norm(mvec) > 0: # orientation information not dead?
                    self.quat = self.saam.estimate(acc=avec, mag=mvec) # quaternion
                    self.drilldir = np.matmul(Quaternion(self.quat).to_DCM(), self.refdir) # drill orientation vector: matrix--vector product between rotation matrix (derived from quaternion) and vertical (plumb) direction
                    incl = np.rad2deg(np.arccos(-self.drilldir[2]))
                    azi  = np.rad2deg(np.arctan2(self.drilldir[1],self.drilldir[0]))
            else:
                azi  = np.rad2deg(math.atan2(self.accelerometer_x, -self.accelerometer_y)) % 360
                incl = np.rad2deg(vector_angle([self.accelerometer_x, self.accelerometer_y, self.accelerometer_z], parvalux_tube_free_hanging))
           
        # Use inclinometer instead...
        else:

#           JC's calculation        
#            x = math.tan(np.deg2rad(self.inclination_x))
#            y = math.tan(np.deg2rad(self.inclination_y))
#            azi = math.degrees(math.atan2(y, x)) % 360
            
            # This calculation gives the angle between (0,0,1) (normalized gravity direction) and the x-y inclinometer plane normal: incl = acos( inner([,,], [0,0,1]) )
            pitch, roll = np.deg2rad(self.inclination_x), np.deg2rad(self.inclination_y)
            incl = np.rad2deg( np.arccos(np.cos(pitch)*np.cos(roll)) )

        return (round(incl,2), round(azi,2))

