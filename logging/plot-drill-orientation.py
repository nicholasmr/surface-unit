#!/usr/bin/python
# N. Rathmann, 2018-2024

import numpy as np
import code # code.interact(local=locals())
import sys, os, time, csv, datetime, time, scipy
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation
import ahrs
from ahrs.filters import SAAM, FLAE, QUEST
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore', message='.*Gimbal', )

#-----------------------
# Options
#-----------------------

OUTPATH = 'drill-logs-processed'
LOGGERPATH = 'logger-data'

CORRECT_FRAME = 0

#-----------------------
# argv test
#-----------------------

if len(sys.argv) != 4: sys.exit('usage: %s /path/to/processed/csv HOUR_START HOUR_END '%(sys.argv[0]))
T_MIN, T_MAX = float(sys.argv[-2]), float(sys.argv[-1])
fdrill = str(sys.argv[1]) # drill log to plot
datetimestr = fdrill[-14:-4] # log file datetime string

#-----------------------
# AHRS setup
#-----------------------

AHRS_METHOD = 'SAAM' # preferred
#AHRS_METHOD = 'QUEST' 
#AHRS_METHOD = 'FLAE' 

# ... magnetic dip required by some estimators
egrip_N, egrip_E, egrip_height = 75.63248, -35.98911, 2.6
wmm = ahrs.utils.WMM(datetime.datetime.now(), latitude=egrip_N, longitude=egrip_E, height=egrip_height) 
mag_dip = wmm.I # Inclination angle (a.k.a. dip angle) -- https://ahrs.readthedocs.io/en/latest/wmm.html
mag_ref = np.array([wmm.X, wmm.Y, wmm.Z])
print('mag_ref = (%.1f, %.1f, %.1f) %.1f'%(mag_ref[0],mag_ref[1],mag_ref[2], np.linalg.norm(mag_ref)))

gravity = 9.0

if AHRS_METHOD == 'SAAM':
    AHRS_estimator = SAAM()
    mvmul = 1
    
elif AHRS_METHOD == 'FLAE':
    AHRS_estimator = FLAE(magnetic_dip=mag_dip)
    mvmul = 1e-6
    
#elif AHRS_METHOD == 'QUEST':
#    AHRS_estimator = QUEST(magnetic_dip=mag_dip, gravity=gravity, weights=np.array([1,1]))
#    mvmul = 1e-6
    
#-----------------------
# Binning method
#-----------------------

# Data bin size 
dz = 15 

# y axis (depth) limits
Z_MAX = 0 
Z_MIN = -3100

z_bin_full = np.arange(0, abs(Z_MIN)+dz, dz) # new z-axis
z_bin = z_bin_full[1:]
        
def binned(df, depth):
    groups = df.groupby(pd.cut(depth, z_bin_full))
    meanbins, varbins = groups.mean().to_numpy(), groups.var().to_numpy()
    return meanbins[:], varbins[:] 

#-----------------------
# Logger data
#-----------------------

### Load data

fields = ['azimuth', 'bottom_sensor', 'compass', 'depth', 'fluxgate_1_raw', 'fluxgate_2_raw', 'inclination', 'inclinometer_1_raw', 'inclinometer_2_raw', 'lower_diameter', \
          'lower_diameter_max_raw', 'lower_diameter_min_raw', 'pressure', 'pressure_raw', 'record_number', 'temperature_pressure_transducer', 'thermistor_high', 'thermistor_high_raw', \
          'upper_diameter', 'upper_diameter_max_raw', 'upper_diameter_min_raw', 'thermistor_low', 'thermistor_low_raw']
          
flogger = 'logger-2023-05-05-down.csv' # Logger data

fin = os.path.join(os.path.dirname(__file__), '%s/%s'%(LOGGERPATH,flogger))
df = pd.read_csv(fin, names=fields, header=1)

# Raw
incl_raw_logger  = df['inclination'].to_numpy()
azim_raw_logger  = df['azimuth'].to_numpy()
depth_raw_logger = df['depth'].to_numpy()

