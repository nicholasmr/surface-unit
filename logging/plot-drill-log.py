#!/usr/bin/python
# N. Rathmann, 2017-2023

import numpy as np
import code # code.interact(local=locals())
import sys, os, time, csv, datetime, time, json, scipy
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import savgol_filter

if len(sys.argv) != 5: sys.exit('usage: %s /mnt/logs/<LOGNAME> HOUR_START HOUR_END /output/path '%(sys.argv[0]))

#-----------------------
# Notes
#-----------------------

### BASH script for plotting multiple days
"""
for i in {01..30}
do
   python3 plot-log.py drill.log.2019-06-$i 8 24 ./
done
"""

### For drilllogplotter cronjob on bob:
"""
IP: 10.2.3.18
usr: drill, psw: same as drill computer
"""

#-----------------------
# Options
#-----------------------

Z_MAX, Z_MIN = 0, -2800 # y axis

xlims=[int(sys.argv[2]),int(sys.argv[3])]; # x axis

#-----------------------
# Files
#-----------------------

OUTPATH = str(sys.argv[-1]) # where to save images
DRILLLOG = str(sys.argv[1]) # drill log to plot
date_time_str0 = DRILLLOG[-10:] # log file date string

#-----------------------
# Initialize
#-----------------------

def empty_array(len):
    arr    = np.empty((len), dtype=float)
    arr[:] = np.nan
    return arr;

flen = sum(1 for l in open(DRILLLOG, "r"))

### Time
t  = empty_array(flen) # time in seconds
th = empty_array(flen) # time in hours
thoff = empty_array(flen) # time in hours, but nan'ed when drill is powered off
tabs = empty_array(flen) # unix time stamp

### Depth, speed, etc.
z  = empty_array(flen) # depth
w  = empty_array(flen) # tower weight
H  = empty_array(flen) # hammer pct.

### Motor
I, U, f  = empty_array(flen),empty_array(flen),empty_array(flen) # motor I, U, RPM

### Temperature
Tg, Tmc, Tm = empty_array(flen), empty_array(flen), empty_array(flen) # temperature gear 1, motor controller, motor

### Accelerometer
accx, accy, accz = empty_array(flen), empty_array(flen), empty_array(flen) 

### Magnetometer
magx, magy, magz = empty_array(flen), empty_array(flen), empty_array(flen) 

### Alarms
gyroalarm = np.zeros((flen))

#-----------------------
# Load log file
#-----------------------

print('*** Loading log %s'%(DRILLLOG))

fh  = open(DRILLLOG, "r")
jj = 0

Icsv = []

for ii, l in enumerate(fh):

    date_time_obj0 = datetime.datetime.strptime(date_time_str0, '%Y-%m-%d')    

    date_time_str1 = l[:23]
    date_time_obj1 = datetime.datetime.strptime(date_time_str1, '%Y-%m-%d %H:%M:%S,%f')
    t[ii]  = (date_time_obj1-date_time_obj0).total_seconds()
    th[ii] = t[ii]/(60**2)
    tabs[ii] = time.mktime(date_time_obj1.timetuple())

    if "GyroSlipAlarm" in l:
        gyroalarm[ii] = 1
        continue

    if "depth_encoder" not in l: 
        continue # not uphole message

    kk = l.find('{')
    l = l[kk:]

    try:    z[ii] = - json.loads(l)['depth_encoder']['depth']
    except: z[ii] = np.nan
    try:    w[ii] = json.loads(l)['load_cell']
    except: w[ii] = np.nan

    #v[ii] is done post loop once depth and times are collected
    H[ii]  = 100 * (float(json.loads(l)['hammer']) / 255.0)

    I[ii]  = json.loads(l)['motor_current']
    U[ii]  = json.loads(l)['motor_voltage']
    f[ii]  = float(json.loads(l)['motor_rpm'])
    
    Tg[ii]  = json.loads(l)['aux_temperature_gear1']
    Tmc[ii] = json.loads(l)['motor_controller_temp']
    Tm[ii]  = json.loads(l)['temperature_motor']

    ### Inclination and azimuth
    
    accx[ii],accy[ii],accz[ii] = json.loads(l)['accelerometer_x'], json.loads(l)['accelerometer_y'], json.loads(l)['accelerometer_z']
    magx[ii],magy[ii],magz[ii] = json.loads(l)['magnetometer_x'], json.loads(l)['magnetometer_y'], json.loads(l)['magnetometer_z']

    ### Make ready for next loop        
    jj +=1
    
    if not np.isnan(z[ii]) and not np.isnan(w[ii]) and not np.isnan(f[ii]): 
        Icsv.append(ii) # save only rows to .csv when no data is missing

fh.close()
print('... done')
        
### Velocity
vel = 100 * abs(np.nan_to_num( np.divide(np.diff(z),np.diff(t))) )
vel = savgol_filter(vel, 101, 2) # smoothing
vel = np.concatenate((vel,[vel[-1],]))

#-----------------------
# Plot timer series
#-----------------------

scale, ylen = 0.7, 14
fig = plt.figure(figsize=(scale*ylen*1.414*1.2, scale*ylen))

xtick = 1 # hour ticks

