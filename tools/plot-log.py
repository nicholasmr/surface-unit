#!/usr/bin/python
# N. Rathmann, 2017-2022

import numpy as np
import code # code.interact(local=locals())
import sys, os, time, csv, datetime, time, json, scipy
from scipy.stats import binned_statistic
import matplotlib.pyplot as plt

if len(sys.argv) < 2: sys.exit('usage: %s /mnt/logs/<LOGNAME> [HOUR_START] [HOUR_END]'%(sys.argv[0]))

"""
for i in {01..30}
do
   python3 plot-log.py drill.log.2019-06-$i
done
"""

#-----------------------
# INIT
#-----------------------

Z_MAX = -150
Z_MIN = -2700
BIN_PER_METER = 5

LOGFILE = str(sys.argv[1])
date_time_str0 = LOGFILE[-10:]

if len(sys.argv) == 4: xlims=[float(sys.argv[2]),float(sys.argv[3])];
else:                  xlims=[8,24];

# INIT structures

def initArr(len):
    arr    = np.empty((len), dtype=float)
    arr[:] = np.nan
    return arr;

flen = sum(1 for l in open(LOGFILE, "r"))
t  = initArr(flen) # time in seconds
th = initArr(flen) # time in hours
thoff = initArr(flen) # time in hours, but nan'ed when drill is powered off

z  = initArr(flen) # depth
v  = initArr(flen) # cable speed
w  = initArr(flen) # tower weight
H  = initArr(flen) # hammer pct.

I  = initArr(flen) # motor I
U  = initArr(flen) # motor U
f  = initArr(flen) # motor rpm

Tg = initArr(flen) # temperature gear 1
Tmc = initArr(flen) # temperature motor controller
Tm = initArr(flen) # temperature motor 

Sg = initArr(flen) # integrated drill rotations: gyro
Si = initArr(flen) # integrated drill rotations: incl

totalChange = 0;
lastAzimuth = -1000;

#-----------------------
# Load log file
#-----------------------

fh  = open(LOGFILE, "r")
for li, l in enumerate(fh):

    if "depth_encoder" not in l: continue # not uphole message

    date_time_obj0 = datetime.datetime.strptime(date_time_str0, '%Y-%m-%d')    

    date_time_str1 = l[:23]
    date_time_obj1 = datetime.datetime.strptime(date_time_str1, '%Y-%m-%d %H:%M:%S,%f')
    t[li]  = (date_time_obj1-date_time_obj0).total_seconds()
    th[li] = t[li]/(60**2)

    ii = l.find('{')
    l = l[ii:]

    z[li]  = json.loads(l)['depth_encoder']['depth']
    w[li]  = json.loads(l)['load_cell']
    #v[li] is done post loop once depth and times are collected
    H[li]  = 100 * (float(json.loads(l)['hammer']) / 255.0)

    I[li]  = json.loads(l)['motor_current']
    U[li]  = json.loads(l)['motor_voltage']
    f[li]  = float(json.loads(l)['motor_rpm'])
    
    Tg[li]  = json.loads(l)['aux_temperature_gear1']
    Tmc[li] = json.loads(l)['motor_controller_temp']
    Tm[li]  = json.loads(l)['temperature_motor']
        
    Sg[li] = 0.15 * float(json.loads(l)['gyroscope_z'])
    
    #-----------------------
    pitch = np.deg2rad(json.loads(l)['inclination_x']);  # pitch
    roll = np.deg2rad(json.loads(l)['inclination_y']);  # roll  
    nx =  np.cos(pitch)*np.sin(roll);
    ny = -np.sin(pitch);
    azrad = np.mod(np.arctan2(ny,nx), 2*np.pi)
    az = np.rad2deg(azrad)

    if az > 180: az -= 360; #   // do this if your azimuth is always positive i.e. 0-360.
    if lastAzimuth == -1000: lastAzimuth = az;

    diff = az - lastAzimuth;
    if diff > 180:  diff -= 360;
    if diff < -180: diff += 360;

    lastAzimuth = az;
    totalChange += diff;
    Si[li] = totalChange / 360;
    #-----------------------
