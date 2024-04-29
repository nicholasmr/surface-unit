# N. Rathmann <rathmann@nbi.dk>, 2019-2024

DEBUG_IS_LOCALHOST = False # testing code on local host, so assume this is the REDIS drill host

IS_UNDEPLOYED = True # not deployed to field with EGRIP network, drill host has address DRILL_HOST_LAN instead of DRILL_HOST

#----------------------
# Drill host
#----------------------

LOCAL_HOST = '127.0.0.1'
DRILL_HOST = '10.2.3.10' # IP address of drill host (surface unit) when field deployed; may change depending on surface unit number
DRILL_HOST_LAN = '10.217.96.247' # e.g. KU DHCP leased IP

#----------------------
# REDIS host
#----------------------

import socket

if socket.gethostname() == 'drill' or DEBUG_IS_LOCALHOST: 
    REDIS_HOST = LOCAL_HOST
    
else:         
    if IS_UNDEPLOYED: # is undeployed?
        print('*** UNDEPLOYED MODE (settings.py): Overriding DRILL_HOST (%s) with DHCP-given IP (%s)'%(DRILL_HOST, DRILL_HOST_LAN))
        DRILL_HOST = DRILL_HOST_LAN # on drill run "dhcpcd" and note down the "leased IP" here

    REDIS_HOST = DRILL_HOST

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
PRECISION_LOAD  = 1
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

