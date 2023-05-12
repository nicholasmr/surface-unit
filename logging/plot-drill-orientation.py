#!/usr/bin/python
# N. Rathmann, 2017-2023

import numpy as np
import code # code.interact(local=locals())
import sys, os, time, csv, datetime, time, json, scipy
import matplotlib.pyplot as plt
import pandas as pd

from scipy.optimize import minimize
from scipy.signal import savgol_filter

from scipy.spatial.transform import Rotation

from ahrs.filters import SAAM, FAMC
from ahrs import Quaternion
saam = SAAM()

import warnings
warnings.filterwarnings('ignore', message='.*Gimbal', )

if len(sys.argv) != 3: sys.exit('usage: %s /mnt/logs/<LOGNAME> /output/path '%(sys.argv[0]))

#-----------------------
# Options
#-----------------------

PLOT_AZIM = 0

RUN_SENSOR_ORIENTATION_CALIBRATION = 1

# How to determine orientation
METHOD_AHRS_DCM  = 0
METHOD_AHRS_QUAT = 1
METHOD_SFUS_QUAT = 0  # only 2023 data output the sensor fusion (SFUS) quats

# Inclination cutoff for average
incl_max = 6.2

# Azimuth delta
dazim = -180

# Initial sensor orientation guess
x_opt, y_opt, z_opt = 0, 0, 0
#x_opt, y_opt = -0.0083, 0.0057

# Data bin size 
dz = 15 

# y axis limits
Z_MAX = 0 
Z_MIN = -3000

# Fit rangge
Z0fit = 200 # ignore misfit with logger at depths shallower than this number
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
# Binning method
#-----------------------

z_bin_full = np.arange(0, abs(Z_MIN)+dz, dz) # new z-axis
z_bin = z_bin_full[1:]
        
def binned_stats(df, depth):
    groups = df.groupby(pd.cut(depth, z_bin_full))
    meanbins, varbins = groups.mean().to_numpy(), groups.var().to_numpy()
    return meanbins[:], varbins[:] 

#-----------------------
# Logger data
#-----------------------

fields = ['azimuth', 'bottom_sensor', 'compass', 'depth', 'fluxgate_1_raw', 'fluxgate_2_raw', 'inclination', 'inclinometer_1_raw', 'inclinometer_2_raw', 'lower_diameter', \
          'lower_diameter_max_raw', 'lower_diameter_min_raw', 'pressure', 'pressure_raw', 'record_number', 'temperature_pressure_transducer', 'thermistor_high', 'thermistor_high_raw', \
          'upper_diameter', 'upper_diameter_max_raw', 'upper_diameter_min_raw', 'thermistor_low', 'thermistor_low_raw']
          
flogger = os.path.join(os.path.dirname(__file__), "logger-data/%s"%(fname_logger))
df_logger = pd.read_csv(flogger, names=fields, header=1)

# Raw
incl_raw_logger, azim_raw_logger, depth_raw_logger = df_logger['inclination'].to_numpy(), df_logger['azimuth'].to_numpy(), df_logger['depth'].to_numpy()

# Mean (binned)
depth_mean_logger, _ = binned_stats(df_logger['depth'], df_logger['depth']) 
incl_mean_logger, _  = binned_stats(df_logger['inclination'], df_logger['depth']) 
azim_mean_logger, _  = binned_stats(df_logger['azimuth'], df_logger['depth']) 

## Apply azim delta
#azim_mean_logger -= dazim
#azim_raw_logger -= dazim

#-----------------------
# Load drill log 
#-----------------------

print('*** Loading log %s'%(DRILLLOG))

def xyzw_to_wxyz(q): return np.roll(q,1)
def wxyz_to_xyzw(q): return np.roll(q,-1)

### Initialize 

def empty_array(len): 
    arr = np.empty((len), dtype=float)
    arr[:] = np.nan
    return arr
flen = sum(1 for l in open(DRILLLOG, "r"))
z  = empty_array(flen) # depth
quat = np.zeros((flen,4))
DCM = np.zeros((flen,3,3)) # rotation matrix

### Loop through rows and get drill orientation for a given time

fh  = open(DRILLLOG, "r")
jj = 0

for ii, l in enumerate(fh):

    if "depth_encoder" not in l: continue # not uphole message

    kk = l.find('{')
    l = l[kk:]

    try:    z[ii] = abs(json.loads(l)['depth_encoder']['depth'])
    except: z[ii] = np.nan # will skip entry in analysis below if nan

    if not METHOD_SFUS_QUAT: # use AHRS?
        avec = np.array([json.loads(l)['accelerometer_x'], json.loads(l)['accelerometer_y'], json.loads(l)['accelerometer_z']])
        mvec = np.array([json.loads(l)['magnetometer_x'], json.loads(l)['magnetometer_y'], json.loads(l)['magnetometer_z']]) 
        q = saam.estimate(acc=avec, mag=mvec) # quaternion

        if np.size(q) != 4 or np.linalg.norm(q) < 1-1e-3: 
            quat[jj,:]  = None # bad normalization => ignored later on
            DCM[jj,:,:] = None
        else:               
            quat[jj,:]  = wxyz_to_xyzw(q)
            DCM[jj,:,:] = Rotation.from_quat(quat[jj,:]).as_matrix() # same