# Mean (binned)
depth_mean_logger, _ = binned(df['depth'],       df['depth']) 
incl_mean_logger, _  = binned(df['inclination'], df['depth']) 
azim_mean_logger, _  = binned(df['azimuth'],     df['depth']) 

### Fitting limits

# Fit range
z0 = 200  # ignore misfit with logger at depths shallower than this 
z1 = 2000 # ignore misfit with logger at depths deeper than this 

# ... in terms of depth axis index
I0fit = int(z0/dz)
#I1fit = int(z1/dz) 
I1fit = -1 # no lower bound

#-----------------------
# Drill data
#-----------------------

print('*** Loading drill log %s'%(fdrill))

fields = ['unixtime', 'hoursSince', 'depth', 'speed', 'load', 'hammer', 'motorRPM', 'motorCurrent', 'motorTemp', 'gearTemp', \
          'qx', 'qy', 'qz', 'qw', 'inclx', 'incly', 'magx', 'magy', 'magz', 'accx', 'accy', 'accz']

df = pd.read_csv(fdrill, names=fields, header=1)
df = df[df['hoursSince'].between(T_MIN, T_MAX)] # slice out requested temporal range (hours since midnight)

# Raw
z = -df['depth']
mx, my, mz = df['magx'].to_numpy(), df['magy'].to_numpy(), df['magz'].to_numpy()
ax, ay, az = df['accx'].to_numpy(), df['accy'].to_numpy(), df['accz'].to_numpy()

#-----------------------
# Determine orientation quaterion 
#-----------------------

N = len(mx) # number of log entries
quat = np.zeros((N,4))

def xyzw_to_wxyz(q): return np.roll(q,1)
def wxyz_to_xyzw(q): return np.roll(q,-1)

for ii in range(N):

    av = np.array([ax[ii], ay[ii], az[ii]])
    mv = np.array([mx[ii], my[ii], mz[ii]]) * mvmul
    q = AHRS_estimator.estimate(acc=av, mag=mv) 

    if np.size(q) != 4 or np.any(np.isnan(q)) or np.linalg.norm(q) < 0.99: 
        print('[!!] Bad entry at ii=%i'%(ii))
        quat[ii,:] = None 
    else:               
        quat[ii,:] = wxyz_to_xyzw(q)
    
   
#-----------------------
# BNO055 orientation calibration
#-----------------------

def get_incl(alpha, beta, gamma, incl_max=6.5):
    r = Rotation.from_euler('ZXZ', [alpha, beta, gamma], degrees=True)
    I = np.nonzero(~np.isnan(quat[:,0]))[0] # ignore badly normalized or missing data
    q0 = Rotation.from_quat(quat[I,:]) 
    q = r*q0 # apply calibration # rotated sensor plane 
    eulerangles = q.as_euler('ZXZ', degrees=True) # intrinsic rotations
    incl_raw = np.zeros(len(z))*np.nan
    if 1: incl_raw[I] = 180-eulerangles[:,1] # to inclination
    else: incl_raw[I] = eulerangles[:,1] # if QUEST
    if AHRS_METHOD == 'QUEST': incl_raw *= 0.5
    Irm = np.nonzero(incl_raw>incl_max)[0]
    incl_raw[Irm] = np.nan
    df = pd.DataFrame(zip(z, incl_raw), columns = ['depth','inclination'])
    incl_mean, _ = binned(df['inclination'], df['depth'])
    return incl_mean, incl_raw, z


# No calibration
incl0_mean, incl0_raw, _ = get_incl(0,0,0) 

if CORRECT_FRAME:
    print('*** Estimating sensor orientation from sensor data')

    def J(x):
        incl_mean, _, _ = get_incl(x[0],x[1],x[2])
        errsq = np.power(incl_mean - incl_mean_logger, 2)
        return np.nansum(errsq[I0fit:I1fit]) # = J
        
    paramvec = [0,0,0] # init guess
    res = minimize(J, paramvec, method='L-BFGS-B', tol=1e-3, options={'gtol': 1e-3, 'disp': True})
    euler_opt = res.x[:] # best fit
    alpha_opt, beta_opt, gamma_opt = euler_opt
    print('... done: (alpha_opt, beta_opt, gamma_opt) = (%f, %f, %f)'%(alpha_opt, beta_opt, gamma_opt))
    
