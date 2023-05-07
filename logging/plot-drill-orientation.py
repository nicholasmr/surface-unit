#!/usr/bin/python
# N. Rathmann, 2017-2023

import numpy as np
import code # code.interact(local=locals())
import sys, os, time, csv, datetime, time, json, scipy
import matplotlib.pyplot as plt
import pandas as pd

from scipy.optimize import minimize
from scipy.signal import savgol_filter

from ahrs.filters import SAAM, FAMC
from ahrs import Quaternion
saam = SAAM()

if len(sys.argv) != 3: sys.exit('usage: %s /mnt/logs/<LOGNAME> /output/path '%(sys.argv[0]))

#-----------------------
# Options
#-----------------------

RUN_SENSOR_ORIENTATION_CALIBRATION = 1

# Initial sensor orientation guess
x_opt, y_opt = -0.00, 0.000
#x_opt, y_opt = -0.0083, 0.0057

# Data bin size 
dz = 15 

# Fit rangge
Z0fit = 100 # ignore misfit with logger at depths shallower than this number
Z1fit = 2000 # ignore misfit with logger at depths deepter than this number

I0fit = int(Z0fit/dz)
#I1fit = int(Z1fit/dz) 
I1fit = -1 # no lower bound

#-----------------------
# Files
#-----------------------

OUTPATH  = str(sys.argv[-1]) # where to save images
DRILLLOG = str(sys.argv[1]) # drill log to plot
date_time_str0 = DRILLLOG[-10:] # log file date string

fname_logger = 'logger-2022-07-09-down.csv' # Logger data
#fname_logger = 'logger-2023-05-05-down.csv' # Logger data

#-----------------------
# Initialize
#-----------------------

Z_MAX, Z_MIN = 0, -2800 # y axis limits

def empty_array(len): 
    arr = np.empty((len), dtype=float)
    arr[:] = np.nan
    return arr

flen = sum(1 for l in open(DRILLLOG, "r"))

z  = empty_array(flen) # depth
quat = np.zeros((flen,4))
DCM = np.zeros((flen,3,3)) # rotation matrix
inc, azi = empty_array(flen), empty_array(flen)

#-----------------------
# Load log file
#-----------------------

print('*** Loading log %s'%(DRILLLOG))

fh  = open(DRILLLOG, "r")
jj = 0

for ii, l in enumerate(fh):

    if "depth_encoder" not in l: 
        continue # not uphole message

    kk = l.find('{')
    l = l[kk:]

    try:    z[ii] = - json.loads(l)['depth_encoder']['depth']
    except: z[ii] = np.nan

    avec = np.array([json.loads(l)['accelerometer_x'], json.loads(l)['accelerometer_y'], json.loads(l)['accelerometer_z']])
    mvec = np.array([json.loads(l)['magnetometer_x'], json.loads(l)['magnetometer_y'], json.loads(l)['magnetometer_z']]) 
    quat[jj,:] = saam.estimate(acc=avec, mag=mvec) # quaternion
    DCM[jj,:,:] = Quaternion(quat[jj,:]).to_DCM()

    jj +=1


fh.close()
print('... done')
        
# Remove empty parts of arrays for incl and azi plots.
jjmax = jj-1
DCM = DCM[0:(jjmax+1), :,:]
Z = z[0:(jjmax+1)]

#-----------------------
# BNO055 orientation calibration
#-----------------------

z_bin_full = np.arange(0, abs(Z_MIN)+dz, dz) # new z-axis
z_bin = z_bin_full[1:]
        
def binned_stats(df, depth):
    groups = df.groupby(pd.cut(depth, z_bin_full))
    meanbins, varbins = groups.mean().to_numpy(), groups.var().to_numpy()
    return meanbins[:], varbins[:] # binned: [ mean(inc), var(inc) ]
    
### Logger data

fields = ['azimuth', 'bottom_sensor', 'compass', 'depth', 'fluxgate_1_raw', 'fluxgate_2_raw', 'inclination', 'inclinometer_1_raw', 'inclinometer_2_raw', 'lower_diameter', \
          'lower_diameter_max_raw', 'lower_diameter_min_raw', 'pressure', 'pressure_raw', 'record_number', 'temperature_pressure_transducer', 'thermistor_high', 'thermistor_high_raw', \
          'upper_diameter', 'upper_diameter_max_raw', 'upper_diameter_min_raw', 'thermistor_low', 'thermistor_low_raw']
          
flogger = os.path.join(os.path.dirname(__file__), "logger-data/%s"%(fname_logger))
df_logger = pd.read_csv(flogger, names=fields, header=1)
#df_logger['depth'] *= -1

