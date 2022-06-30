# N. Rathmann <rathmann@nbi.dk>, 2019-2022

#----------------------
# Drill host
#----------------------
DRILL_HOST = "10.2.3.10" # Assumed IP address for drill host (raspberry pi in surface unit), may change depending on surface unit number

#----------------------
# REDIS host
#----------------------
import socket
if socket.gethostname() == 'drill': REDIS_HOST = '127.0.0.1'
else:                               REDIS_HOST = DRILL_HOST

#----------------------
# Cable linear density for load-cable calculation
#----------------------
CABLE_DENSITY = 0.165 # kg/m

#----------------------
# Orientation settings
#----------------------
USE_BNO055_FOR_ORIENTATION = True # Use BNO055 triaxial information for determining orientation? Else use inclinometer.
parvalux_tube_free_hanging = [-0.04, 1.05, -9.64] # Gravity vector when drill is hanging plumb.  

#----------------------
# Sensor reference values
#----------------------
HAMMER_MAX = 255

#----------------------
# Safe range for drill sensors
#----------------------
warn__motor_current           = [0,13]     # Amps
warn__motor_rpm               = [-70,70]   # RPM
warn__temperature_motor       = [-30,60]   # deg C
warn__temperature_electronics = [-30,60]   # deg C
warn__pressure                = [700,1100] # mbar
warn__hammer                  = [0,10]     # percent
warn__spin                    = [0,10]     # rpm
warn__corelength              = [0.0,3.0]  # metre

#----------------------
# Safe range for surface sensors
#----------------------
warn__load     = [0,1200]    # kg
warn__velocity = [-1.2,1.2]  # m/s


# DISCARD
#inching_time     = 1.0    # seconds
#inching_pwm      = 90 # KM og NR: new val of 90 is more appropriate
#inching_pwm__FLT = 90 # Filter (FLT) valve open close (requires at least 60 deg. rot.)
#inching_pwm__SB  = 15 # Super banger (SB) disengage should be no more than 15 deg. to not rotate out of baronet.

