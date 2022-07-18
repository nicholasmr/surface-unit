# N. Rathmann <rathmann@nbi.dk>, 2019-2022

#----------------------
# Drill host
#----------------------
DRILL_HOST = '10.2.3.10' # Assumed IP address for drill host (raspberry pi in surface unit), may change depending on surface unit number
LOCAL_HOST = '127.0.0.1'

#----------------------
# REDIS host
#----------------------
import socket
if socket.gethostname() == 'drill': REDIS_HOST = LOCAL_HOST
else:                               REDIS_HOST = DRILL_HOST
#REDIS_HOST = LOCAL_HOST

#----------------------
# Cable linear density for load-cable calculation
#----------------------
CABLE_DENSITY = 0.165 # kg/m

#----------------------
# Orientation settings
#----------------------
USE_BNO055_FOR_ORIENTATION = True # Use BNO055 triaxial information for determining orientation? Else use inclinometer.
#parvalux_tube_free_hanging = [-0.04, 1.05, -9.64] # Gravity vector when drill is hanging plumb.  

#----------------------
# Sensor reference values
#----------------------
HAMMER_MAX = 255
TACHO_PRE_REV = 1/560

# Decimal point precisions for physical displays of surface unit
PRECISION_LOAD  = 2
PRECISION_DEPTH = 2

# Presumed max depth of core site
DEPTH_MAX = 2700

#----------------------
# Safe range for drill sensors
#----------------------
warn__motor_current           = [0,13]     # Amps
warn__motor_rpm               = [-75,75]   # RPM
warn__temperature_motor       = [-60,60]   # deg C
warn__temperature_electronics = [-60,60]   # deg C
warn__pressure                = [700,1100] # mbar
warn__hammer                  = [0,50]     # percent
warn__spin                    = [0,10]     # rpm
warn__corelength              = [0.0,4.0]  # metre
warn__downholevoltage         = [325,425]  # volt

#----------------------
# Safe range for surface sensors
#----------------------
warn__load     = [-100,1400] # kg
warn__velocity = [-130,130]  # cm/s

