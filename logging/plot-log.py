#!/usr/bin/python
# N. Rathmann, 2017-2022

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

if len(sys.argv) !=6: sys.exit('usage: %s /mnt/logs/<LOGNAME> HOUR_START HOUR_END PLOT_ORIENTATION /output/path '%(sys.argv[0]))

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
# Flags
#-----------------------

PLOT_TIMESERIES  = 1
PLOT_ORIENTATION = int(sys.argv[4])
RUN_SENSOR_ORIENTATION_CALIBRATION = PLOT_ORIENTATION

#-----------------------
# Files
#-----------------------

OUTPATH = str(sys.argv[-1]) # where to save images
DRILLLOG = str(sys.argv[1]) # drill log to plot
date_time_str0 = DRILLLOG[-10:] # log file date string

### Logger data
fname_logger    = 'logger-2019.dat'
fname_loggernew = 'logger-2022-07-09.dat'
LOGGERDATA    = os.path.join(os.path.dirname(__file__), "logger-data/%s"%(fname_logger))
LOGGERDATANEW = os.path.join(os.path.dirname(__file__), "logger-data/%s"%(fname_loggernew))

#-----------------------
# Initialize
#-----------------------

### Plot limits
Z_MAX, Z_MIN = 0, -2800 # y axis
xlims=[int(sys.argv[2]),int(sys.argv[3])]; # x axis

def empty_array(len):
    arr    = np.empty((len), dtype=float)
    arr[:] = np.nan
    return arr;

flen = sum(1 for l in open(DRILLLOG, "r"))

### Time
t  = empty_array(flen) # time in seconds
th = empty_array(flen) # time in hours
thoff = empty_array(flen) # time in hours, but nan'ed when drill is powered off

### Depth, speed, etc.
z  = empty_array(flen) # depth
w  = empty_array(flen) # tower weight
H  = empty_array(flen) # hammer pct.

### Motor
I, U, f  = empty_array(flen),empty_array(flen),empty_array(flen) # motor I, U, RPM

### Temperature
Tg, Tmc, Tm = empty_array(flen), empty_array(flen), empty_array(flen) # temperature gear 1, motor controller, motor

### Orientation
quat = np.zeros((flen,4))
DCM = np.zeros((flen,3,3)) # rotation matrix
inc, azi = empty_array(flen), empty_array(flen)

### Alarms
gyroalarm = np.zeros((flen))

#-----------------------
# Load log file
#-----------------------

if 1:

    print('*** Loading log file %s'%(DRILLLOG))

    fh  = open(DRILLLOG, "r")
    jj = 0
    for ii, l in enumerate(fh):

        date_time_obj0 = datetime.datetime.strptime(date_time_str0, '%Y-%m-%d')    

        date_time_str1 = l[:23]
        date_time_obj1 = datetime.datetime.strptime(date_time_str1, '%Y-%m-%d %H:%M:%S,%f')
        t[ii]  = (date_time_obj1-date_time_obj0).total_seconds()
        th[ii] = t[ii]/(60**2)

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
        
        avec = np.array([json.loads(l)['accelerometer_x'], json.loads(l)['accelerometer_y'], json.loads(l)['accelerometer_z']])
        mvec = np.array([json.loads(l)['magnetometer_x'], json.loads(l)['magnetometer_y'], json.loads(l)['magnetometer_z']]) 
        quat[jj,:] = saam.estimate(acc=avec, mag=mvec) # quaternion
        DCM[jj,:,:] = Quaternion(quat[jj,:]).to_DCM()

        ### Make ready for next loop        
        jj +=1

    fh.close()
    print('... done')
            
    ### Velocity
    vel = 100 * abs(np.nan_to_num( np.divide(np.diff(z),np.diff(t))) )
    vel = savgol_filter(vel, 101, 2) # smoothing

    ### Remove empty parts of arrays for incl and azi plots.
    jjmax = jj-1
    DCM = DCM[0:(jjmax+1), :,:]
    Z = z[0:(jjmax+1)]


#-----------------------
# Dump z(t) for Aslak's codex560 calibration
#-----------------------

#df = pd.DataFrame(zip(t,z), columns = ['t','z'])
#df.to_csv('%s_zt.csv'%DRILLLOG, index=False)
#sys.exit(0)

#-----------------------
# BNO055 orientation calibration
#-----------------------

x_opt, y_opt = -0.01, 0.03 # initial sensor orientation guess

dz = 15 # dz is data bin size 
Z0fit = 75 # ignore misfit with logger at depths shallower than this number
Z1fit = 1200 # ignore misfit with logger at depths deepter than this number
I0fit = int(Z0fit/dz)
I1fit = -1 # no lower bound
#I1fit = int(Z1fit/dz) 
z_bin_full = np.arange(0, abs(Z_MIN)+dz, dz) # new z-axis
z_bin = z_bin_full[1:]
        
def binned_stats(df):
    groups = df.groupby(pd.cut(df.z, z_bin_full))
    meanbins, varbins = groups.mean().to_numpy(), groups.var().to_numpy()
    return meanbins[:,1], varbins[:,1] # binned: [ mean(inc), var(inc) ]
    