N = 4;
lw = 1.4
lwtwin = lw*0.8
fs, fw = 11, 'normal'

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
color = 'tab:orange'
ax2.plot(th, Tmc, color=color, lw=lwtwin)
ax2.set_xticks(np.arange(-5,30,xtick))
ax2.set_xticks(np.arange(-5,30,xtick/4.), minor=True)
ax2.set_ylabel('Motor ctrl. temp. (C)', color=color, fontweight=fw, fontsize=fs);
ax2.set_yticks(np.arange(ylims_temp[0],ylims_temp[1]+1,20))
ax2.set_ylim(ylims_temp)

#-----

ax = plt.subplot(N,1,1, sharex=axz)
plt.plot(th, -z, 'k', lw=lw)
#plt.setp(axz.get_xticklabels())
plt.setp(ax.get_xticklabels(), visible=False)
ax.set_yticks(np.arange(Z_MAX-20,Z_MIN+1,-500))
ax.set_yticks(np.arange(Z_MAX-20,Z_MIN+1,-100),minor=True)
plt.xlim(xlims); plt.ylim([Z_MIN,0]); ax.grid()
plt.ylabel('Depth (m)', fontweight=fw, fontsize=fs);

ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis
color = 'tab:green'
ax2.plot(th, vel, color=color, lw=lwtwin)
ax2.set_ylabel('|Speed| (cm/s)', color=color, fontweight=fw, fontsize=fs);
plt.ylim([0,110]);

#-----

ax = plt.subplot(N,1,2, sharex=axz)
plt.plot(th, w, 'k', lw=lw*1.2)
plt.setp(ax.get_xticklabels(), visible=False)
ax.set_yticks(np.arange(0,3000+1,500))
plt.xlim(xlims); plt.ylim([0,3000]); ax.grid()
#    ax.set_yticks(np.arange(500,600+1,100))
#    plt.xlim(xlims); plt.ylim([500,600]); ax.grid()
plt.ylabel('Tower load (kg)', fontweight=fw, fontsize=fs);

ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis
color = 'tab:blue'
ax2.plot(th, H, color=color, lw=lwtwin)
ax2.set_ylabel('Hammer position (%)',color=color, fontweight=fw, fontsize=fs)  # we already handled the x-label with ax1
ax2.set_ylim([0, 100])

#-----

ax = plt.subplot(N,1,3, sharex=axz)
color = 'k'
plt.plot(th, f, color=color, lw=lw)
plt.setp(ax.get_xticklabels(), visible=False)
ax.set_yticks(np.arange(0,80+1,10))
#ax.set_yticks(np.arange(0,80+1,10),minor=True)
plt.xlim(xlims); plt.ylim([0, 80]); ax.grid()
ax.set_ylabel('Motor speed (RPM)', color=color, fontweight=fw, fontsize=fs)

ax2 = ax.twinx()  # instantiate a second axes that shares the same x-axis
color = 'tab:red'
ax2.plot(th, I, color=color, lw=lwtwin)
ax2.set_ylabel('Motor current (A)',color=color, fontweight=fw, fontsize=fs)  # we already handled the x-label with ax1
ax2.plot(th, gyroalarm*20, color='tab:purple', lw=lwtwin, label='Gyro slip alarm')
ax2.set_yticks(np.arange(0,15+1,2))
ax2.set_ylim([0, 15])
ax2.legend(loc=2)

#-----

imgout = '%s/drill-log-%s--%i-%i.png'%(OUTPATH,date_time_str0,xlims[0],xlims[1])
print('*** Saving %s'%(imgout))
plt.savefig(imgout, dpi=260, bbox_inches='tight')

### Save time series for easier third-party use

fcsv = 'drill-logs-processed/drill.log.processed.%s.csv'%(date_time_str0)
print('*** Saving %s'%(fcsv))
d = {'unixtime':     [int(x)      for x in tabs[Icsv]], \
     'hoursSince':   [round(float(x), 4) for x in th[Icsv]],  \
     'depth':        [round(float(x), 2) for x in z[Icsv]],  \
     'speed':        [round(float(x), 4) for x in vel[Icsv]], \
     'load':         [round(float(x), 2) for x in w[Icsv]], \
     'hammer':       [round(x, 2) for x in H[Icsv]], \
     'motorRPM':     [round(x, 2) for x in f[Icsv]], \
     'motorCurrent': [round(x, 2) for x in I[Icsv]], \
     'motorTemp':    [round(x, 2) for x in Tmc[Icsv]], \
     'gearTemp':     [round(x, 2) for x in Tg[Icsv]], \
     'magx':         [round(x, 3) for x in magx[Icsv]], \
     'magy':         [round(x, 3) for x in magy[Icsv]], \
     'magz':         [round(x, 3) for x in magz[Icsv]], \
     'accx':         [round(x, 3) for x in accx[Icsv]], \
     'accy':         [round(x, 3) for x in accy[Icsv]], \
     'accz':         [round(x, 3) for x in accz[Icsv]], \
 } 
df = pd.DataFrame(data=d)
#    code.interact(local=locals())
os.system('mkdir -p drill-logs-processed')
df.to_csv(fcsv, index=False)