#    if ~np.isnan(Si[li]): thoff[li] = th[li]

fh.close()

#-----------------------
# Plot
#-----------------------

scale = 0.7
ylen = 14
xtick = 1
fig = plt.figure(figsize=(scale*ylen*1.414*1.2, scale*ylen))

N = 4;
lw = 1.4
lwtwin = lw*0.8
fw = 'normal'
fs = 11

### Subplots

axz = plt.subplot(N,1,4)

plt.plot(th, Tg, color='k', lw=lw)
axz.set_xticks(np.arange(-5,30,xtick))
axz.set_xticks(np.arange(-5,30,xtick/4.), minor=True)
plt.xlim(xlims); 
plt.xlabel('Hours since %s'%(date_time_str0), fontweight=fw, fontsize=fs);
ylims_temp = [-40,80]
axz.set_yticks(np.arange(ylims_temp[0],ylims_temp[1]+1,20))
plt.ylim(ylims_temp); axz.grid()
plt.ylabel('Gear temp. (C)', fontweight=fw, fontsize=fs);

ax2 = axz.twinx()  # instantiate a second axes that shares the same x-axis
color = 'tab:purple'
ax2.plot(th, Tmc, color=color, lw=lwtwin)
ax2.set_xticks(np.arange(-5,30,xtick))
ax2.set_xticks(np.arange(-5,30,xtick/4.), minor=True)
ax2.set_ylabel('Motor ctrl. temp. (C)', color=color, fontweight=fw, fontsize=fs);
ax2.set_yticks(np.arange(ylims_temp[0],ylims_temp[1]+1,20))
ax2.set_ylim(ylims_temp)

#-------------------------

ax = plt.subplot(N,1,1, sharex=axz)
plt.plot(th, z, 'k', lw=lw)
#plt.setp(axz.get_xticklabels())
plt.setp(ax.get_xticklabels(), visible=False)
plt.xlim(xlims); plt.ylim([-2700,0]); ax.grid()
plt.ylabel('Depth (m)', fontweight=fw, fontsize=fs);

ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis
color = 'tab:green'
ax2.plot(th, Si, color=color, lw=lwtwin)
ax2.set_xticks(np.arange(-5,30,xtick))
ax2.set_xticks(np.arange(-5,30,xtick/4.), minor=True)
ax2.set_ylabel('Drill rotations (rev)', color=color, fontweight=fw, fontsize=fs);

#-------------------------

ax = plt.subplot(N,1,2, sharex=axz)
plt.plot(th, w, 'k', lw=lw*1.2)
plt.setp(ax.get_xticklabels(), visible=False)
plt.xlim(xlims); plt.ylim([0,2500]); ax.grid()
plt.ylabel('Tower load (kg)', fontweight=fw, fontsize=fs);

ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis
color = 'tab:blue'
ax2.plot(th, H, color=color, lw=lwtwin)
ax2.set_ylabel('Hammer position (%)',color=color, fontweight=fw, fontsize=fs)  # we already handled the x-label with ax1
ax2.set_ylim([0, 100])

#-------------------------

ax = plt.subplot(N,1,3, sharex=axz)
color = 'k'
plt.plot(th, f, color=color, lw=lw)
plt.setp(ax.get_xticklabels(), visible=False)
plt.xlim(xlims); plt.ylim([0, 80]); ax.grid()
ax.set_ylabel('Motor speed (RPM)', color=color, fontweight=fw, fontsize=fs)

ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis
color = 'tab:red'
ax2.plot(th, I, color=color, lw=lwtwin)
ax2.set_ylabel('Motor current (A)',color=color, fontweight=fw, fontsize=fs)  # we already handled the x-label with ax1
ax2.set_yticks(np.arange(0,15+1,2))
ax2.set_ylim([0, 15])

#-------------------------

imgout = '%s.png'%(date_time_str0)
print('Saving image to %s'%(imgout))
plt.savefig(imgout, dpi=300, bbox_inches='tight')