else:
    euler_opt = (0, 0, 0) # Initial sensor orientation guess
#    euler_opt = (100, -1, 20) # Initial sensor orientation guess
    print('*** Using pre-defined sensor orientation: (alpha_opt, beta_opt, gamma_opt) = (%f, %f, %f)'%(euler_opt[0], euler_opt[1], euler_opt[2]))
    
# Best fit solution    
incl_mean, incl_raw, depth_drill = get_incl(*euler_opt)

#-----------------------
# Save as CSV
#-----------------------

print('*** Saving .csv')
I = np.logical_not(np.isnan(incl0_raw))
d = {'depth': -depth_drill[I], 'inclination': incl0_raw[I]}
df = pd.DataFrame(data=d)
fcsv = 'drill-logs-processed/drill-orientation-%s.csv'%(datetimestr)
print('*** Saving %s'%(fcsv))
df.to_csv(fcsv, index=False)

#-----------------------
# Plot
#-----------------------

print('*** Plotting')

fig = plt.figure(figsize=(7.8,8))

c_logger = 'k'
c_drill  = '#e31a1c'
c_drill2 = '#fb9a99'

ax1 = plt.subplot(1,2,1)
ax2 = plt.subplot(1,2,2, sharey=ax1)
xlims = [0,7]

lbl_uncalibrated = 'Drill %s (%s est.)'%(datetimestr, AHRS_METHOD)
if CORRECT_FRAME: lbl_calibrated = 'Calibrated (a,b,g)=(%.1f, %.1f, %.1f)'%(euler_opt[0], euler_opt[1], euler_opt[2])

kwargs_legend = {'fancybox':False, 'fontsize':10}

### Raw inclination scatter plot

ax = ax1
ax.scatter(incl_raw_logger, -depth_raw_logger, marker='o', s=2**2, ec=c_logger, c='none', label=flogger)
ax.scatter(incl0_raw, -depth_drill,  marker='o', s=2**2, ec=c_drill2, c='none', label=lbl_uncalibrated)
if CORRECT_FRAME: ax.scatter(incl_raw,  -depth_drill,  marker='o', s=2**2, ec=c_drill, c='none', label=lbl_calibrated)

ax.grid()
ax.legend(**kwargs_legend); ax.set_title('Scatter // %.1fh to %.1fh'%(T_MIN,T_MAX))
ax.set_xlim(xlims)
ax.set_xlabel(r'$\theta$ (deg)')
ax.set_ylim([Z_MIN,0])
ax.set_ylabel('$z$ (m)'); ax.set_xlabel(r'Inclination (deg)')
ax.set_yticks(np.arange(Z_MIN,0+1,200))
ax.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)

### Mean inclination plot

Z = -z_bin[I0fit:] # z axis of binned (mean) profiles

ax = ax2
ax.plot(incl_mean_logger, -depth_mean_logger, c=c_logger, lw=2, label=flogger, zorder=4)
ax.plot(incl0_mean[I0fit:], Z, c=c_drill2,  lw=2, ls='--', label=lbl_uncalibrated, zorder=5)    
if CORRECT_FRAME: ax.plot(incl_mean[I0fit:], zz, c=c_drill,  lw=2, label=lbl_calibrated, zorder=5)    

ax.grid()
ax.legend(**kwargs_legend); ax.set_title('Mean // bin=%.0fm'%(dz))
ax.set_xlim(xlims)
ax.set_xlabel(r'Inclination (deg)')
plt.setp(ax.get_yticklabels(), visible=False)

### Save output

imgout = '%s/drill-orientation-%s.png'%(OUTPATH,datetimestr)
print('*** Saving %s'%(imgout))
plt.savefig(imgout, dpi=300, bbox_inches='tight')