#            DCM[jj,:,:] = Quaternion(q).to_DCM() # same
    else:
        quat[jj,:] = np.array([ json.loads(l)['quaternion_x'], json.loads(l)['quaternion_y'], json.loads(l)['quaternion_z'], json.loads(l)['quaternion_w'] ]) 
        
    jj +=1


fh.close()
print('... done')
        
### Remove empty parts of array because we skipped rows without depth-counter values

jjmax = jj-1
DCM = DCM[0:(jjmax+1), :,:]
quat = quat[0:(jjmax+1),:] 
Z = z[0:(jjmax+1)]

#-----------------------
# BNO055 orientation calibration
#-----------------------

if METHOD_AHRS_DCM:
    def incl_from_sensor_rot(x, y):
        sensordir = -np.array([x,y,np.sqrt(1-x**2-y**2)]) # presumed BNO055 sensor orientation
        drilldir = np.array([np.matmul(DCM[ii,:,:], sensordir) for ii in np.arange(jjmax+1)]) 
        incl_raw = np.rad2deg(np.arccos(drilldir[:,2])) # raw inclination data
        incl_raw[incl_raw>incl_max] = np.nan
        df = pd.DataFrame(zip(Z,incl_raw), columns = ['depth','inclination'])
        incl_mean, _ = binned_stats(df['inclination'], df['depth'])
        azim_mean, azim_raw = 0*incl_mean, 0*incl_raw
        return incl_mean, incl_raw, azim_mean, azim_raw, Z
else:
    def incl_from_sensor_rot(rotx, roty):
        I = np.nonzero(~np.isnan(quat[:,0]))[0] # ignore badly normalized or missing data
        q0 = Rotation.from_quat(quat[I,:]) 
        qx = Rotation.from_euler('x', rotx, degrees=True)
        qy = Rotation.from_euler('y', roty, degrees=True)
#        qz = Rotation.from_euler('y', roty, degrees=True)
        q = qy*qx*q0 # apply calibration # rotated sensor plane 
        eulerangles = q.as_euler('ZXZ', degrees=True) # intrinsic rotations
        incl_raw = np.zeros(len(Z))*np.nan
        azim_raw = np.zeros(len(Z))*np.nan
        incl_raw[I] = 180-eulerangles[:,1] # to inclination
        azim_raw[I] = eulerangles[:,0] + 180
        Irm = np.nonzero(incl_raw>incl_max)[0]
        incl_raw[Irm] = np.nan
        azim_raw[Irm] = np.nan
        df = pd.DataFrame(zip(Z,incl_raw), columns = ['depth','inclination'])
        incl_mean, _ = binned_stats(df['inclination'], df['depth'])
        df = pd.DataFrame(zip(Z,azim_raw), columns = ['depth','azimuth'])
        azim_mean, _ = binned_stats(df['azimuth'], df['depth'])
        return incl_mean, incl_raw, azim_mean, azim_raw, Z


if RUN_SENSOR_ORIENTATION_CALIBRATION:
    print('*** Estimating drill orientation from sensor data')

    # Misfit measure
    def J(xy):
        incl_mean, _, _, _, _ = incl_from_sensor_rot(xy[0], xy[1])
        errsq = np.power(incl_mean - incl_mean_logger, 2)
        J = np.nansum(errsq[I0fit:I1fit])
        return J
        
    paramvec = [x_opt, y_opt] # init guess
#    bounds = [(-0.1,0.1), (-0.1,0.1)]
    if METHOD_AHRS_DCM: bounds = [(-0.1,0.1), (-0.01,0.01)]
    else:               bounds = [(-2,+2), (-2,+2)] 
    res = minimize(J, paramvec, method='L-BFGS-B', bounds=bounds, tol=1e-4, options={'gtol': 1e-2, 'disp': True})
    x_opt, y_opt = res.x[0], res.x[1] # best fit
    print('... done: (x_opt, y_opt) = (%f,%f)'%(x_opt,y_opt))
else:
    print('*** Using pre-defined BNO055 sensor orientation: (x_opt, y_opt) = (%f,%f)'%(x_opt,y_opt))
    
# Best fit solution    
incl_mean, incl_raw, azim_mean, azim_raw, depth_drill = incl_from_sensor_rot(x_opt, y_opt)

# No calibration
incl0_mean, incl0_raw, azim0_mean, azim0_raw, _ = incl_from_sensor_rot(0, 0) 

#-----------------------
# Plot
#-----------------------

print('*** Plotting')

scale = 0.7
fig = plt.figure(figsize=(7.5*(2 if PLOT_AZIM else 1),8))

