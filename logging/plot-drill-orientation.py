#!/usr/bin/python
# N. Rathmann, 2018-2024

import numpy as np
import code # code.interact(local=locals())
import sys, os, time, csv, datetime, time, scipy
import pandas as pd
from scipy.optimize import minimize
from scipy.spatial.transform import Rotation
import ahrs
from ahrs.filters import SAAM, Tilt, FLAE, QUEST
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore', message='.*Gimbal', )

#-----------------------
# Options
#-----------------------

OUTPATH = 'drill-logs-processed'

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
#AHRS_METHOD = 'Tilt' # gives approx same as SAAM
#AHRS_METHOD = 'FLAE' 
#AHRS_METHOD = 'QUEST' 

# ... magnetic dip required by some estimators
egrip_N, egrip_E, egrip_height = 75.63248, -35.98911, 2.6
wmm = ahrs.utils.WMM(datetime.datetime.now(), latitude=egrip_N, longitude=egrip_E, height=egrip_height) 
mag_dip = wmm.I # Inclination angle (a.k.a. dip angle) -- https://ahrs.readthedocs.io/en/latest/wmm.html
mag_ref = np.array([wmm.X, wmm.Y, wmm.Z])
print('mag_ref = (%.1f, %.1f, %.1f) %.1f'%(mag_ref[0],mag_ref[1],mag_ref[2], np.linalg.norm(mag_ref)))

if AHRS_METHOD == 'SAAM':
    AHRS_estimator = SAAM()
    mvmul = 1
    
if AHRS_METHOD == 'Tilt':
    AHRS_estimator = Tilt()
    mvmul = 1
    
elif AHRS_METHOD == 'FLAE':
    AHRS_estimator = FLAE(magnetic_dip=mag_dip)
    mvmul = 1e-6
    
elif AHRS_METHOD == 'QUEST':
    AHRS_estimator = QUEST(magnetic_dip=mag_dip, gravity=9.8, weights=np.array([1,1]))
    mvmul = 1e-6
    
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
    if AHRS_METHOD == 'Tilt': mv = None
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
    azim_raw = np.zeros(len(z))*np.nan
    incl_raw[I] = 180-eulerangles[:,1] # to inclination
    azim_raw[I] = eulerangles[:,2]
    Irm = np.nonzero(incl_raw>incl_max)[0]
    incl_raw[Irm] = np.nan
    azim_raw[Irm] = np.nan
    return incl_raw, azim_raw, z

incl0_raw, azim0_raw, depth_drill = get_incl(0,0,0) # No calibration

#-----------------------
# Save as CSV
#-----------------------

print('*** Saving .csv')
I = np.logical_not(np.isnan(incl0_raw))
d = {'depth': -depth_drill[I], 'inclination': incl0_raw[I], 'azimuth': azim0_raw[I]}
df = pd.DataFrame(data=d)
fcsv = 'drill-logs-processed/drill-orientation-%s.csv'%(datetimestr)
print('*** Saving %s'%(fcsv))
df.to_csv(fcsv, index=False)

#-----------------------
# Plot
#-----------------------

print('*** Plotting')

fig = plt.figure(figsize=(7.8,7))

c_logger = 'k'
c_drill  = 'tab:red'

ax1 = plt.subplot(1,2,1)
ax2 = plt.subplot(1,2,2, sharey=ax1)
xlims = [0,7]
Z_MIN = -np.amax(np.abs(depth_drill[I]))*1.08

lbl_uncalibrated = 'Drill %s (%s)'%(datetimestr, AHRS_METHOD)
kwargs_legend = {'fancybox':False, 'fontsize':10, 'loc':4}

### Raw inclination scatter plot

ax = ax1
ax.scatter(incl0_raw, -depth_drill,  marker='o', s=2**2, ec=c_drill, c='none', label=lbl_uncalibrated)

ax.grid()
ax.legend(**kwargs_legend); ax.set_title('Scatter // %.1fh to %.1fh'%(T_MIN,T_MAX))
ax.set_xticks(np.arange(0,10,1))
ax.set_xlim(xlims)
ax.set_xlabel(r'Inclination (deg)')
ax.set_ylabel('$z$ (m)'); 
ax.set_xlabel(r'Inclination (deg)')
ax.set_yticks(np.arange(-5000,0+1,200))
ax.set_yticks(np.arange(-5000,0+1,100),minor=True)
ax.set_ylim([Z_MIN,0])

### Raw azimuth scatter plot

ax = ax2
ax.scatter(azim0_raw, -depth_drill,  marker='o', s=2**2, ec=c_drill, c='none', label=lbl_uncalibrated)

ax.grid()
ax.legend(**kwargs_legend); 
ax.set_xticks(np.arange(-180,180+1,60))
ax.set_xlim([-180,180])
ax.set_xlabel(r'Azimuth (deg)')
plt.setp(ax.get_yticklabels(), visible=False)

### Save output

imgout = '%s/drill-orientation-%s.png'%(OUTPATH,datetimestr)
print('*** Saving %s'%(imgout))
plt.savefig(imgout, dpi=300, bbox_inches='tight')

