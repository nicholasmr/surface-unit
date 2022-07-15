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
# INIT
#-----------------------

PLOT_TIMESERIES  = 1

PLOT_ORIENTATION = int(sys.argv[4])
RUN_SENSOR_ORIENTATION_CALIBRATION = PLOT_ORIENTATION

Z_MAX = 0
Z_MIN = -2800

LOGFILE = str(sys.argv[1])
date_time_str0 = LOGFILE[-10:]

flog = "logger-2019.dat"
script_dir = os.path.dirname(__file__)
rel_path = "logger-data/%s"%(flog)
LOGGERDATA = os.path.join(script_dir, rel_path)

xlims=[int(sys.argv[2]),int(sys.argv[3])];
OUTPATH = str(sys.argv[-1])

### Data structures

def empty_array(len):
    arr    = np.empty((len), dtype=float)
    arr[:] = np.nan
    return arr;

flen = sum(1 for l in open(LOGFILE, "r"))

### Time
t  = empty_array(flen) # time in seconds
th = empty_array(flen) # time in hours
thoff = empty_array(flen) # time in hours, but nan'ed when drill is powered off

### Depth, speed, etc.
z  = empty_array(flen) # depth
v  = empty_array(flen) # winch speed
w  = empty_array(flen) # tower weight
H  = empty_array(flen) # hammer pct.

### Motor
I, U, f  = empty_array(flen),empty_array(flen),empty_array(flen) # motor I, U, RPM

### Temperature
Tg, Tmc, Tm = empty_array(flen), empty_array(flen), empty_array(flen) # temperature gear 1, motor controller, motor

### Orientation
quat = np.zeros((flen,4))
DCM = np.zeros((flen,3,3))
incl, azi = empty_array(flen), empty_array(flen)

#ax,ay,az = empty_array(flen),empty_array(flen),empty_array(flen)
#mx,my,mz = empty_array(flen),empty_array(flen),empty_array(flen)

#Sg = initArr(flen) # integrated drill rotations: gyro
#Si = initArr(flen) # integrated drill rotations: incl
#totalChange = 0;
#lastAzimuth = -1000;

#-----------------------
# Load log file
#-----------------------

if 1:

    print('*** Loading log file %s'%(LOGFILE))

    fh  = open(LOGFILE, "r")
    jj = 0
    for ii, l in enumerate(fh):

        if "depth_encoder" not in l: continue # not uphole message

        date_time_obj0 = datetime.datetime.strptime(date_time_str0, '%Y-%m-%d')    

        date_time_str1 = l[:23]
        date_time_obj1 = datetime.datetime.strptime(date_time_str1, '%Y-%m-%d %H:%M:%S,%f')
        t[ii]  = (date_time_obj1-date_time_obj0).total_seconds()
        th[ii] = t[ii]/(60**2)

        kk = l.find('{')
        l = l[kk:]

        z[ii]  = - json.loads(l)['depth_encoder']['depth']
        w[ii]  = json.loads(l)['load_cell']
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
        
        jj +=1
        
    #    quat = famc.estimate(acc=avec, mag=mvec) # quaternion
#        drilldir = np.matmul(Quaternion(quat).to_DCM(), sensordir) # drill orientation vector: matrix--vector product between rotation matrix (derived from quaternion) and vertical (plumb) direction
#        incl[ii] = np.rad2deg(np.arccos(drilldir[2]))
#        azi[ii]  = np.rad2deg(np.arctan2(drilldir[1],drilldir[0]))
    #       if azi[ii] < 0: azi[ii] = 360-azi[ii]

#        ### drill rotations
#            
#        Sg[ii] = 0.15 * float(json.loads(l)['gyroscope_z'])
#        
#        pitch = np.deg2rad(json.loads(l)['inclination_x']);  # pitch
#        roll = np.deg2rad(json.loads(l)['inclination_y']);  # roll  
#        nx =  np.cos(pitch)*np.sin(roll);
#        ny = -np.sin(pitch);
#        azrad = np.mod(np.arctan2(ny,nx), 2*np.pi)
#        az = np.rad2deg(azrad)

#        if az > 180: az -= 360; #   // do this if your azimuth is always positive i.e. 0-360.
#        if lastAzimuth == -1000: lastAzimuth = az;

#        diff = az - lastAzimuth;
#        if diff > 180:  diff -= 360;
#        if diff < -180: diff += 360;

#        lastAzimuth = az;
#        totalChange += diff;
#        Si[ii] = totalChange / 360;
#        #-----------------------
#    #    if ~np.isnan(Si[ii]): thoff[ii] = th[ii]

    ### Velocity
    vel = 100 * abs(np.nan_to_num( np.divide(np.diff(z),np.diff(t))) )
    vel = savgol_filter(vel, 100, 2) # smoothing

    fh.close()
    jjmax = jj-1
    DCM = DCM[0:(jjmax+1), :,:]
    Z = z[0:(jjmax+1)]

    print('... done')

