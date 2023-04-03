DRILL_HOST = "10.2.3.10"
#DRILL_HOST = "127.0.0.1"

screenshot_directory = "/mnt/logs/screenshots/"

warn_load     = 1200  # kg
warn_hammer   = 40.   # native value (640 is max)
warn_sliprate = 1     # 1 rpm
warn_motorI   = 14    # I
warn_vdrill   = 1.2e2 # cm/s
warn_temp     = 60    # deg C
warm_corelen  = 3.5 # metre
max_hammer    = 255


inching_time     = 1.0    # seconds
inching_pwm      = 90 # KM og NR: new val of 90 is more appropriate
inching_pwm__FLT = 90 # Filter (FLT) valve open close (requires at least 60 deg. rot.)
inching_pwm__SB  = 15 # Super banger (SB) disengage should be no more than 15 deg. to not rotate out of baronet.

# Set calibration matrix here
accCalibration = [[ 0.99978962,  0.00539519, -0.0197891],
                  [-0.00539519, 0.999985, 0.0000533885],
                  [0.0197891, 0.0000533885, 0.999804]]


def cable_weight(depth):
    return 0.165 * depth # KM og NR: 0.165 is the most accurate val