c_logger = 'k'
c_drill  = '#e31a1c'
c_drill2 = '#fb9a99'

inclims = [0,7]

cols = 4 if PLOT_AZIM else 2
ax1 = plt.subplot(1,cols,1)
ax2 = plt.subplot(1,cols,2, sharey=ax1)
if PLOT_AZIM:
    ax3 = plt.subplot(1,cols,3, sharey=ax1)
    ax4 = plt.subplot(1,cols,4, sharey=ax1)

lbl_calibrated = 'Calibrated (x,y=%.3f,%.3f)'%(x_opt,y_opt)
lbl_uncalibrated = 'Uncalibrated (x,y=0,0)'

zz = -z_bin[I0fit:] # z axis of binned (mean) profiles

kwargs_legend = {'fancybox':False, 'fontsize':10}

### Mean inclination plot

ax = ax1
ax.plot(incl_mean_logger, -depth_mean_logger, c=c_logger, lw=2, label=fname_logger, zorder=4)
ax.plot(incl0_mean[I0fit:], zz, c=c_drill2,  lw=2, ls='--', label=lbl_uncalibrated, zorder=5)    
ax.plot(incl_mean[I0fit:], zz, c=c_drill,  lw=2, label=lbl_calibrated, zorder=5)    
ax.set_xlim(inclims); 
ax.set_ylim([Z_MIN,0])
ax.set_ylabel('$z$ (m)'); ax.set_xlabel(r'$\theta$ (deg)')
ax.set_yticks(np.arange(Z_MIN,0+1,200))
ax.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
ax.grid(); ax.legend(**kwargs_legend); ax.set_title('Mean (bin $dz$ = %.0f)'%(dz))

### Raw inclination scatter plot

ax = ax2
ax.scatter(incl_raw_logger, -depth_raw_logger, marker='o', s=2**2, ec=c_logger, c='none', label=fname_logger)
ax.scatter(incl0_raw, -depth_drill,  marker='o', s=2**2, ec=c_drill2, c='none', label=lbl_uncalibrated)
ax.scatter(incl_raw,  -depth_drill,  marker='o', s=2**2, ec=c_drill, c='none', label=lbl_calibrated)
ax.set_xlim(inclims); ax.set_xlabel(r'$\theta$ (deg)')
plt.setp(ax.get_yticklabels(), visible=False)
ax.grid(); ax.legend(**kwargs_legend); ax.set_title('Raw from %s'%('SFUS' if METHOD_SFUS_QUAT else ('AHRS quaternion' if METHOD_AHRS_QUAT else 'AHRS DCM')))

if PLOT_AZIM:

    ### Mean azimuth plot

    ax = ax3
    ax.plot(azim_mean_logger, -depth_mean_logger, c=c_logger, lw=2, label=fname_logger, zorder=4)
    ax.plot(azim0_mean[I0fit:], zz, c=c_drill2,  lw=2, ls='--', label=lbl_uncalibrated, zorder=5)    
    ax.plot(azim_mean[I0fit:], zz, c=c_drill,  lw=2, label=lbl_calibrated, zorder=5)    
    #ax.set_xlim([0,360]); 
    ax1.set_ylim([Z_MIN,0])
    ax.set_ylabel('$z$ (m)'); ax.set_xlabel(r'$\phi$ (deg)')
    ax.set_yticks(np.arange(Z_MIN,0+1,200))
    ax.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
    ax.grid(); ax.legend(**kwargs_legend); ax.set_title('Mean (bin $dz$ = %.0f)'%(dz))

    ### Raw azimuth scatter plot

    ax = ax4
    ax.scatter(azim_raw_logger, -depth_raw_logger, marker='o', s=2**2, ec=c_logger, c='none', label=fname_logger)
    ax.scatter(azim0_raw,  -depth_drill,  marker='o', s=2**2, ec=c_drill2, c='none', label=lbl_uncalibrated)
    ax.scatter(azim_raw,  -depth_drill,  marker='o', s=2**2, ec=c_drill, c='none', label=lbl_calibrated)
    #ax.set_xlim(inclims); 
    ax.set_xlabel(r'$\phi$ (deg)')
    plt.setp(ax2.get_yticklabels(), visible=False)
    ax.grid(); ax.legend(**kwargs_legend)


### Save output

imgout = '%s/drill-orientation-%s.png'%(OUTPATH,date_time_str0)
print('*** Saving %s'%(imgout))
plt.savefig(imgout, dpi=300, bbox_inches='tight')

#-----------------------
# Save as CSV
#-----------------------

d = {
    'depth': zz, \
    'inclination': incl_mean[I0fit:], \
    'azimuth': azim_mean[I0fit:], \
}

df = pd.DataFrame(data=d)
fcsv = 'drill-logs-processed/drill-orientation-%s.csv'%(date_time_str0)
print('*** Saving %s'%(fcsv))
df.to_csv(fcsv, index=False)