### Dump z(t) log
#df = pd.DataFrame(zip(t,z), columns = ['t','z'])
#df.to_csv('%s_zt.csv'%LOGFILE, index=False)
#sys.exit(0)

#-----------------------
# BNO055 orientation calibration
#-----------------------

dz = 15 # dz is bin size
    
def binned_average(df):
#    ranges = np.arange(df.z.min() - dz, df.z.max() + dz, dz)
    ranges = np.arange(0, abs(Z_MIN)+dz, dz)
    groups = df.groupby(pd.cut(df.z, ranges))
    meanbins = groups.mean().to_numpy()
    varbins = groups.var().to_numpy()
    return ranges[1:], meanbins[:,1], varbins[:,1] # binned: [ z, mean(incl), var(incl) ]
    
def incl_from_sensordir(x,y):
        sensordir = -np.array([x,y,np.sqrt(1-x**2-y**2)])
        drilldir = np.array([np.matmul(DCM[ii,:,:], sensordir) for ii in np.arange(jjmax+1)])
        incl_raw = np.rad2deg(np.arccos(drilldir[:,2]))
        df = pd.DataFrame(zip(Z,incl_raw), columns = ['z','incl'])
        z_est, inclmean_est, inclvar_est = binned_average(df)
        return z_est, inclmean_est, inclvar_est, incl_raw

df_log = pd.read_csv(LOGGERDATA, names=['z','incl'])
Z_log, inclmean_log, _ = binned_average(df_log)
lograw = df_log.to_numpy()
z_lograw, incl_lograw = lograw[:,0], lograw[:,1]
    
x_opt, y_opt = -0.01, 0.03
Z0fit = 75 # ignore misfit with logger at depths shallower than this number
I0fit = int(Z0fit/dz)

if RUN_SENSOR_ORIENTATION_CALIBRATION:

    print('*** Estimating BNO055 sensor orientation')

    def J(xy):
        Z_est, inclmean_est, inclvar_est, _ = incl_from_sensordir(xy[0], xy[1])
        if 1: # logger misfit?
            errsq = np.power(inclmean_est-inclmean_log, 2)
            J = np.nansum(errsq[I0fit:])
        else: # reduce variance
            J = np.nansum(inclvar_est)
        return J
        
#    x_0, y_0 = 0, 0 # init guess
    x_0, y_0 = x_opt, y_opt # init guess
    paramvec = [x_0,y_0]
    res = minimize(J, paramvec, method='BFGS', tol=1e-4, options={'gtol': 1e-4, 'disp': True})
    x_opt, y_opt = res.x[0], res.x[1]
            
    print('... done: (x_opt, y_opt) = (%f,%f)'%(x_opt,y_opt))
else:
    print('*** Using pre-defined BNO055 sensor orientation: (x_opt, y_opt) = (%f,%f)'%(x_opt,y_opt))
    
Z_est, inclmean_est, inclvar_est, incl_estraw = incl_from_sensordir(x_opt, y_opt)

#code.interact(local=locals())

#-----------------------
# Plot timer series
#-----------------------

if PLOT_TIMESERIES:

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
    ax2.set_yticks(np.arange(0,15+1,2))
    ax2.set_ylim([0, 15])

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
    c_lograw, c_log = '0.6', 'k'
    c_drillraw, c_drill = '#a6cee3', '#1f78b4'
    incllims = [0,7]

    ax1 = plt.subplot(1,2,1)
    ax2 = plt.subplot(1,2,2, sharey=ax1)

    ax1.plot(inclmean_log[I0fit:], -Z_log[I0fit:], c=c_log, lw=2, label='Mean logger (%s)'%flog)
    ax1.plot(inclmean_est[I0fit:], -Z_est[I0fit:], c=c_drill, lw=2, label='Mean drill')
    ax1.set_xlim(incllims)
    ax1.set_ylim([Z_MIN,0])
    ax1.set_ylabel('z (m)')
    ax1.set_xlabel('Inclination (deg)')
    ax1.grid()
    ax1.set_yticks(np.arange(Z_MIN,0+1,200))
    ax1.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
    ax1.legend()

    ax2.scatter(incl_lograw, -z_lograw, marker='.', s=1, c=c_log, label='Raw logger (%s)'%(flog))
    ax2.scatter(incl_estraw, -Z, marker='.', s=1, c=c_drill, label='Raw drill')
    ax2.set_xlim(incllims)
    ax2.set_xlabel('Azimuth (deg)')
    ax2.grid()
    plt.setp(ax2.get_yticklabels(), visible=False)
    ax2.legend()

    imgout = '%s/%s-orientation.png'%(OUTPATH,date_time_str0)
    print('Saving %s'%(imgout))
    plt.savefig(imgout, dpi=300, bbox_inches='tight')

