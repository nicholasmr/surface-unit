import pyvesc, datetime, json

class Ping(metaclass=pyvesc.VESCMessage):
    id = 128

    fields = []
    
    def as_json(self):
        return json.dumps({'packet': 'Ping'})

class DownholeState(metaclass=pyvesc.VESCMessage):
    id = 129
    fields = [
        ('hammer', 'B'),
        ('motor_state', 'B'),
        ('motor_voltage', 'h'),
        ('motor_current', 'h'),
        ('motor_rpm', 'h'),
        ('motor_duty_cycle', 'h'),
        ('motor_controller_temp', 'h'),
        ('inclination_x', 'h'),
        ('inclination_y', 'h'),
        ('temperature_electronics', 'h'),
        ('temperature_motor', 'h'),
        ('pressure_electronics', 'H'),
        ('pressure_topplug', 'H'),
        ('pressure_gear1', 'H'),
        ('pressure_gear2', 'H'),
        ('aux_temperature_electronics', 'h'),
        ('aux_temperature_topplug', 'h'),
        ('aux_temperature_gear1', 'h'),
        ('aux_temperature_gear2', 'h'),
        ('accelerometer_x', 'h'),
        ('accelerometer_y', 'h'),
        ('accelerometer_z', 'h'),
        ('gyroscope_x', 'h'),
        ('gyroscope_y', 'h'),
        ('gyroscope_z', 'h'),
        ('downhole_voltage', 'H'),
        ('tachometer', 'l'),
        ('gyro_alarm', 'B'),
        ('magnetometer_x', 'h'),
        ('magnetometer_y', 'h'),
        ('magnetometer_z', 'h'),

        ('linearaccel_x', 'h'),
        ('linearaccel_y', 'h'),
        ('linearaccel_z', 'h'),

        ('gravity_x', 'h'),
        ('gravity_y', 'h'),
        ('gravity_z', 'h'),

        ('quaternion_w', 'h'),
        ('quaternion_x', 'h'),
        ('quaternion_y', 'h'),
        ('quaternion_z', 'h'),

    ]

    transfer_functions = {
#        'hammer': lambda x: x,
#        'motor_state': lambda x: x,

        'motor_voltage': lambda x: x / 100,
        'motor_current': lambda x: x / 100,
        'motor_rpm': lambda x: x / 100,
        'motor_duty_cycle': lambda x: x / 1000,
        'motor_controller_temp': lambda x: x / 100,
 
         #'inclination_x': lambda x: x/100.0 - 35,
         #'inclination_y': lambda x: x/100.0 - 35,
         #
        'inclination_x': lambda x: x/100.0,
         'inclination_y': lambda x: x/100.0,

        'temperature_electronics': lambda x: x / 10,
        'temperature_motor': lambda x: x / 10,

#        'pressure_electronics': lambda x: x,
#        'pressure_topplug': lambda x: x,
#        'pressure_gear1': lambda x: x,
#        'pressure_gear2': lambda x: x,

#        'aux_temperature_electronics': lambda x: x,
#        'aux_temperature_topplug': lambda x: x,
#        'aux_temperature_gear1': lambda x: x,
#        'aux_temperature_gear2': lambda x: x,

        'accelerometer_x': lambda x: x / 100,
        'accelerometer_y': lambda x: x / 100,
        'accelerometer_z': lambda x: x / 100,

        'gyroscope_x': lambda x: x / 100,
        'gyroscope_y': lambda x: x / 100,
        'gyroscope_z': lambda x: x / 100,
        
        'downhole_voltage': lambda x: x/100,

        'tachometer': lambda x: x,

#        'gyro_alarm': lambda x: 10 * x,

        
        'magnetometer_x': lambda x: x / 100,
        'magnetometer_y': lambda x: x / 100,
        'magnetometer_z': lambda x: x / 100,

        'linearaccel_x': lambda x: x / 100,
        'linearaccel_y': lambda x: x / 100,
        'linearaccel_z': lambda x: x / 100,

        'gravity_x': lambda x: x / 100,
        'gravity_y': lambda x: x / 100,
        'gravity_z': lambda x: x / 100,

        'quaternion_w': lambda x: x / 100,
        'quaternion_x': lambda x: x / 100,
        'quaternion_y': lambda x: x / 100,
        'quaternion_z': lambda x: x / 100,
    }

    def __init__(self):
        super()

        self.received = datetime.datetime.now()

    def __setattr__(self, item, value):
        if item in self.transfer_functions:
            return dict.__setattr__(self, item, self.transfer_functions[item](value))
        else:
            return dict.__setattr__(self, item, value)
    
    def print(self):
        print("Hammer:                         %f" % self.hammer)
        print()
        print("Motor state:                    %d" % self.motor_state)
        print("Motor voltage:                  %.02f V" % self.motor_voltage)
        print("Motor current:                  %.02f A" % self.motor_current)
        print("Motor RPM:                      %.02f rpm" % self.motor_rpm)
        print("Motor duty cycle:               %.02f" % self.motor_duty_cycle)
        print("Motor controller temperature:   %.02f deg C" % self.motor_controller_temp)
        print()
        print("Inclination:                    %.02f x %.02f" % (self.inclination_x, self.inclination_y))
        print()
        print("Temperature, electronics:       %.02f deg C" % (self.temperature_electronics / 10))
        print("Temperature, motor:             %.02f deg C" % (self.temperature_motor / 10))
        print()
        print("Electronics:                    %.02f mbar %.02f deg C" % (self.pressure_electronics, self.aux_temperature_electronics))
        print("Top plug:                       %.02f mbar %.02f deg C" % (self.pressure_topplug, self.aux_temperature_topplug))
        print("Gear section sensor 1:          %.02f mbar %.02f deg C" % (self.pressure_gear1, self.aux_temperature_gear1))
        print("Gear section sensor 2:          %.02f mbar %.02f deg C" % (self.pressure_gear2, self.aux_temperature_gear2))
        print()
        print("Accelerometer:                  X: %.02f N\tY: %.02f N\tZ: %.02f N" % (self.accelerometer_x, self.accelerometer_y, self.accelerometer_z))
        print("Gyroscope:                      X: %.02f ?\tY: %.02f ?\tZ: %.02f ?" % (self.gyroscope_x, self.gyroscope_y, self.gyroscope_z))
        print()
        print("Downhole voltage:               %.02f V" % self.motor_controller_temp)
        print()
        print("Tachometer:                     %d" % self.tachometer)
        print("Gyro alarm:                     %d" % self.gyro_alarm)
            
    def as_dict(self):
        d = {
            "received": self.received.strftime("%Y-%m-%d %H:%M:%S"),
            "hammer": self.hammer,
            "motor_state": self.motor_state,
            'motor_voltage': self.motor_voltage,
            'motor_current': self.motor_current,
            'motor_rpm': self.motor_rpm,
            'motor_duty_cycle': self.motor_duty_cycle,
            'motor_controller_temp': self.motor_controller_temp,
            'inclination_x': self.inclination_x,
            'inclination_y': self.inclination_y,
            'temperature_electronics': self.temperature_electronics,
            'temperature_motor': self.temperature_motor,
            'pressure_electronics': self.pressure_electronics,
            'pressure_topplug': self.pressure_topplug,
            'pressure_gear1': self.pressure_gear1,
            'pressure_gear2': self.pressure_gear2,
            'aux_temperature_electronics': self.aux_temperature_electronics,
            'aux_temperature_topplug': self.aux_temperature_topplug,
            'aux_temperature_gear1': self.aux_temperature_gear1,
            'aux_temperature_gear2': self.aux_temperature_gear2,
            'accelerometer_x': self.accelerometer_x,
            'accelerometer_y': self.accelerometer_y,
            'accelerometer_z': self.accelerometer_z,
            'gyroscope_x': self.gyroscope_x,
            'gyroscope_y': self.gyroscope_y,
            'gyroscope_z': self.gyroscope_z,
            'downhole_voltage': self.downhole_voltage,
            'tachometer': self.tachometer,
            'gyro_alarm': self.gyro_alarm,
            'magnetometer_x': self.magnetometer_x,
            'magnetometer_y': self.magnetometer_y,
            'magnetometer_z': self.magnetometer_z,

            'linearaccel_x': self.linearaccel_x,
            'linearaccel_y': self.linearaccel_y,
            'linearaccel_z': self.linearaccel_z,

            'gravity_x': self.gravity_x,
            'gravity_y': self.gravity_y,
            'gravity_z': self.gravity_z,

            'quaternion_w': self.quaternion_w,
            'quaternion_x': self.quaternion_x,
            'quaternion_y': self.quaternion_y,
            'quaternion_z': self.quaternion_z,
        }
        

        # This is kind of hacky. Depth and load are tagged on to the packet in uphole.py,
        # although they are technically values in the surface realm. It is to have current
        # load and depth at the exact times of the uphole packet.
        if hasattr(self, 'depth_encoder'):
            d.update({'depth_encoder': self.depth_encoder})
            
        if hasattr(self, 'load_cell'):
            d.update({'load_cell': self.load_cell})

        for method in ['sfus','ahrs']:
            for i in ['azim','incl','roll']:
                field = 'oricalib_%s_%s'%(method,i)
                if hasattr(self, field):
                    d.update({field: getattr(self, field)})
    
        return d

    def get_inclination(self):
        ix = self.inclination_x
        iy = self.inclination_y

    def as_json(self):
        return json.dumps(self.as_dict())

    def as_csv_entry(self):
        pass
    

