import json, redis, math
from settings import cable_weight, DRILL_HOST
from drill_math import *

RPM_PER_RAD_S = 9.549296596425384
RPM_PER_D_S = (1/6)

USE_BNO055_FOR_INCL_AZI = True

parvalux_tube_free_hanging = [-0.04, 1.05, -9.64]

class DrillState():
    redis_connection = None
    
    def __init__(self, redis_connection=None):
        if redis_connection is None:
            self.redis_connection = redis.StrictRedis(host=DRILL_HOST)
        else:
            self.redis_connection = redis_connection

        self.update()

    def get(self, attr):
        try:
            return getattr(self, attr)
        except:
            return None

    def is_orientation_dead(self):
        return 0 == sum([
            self.get('accelerometer_x'),
            self.get('accelerometer_y'),
            self.get('accelerometer_z'),
            self.get('gyroscope_x'),
            self.get('gyroscope_x'),
            self.get('gyroscope_x'),
        ])
        
    def get_spin(self):
        if self.is_orientation_dead():
            return None
        
        try:
            return self.get('gyroscope_z') * RPM_PER_D_S
        except:
            return None

    def get_azimuth(self):
        if USE_BNO055_FOR_INCL_AZI:
            if self.is_orientation_dead():
                return None
            
            # TODO: Use Marius'+Matthias' algorithm for this + remember calibration matrix
            try:
                return math.degrees(math.atan2(self.accelerometer_x, -self.accelerometer_y)) % 360
            except:
                return None
        else:
            x = math.radians(self.get('inclination_x'))
            y = math.radians(self.get('inclination_y'))

            x = math.tan(x)
            y = math.tan(y)

            return math.degrees(math.atan2(y, x)) % 360

    def get_inclination(self):
        if USE_BNO055_FOR_INCL_AZI:
            try:
                ax = self.accelerometer_x
                ay = self.accelerometer_y
                az = self.accelerometer_z

                return math.degrees(vector_angle([ax, ay, az], parvalux_tube_free_hanging))
            except:
                return None
        else:
#            x = math.radians(self.get('inclination_x'))
#            y = math.radians(self.get('inclination_y'))
#
#            x = math.tan(x)
#            y = math.tan(y)
#
#            incl_vec_dist = math.sqrt(x**2 + y**2)
#
#            return math.degrees(math.atan(incl_vec_dist))

             # Nicholas' version
             # This calculation gives the angle between (0,0,1) (normalized gravity direction) and the x-y inclinometer plane normal: incl = acos( inner([,,], [0,0,1]) )
             pitch = np.deg2rad(json.loads(r.get('drill-state'))['inclination_x']);  # pitch
             roll  = np.deg2rad(json.loads(r.get('drill-state'))['inclination_y']);  # roll      
             incl  = np.arccos(np.cos(pitch)*np.cos(roll))
             return np.rad2deg(incl)
    
    def update(self):
        # Get the redis things
        try:
            redis_object = json.loads(self.redis_connection.get('drill-state'))
        except:
            redis_object = {}

        for key in redis_object:
            setattr(self, key, redis_object[key])



        # azimuth = Math.toDegrees(Math.atan2(ay, ax));
        # /*
        # if (ax > 0)
        #     azimuth = Math.toDegrees(Math.atan2(ay, ax));
        # else
        #     azimuth = Math.toDegrees(Math.atan2(ay, ax)) + 180;
        # */
        # double gravity = ax+ay+az;

        # ax = Math.toDegrees(Math.asin(ax/gravity));
        # ay = Math.toDegrees(Math.asin(ay/gravity));
        # az = Math.toDegrees(Math.asin(az/gravity));

            
# {'accelerometer_x': 0,
#  'accelerometer_y': 0,
#  'accelerometer_z': 0,
#  'aux_temperature_electronics': -50,
#  'aux_temperature_gear1': -50,
#  'aux_temperature_gear2': -50,
#  'aux_temperature_topplug': -50,
#  'downhole_voltage': 14459,
#  'gyroscope_x': 0,
#  'gyroscope_y': 0,
#  'gyroscope_z': 0,
#  'hammer': 97,
#  'inclination_x': 0,
#  'inclination_y': 0,
#  'motor_controller_temp': 0,
#  'motor_current': 0,
#  'motor_duty_cycle': 0,
#  'motor_rpm': 0,
#  'motor_state': 0,
#  'motor_voltage': 0,
#  'pressure_electronics': 0,
#  'pressure_gear1': 0,
#  'pressure_gear2': 0,
#  'pressure_topplug': 0,
#  'received': '2019-05-03 17:43:08',
#  'temperature_electronics': 0,
#  'temperature_motor': 0}


class SurfaceState():
    redis_connection = None
    
    def __init__(self, redis_connection=None):
        if redis_connection is None:
            self.redis_connection = redis.StrictRedis(host=DRILL_HOST)
        else:
            self.redis_connection = redis_connection

        self.update()

    def get(self, attr):
        try:
            return getattr(self, attr)
        except:
            return None
        
    def update(self):
        encoder = json.loads(self.redis_connection.get('depth-encoder'))
        loadcell = json.loads(self.redis_connection.get('load-cell'))

        # TODO: Ensure that the data is fresh
        self.depth = encoder["depth"] * -1
        self.velocity = encoder["velocity"] * -1

        self.load = loadcell["load"]


    def get_net_load(self):
        return self.load - cable_weight(self.depth)
        
    # TODO: move the liquid level detection logic here