def inc_given_sensor_xyplane(x,y):
        sensordir = -np.array([x,y,np.sqrt(1-x**2-y**2)]) # presumed BNO055 sensor orientation
        drilldir = np.array([np.matmul(DCM[ii,:,:], sensordir) for ii in np.arange(jjmax+1)]) 
        incr = np.rad2deg(np.arccos(drilldir[:,2])) # raw inclination data
        df = pd.DataFrame(zip(Z,incr), columns = ['z','inc'])
        incm, _ = binned_stats(df)
        return incm, incr

### Load logger data

df_loggernew = pd.read_csv(LOGGERDATANEW, names=['z','inc'], delim_whitespace=True)
df_logger    = pd.read_csv(LOGGERDATA,    names=['z','inc'])
incm_logger, _ = binned_stats(df_logger) # this is what is used to calibration against ("true" inc/azi)

### Run sensor calibration?

if RUN_SENSOR_ORIENTATION_CALIBRATION:

    print('*** Estimating BNO055 sensor orientation')

    # Misfit measure
    def J(xy):
        incm, _ = inc_given_sensor_xyplane(xy[0], xy[1])
        errsq = np.power(incm - incm_logger, 2)
        J = np.nansum(errsq[I0fit:I1fit])
        return J
        
    paramvec = [x_opt, y_opt] # init guess
    res = minimize(J, paramvec, method='L-BFGS-B', bounds=[(-0.1,0.1),(-0.1,0.1)], tol=1e-4, options={'gtol': 1e-4, 'disp': True})
    x_opt, y_opt = res.x[0], res.x[1] # best fit
    print('... done: (x_opt, y_opt) = (%f,%f)'%(x_opt,y_opt))
    
else:
    print('*** Using pre-defined BNO055 sensor orientation: (x_opt, y_opt) = (%f,%f)'%(x_opt,y_opt))
    
### Best fit solution    
incm_drill, incr_drill = inc_given_sensor_xyplane(x_opt, y_opt)

# No calibration solution
incm_drill_nocal, _ = inc_given_sensor_xyplane(0, 0) 

#-----------------------
# Plot timer series
#-----------------------

if PLOT_TIMESERIES:

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
    ax2.plot(th[:-1], vel, color=color, lw=lwtwin)
    ax2.set_ylabel('|Speed| (cm/s)', color=color, fontweight=fw, fontsize=fs);
    plt.ylim([0,110]);

    #-----

    ax = plt.subplot(N,1,2, sharex=axz)
    plt.plot(th, w, 'k', lw=lw*1.2)
    plt.setp(ax.get_xticklabels(), visible=False)
    ax.set_yticks(np.arange(0,3000+1,500))
    plt.xlim(xlims); plt.ylim([0,3000]); ax.grid()
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

    imgout = '%s/%s--%i-%i.png'%(OUTPATH,date_time_str0,xlims[0],xlims[1])
    print('Saving %s'%(imgout))
    plt.savefig(imgout, dpi=300, bbox_inches='tight')

#-----------------------
# Orientation
#-----------------------

if PLOT_ORIENTATION:

    scale = 0.7
    fig = plt.figure(figsize=(7,8))
    c_drill, c_drill2, c_logger, c_loggernew = '#1f78b4', '#9ecae1', '0.6', 'k'
    inclims = [0,7]

    ax1 = plt.subplot(1,2,1)
    ax2 = plt.subplot(1,2,2, sharey=ax1)

    loggerraw = df_logger.to_numpy()
    loggerrawnew = df_loggernew.to_numpy()
    z_ = -z_bin[I0fit:]

    ax1.plot(incm_drill_nocal[I0fit:],  z_, c=c_drill2,  lw=2, ls='--', label='Drill (x,y=0,0)', zorder=5)    
    ax1.plot(incm_drill[I0fit:],  z_, c=c_drill,  lw=2, label='Drill (x,y=%.2f,%.2f)'%(x_opt,y_opt), zorder=5)    
    ax1.plot(incm_logger[I0fit:], z_, c=c_logger, lw=2, label='%s'%fname_logger, zorder=4)
    ax1.plot(loggerrawnew[:,1], -loggerrawnew[:,0], c=c_loggernew, lw=2, label='%s'%fname_loggernew, zorder=3)
    ax1.set_xlim(inclims); ax1.set_ylim([Z_MIN,0])
    ax1.set_ylabel('z (m)'); ax1.set_xlabel('Mean inclination (deg)')
    ax1.set_yticks(np.arange(Z_MIN,0+1,200))
    ax1.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
    ax1.grid()
    ax1.legend()

    ax2.scatter(loggerraw[:,1], -loggerraw[:,0], marker='.', s=1, c=c_logger, label='%s'%(fname_logger))
    ax2.scatter(incr_drill, -Z, marker='.', s=1, c=c_drill, label='Drill')
    ax2.set_xlim(inclims); ax2.set_xlabel('Inclination (deg)')
    plt.setp(ax2.get_yticklabels(), visible=False)
    ax2.grid()
    ax2.legend()

    imgout = '%s/%s-orientation.png'%(OUTPATH,date_time_str0)
    print('Saving %s'%(imgout))
    plt.savefig(imgout, dpi=300, bbox_inches='tight')