class MotorLoadConfig(metaclass=pyvesc.VESCMessage):
    id = 130

    fields = []

class MotorStop(metaclass=pyvesc.VESCMessage):
    id = 131

    fields = []

class MotorStartPWM(metaclass=pyvesc.VESCMessage):
    id = 132

    fields = [
        ('pwm', 'h')
    ]


class MotorStartRPM(metaclass=pyvesc.VESCMessage):
    id = 133

    fields = [
        ('rpm', 'h')
    ]

class MotorRotateBy(metaclass=pyvesc.VESCMessage):
    id = 142

    fields = [
        ('degrees_d', 'h'),('rpm_d', 'h')
    ]
    

class MotorJerk(metaclass=pyvesc.VESCMessage):
    id = 134

    fields = []

    
class MotorJerkReverse(metaclass=pyvesc.VESCMessage):
    id = 135

    fields = []

class MotorSetThrottle(metaclass=pyvesc.VESCMessage):
    id = 136

    fields = []

class MotorSetVESCPassthru(metaclass=pyvesc.VESCMessage):
    id = 137

    fields = []

class MotorFlashConfig(metaclass=pyvesc.VESCMessage):
    id = 138

    fields = [
        ('motor_config_id', 'B')
    ]

class GyroSlipAlarm(metaclass=pyvesc.VESCMessage):
    id = 139
    fields = []

    def __init__(self):
        super()
        self.received = datetime.datetime.now()

    def as_json(self):
        return json.dumps({'packet': 'GyroSlipAlarm', 'received': str(self.received)})


class SetAlarm(metaclass=pyvesc.VESCMessage):
    id = 140

    fields = [
        ('alarm_id', 'B'),
        ('state', 'B'),
    ]

class MotorSetTachometer(metaclass=pyvesc.VESCMessage):
    id = 141

    fields = [
        ('tachometer', 'l')
    ]