# Mean (binned)
depthm_logger, _ = binned_stats(df_logger['depth'], df_logger['depth']) 
incm_logger, _   = binned_stats(df_logger['inclination'], df_logger['depth']) 

# Raw
inc_logger, depth_logger = df_logger['inclination'].to_numpy(), df_logger['depth'].to_numpy()
    
### Drill data

def inc_given_sensor_xyplane(x,y):
    sensordir = -np.array([x,y,np.sqrt(1-x**2-y**2)]) # presumed BNO055 sensor orientation
    drilldir = np.array([np.matmul(DCM[ii,:,:], sensordir) for ii in np.arange(jjmax+1)]) 
    incr = np.rad2deg(np.arccos(drilldir[:,2])) # raw inclination data
    df = pd.DataFrame(zip(Z,incr), columns = ['depth','inclination'])
    incm, _ = binned_stats(df['inclination'], df['depth'])
    return incm, incr, Z

if RUN_SENSOR_ORIENTATION_CALIBRATION:

    print('*** Estimating BNO055 sensor orientation')

    # Misfit measure
    def J(xy):
        incm, _, _ = inc_given_sensor_xyplane(xy[0], xy[1])
        errsq = np.power(incm - incm_logger, 2)
        J = np.nansum(errsq[I0fit:I1fit])
        return J
        
    paramvec = [x_opt, y_opt] # init guess
#    bounds = [(-0.1,0.1), (-0.1,0.1)]
    bounds = [(-0.1,0.1), (-0.01,0.01)]
    res = minimize(J, paramvec, method='L-BFGS-B', bounds=bounds, tol=1e-4, options={'gtol': 1e-4, 'disp': True})
    x_opt, y_opt = res.x[0], res.x[1] # best fit
    print('... done: (x_opt, y_opt) = (%f,%f)'%(x_opt,y_opt))
    
else:
    print('*** Using pre-defined BNO055 sensor orientation: (x_opt, y_opt) = (%f,%f)'%(x_opt,y_opt))
    
### Best fit solution    
incm_drill, inc_drill, depth_drill = inc_given_sensor_xyplane(x_opt, y_opt)

### No calibration
incm_drill_nocal, _, _ = inc_given_sensor_xyplane(0, 0) 

#-----------------------
# Plot
#-----------------------

scale = 0.7
fig = plt.figure(figsize=(7,8))
c_drill, c_drill2, c_logger = '#1f78b4', '#9ecae1', 'k'
inclims = [0,7]

ax1 = plt.subplot(1,2,1)
ax2 = plt.subplot(1,2,2, sharey=ax1)

lbl_calibrated = 'Calibrated (x,y=%.4f,%.4f)'%(x_opt,y_opt)

### Mean plot

zz = -z_bin[I0fit:]

ax1.plot(incm_drill_nocal[I0fit:], zz, c=c_drill2,  lw=2, ls='--', label='Uncalibrated (x,y=0,0)', zorder=5)    
ax1.plot(incm_drill[I0fit:], zz, c=c_drill,  lw=2, label=lbl_calibrated, zorder=5)    
ax1.plot(incm_logger, -depthm_logger, c=c_logger, lw=2, label=fname_logger, zorder=4)

ax1.set_xlim(inclims); ax1.set_ylim([Z_MIN,0])
ax1.set_ylabel('$z$ (m)'); ax1.set_xlabel(r'$\theta$ (deg)')
ax1.set_yticks(np.arange(Z_MIN,0+1,200))
ax1.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
ax1.grid(); ax1.legend(); ax1.set_title('Mean (bin $dz$ = %.0f)'%(dz))

### Raw scatter plot

ax2.scatter(inc_logger, -depth_logger, marker='o', s=2**2, ec=c_logger, c='none', label=fname_logger)
ax2.scatter(inc_drill,  -depth_drill,  marker='o', s=2**2, ec=c_drill, c='none', label=lbl_calibrated)
ax2.set_xlim(inclims); ax2.set_xlabel(r'$\theta$ (deg)')
plt.setp(ax2.get_yticklabels(), visible=False)
ax2.grid(); ax2.legend(); ax2.set_title('Raw')

imgout = '%s/drill-orientation-%s.png'%(OUTPATH,date_time_str0)
print('*** Saving %s'%(imgout))
plt.savefig(imgout, dpi=300, bbox_inches='tight')

### Save as CSV

d = {
    'depth': zz, \
    'inclination': incm_drill[I0fit:], \
    'azimuth': 0*zz +np.nan, \
}

df = pd.DataFrame(data=d)
fcsv = 'drill-logs-processed/drill-orientation-%s.csv'%(date_time_str0)
print('*** Saving %s'%(fcsv))
df.to_csv(fcsv, index=False)

