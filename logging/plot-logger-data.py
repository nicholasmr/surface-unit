#!/usr/bin/python
# N. Rathmann, 2017-2022

import numpy as np
import code # code.interact(local=locals())
import sys, os, time, csv, datetime, time, json, scipy
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd

PLOT_PANELS = 1
PLOT_BOREHOLE = 0

Z_MAX, Z_MIN = 0, -2800 # y axis

fields_oldlogger1 = ['azimuth', 'bottom_sensor', 'compass', 'depth', 'fluxgate_1_raw', 'fluxgate_2_raw', 'inclination', 'inclinometer_1_raw', 'inclinometer_2_raw', 'lower_diameter', \
                    'lower_diameter_max_raw', 'lower_diameter_min_raw', 'pressure', 'pressure_raw', 'record_number', 'temperature_pressure_transducer', 'thermistor_high', 'thermistor_high_raw', \
                    'upper_diameter', 'upper_diameter_max_raw', 'upper_diameter_min_raw', 'thermistor_low', 'thermistor_low_raw']

fields_oldlogger2 = ["azimuth","bottom_sensor","compass","depth","fluxgate_1_raw","fluxgate_2_raw","inclination","inclinometer_1_raw","inclinometer_2_raw","lower_diameter", \
                     "lower_diameter_max_raw","lower_diameter_min_raw","pressure","pressure_raw","record_number","temperature_pressure_transducer","thermistor_high","thermistor_high_raw", \
                     "thermistor_low","thermistor_low_raw","upper_diameter","upper_diameter_max_raw","upper_diameter_min_raw"]

logger_2022 =  {\
    'name': 'oldlogger down @ 2022-07-09', \
    'isdrill': False, \
    'fields': fields_oldlogger1, \
    'delim_whitespace': False, \
    'header': None, \
    'negdepth': False, \
    'color': 'k', \
    'colorlight': '0.5' \
}

logger_2023 = {\
    'name': 'oldlogger down @ 2023-05-05', \
    'isdrill': False, \
    'fields': fields_oldlogger2, \
    'delim_whitespace': False, \
    'header': 1, \
    'negdepth': False, \
    'color': '#e31a1c', \
    'colorlight': '#fb9a99' \
}

drill_2023 = {\
    'name': 'drill down+up @ 2022-08-06', \
    'isdrill': True, \
    'fields': ['depth','inclination','azimuth'], \
    'delim_whitespace': False, \
    'header': 1, \
    'negdepth': True, \
    'color': '#a6cee3', \
    'colorlight': '#1f78b4' \
}

files = {
   'logger-data/logger-2022-07-09-down.csv': logger_2022, \
   'logger-data/logger-2023-05-05-down.csv': logger_2023, \
   'drill-logs-processed/drill-orientation-2022-08-06.csv': drill_2023, \
}

if PLOT_BOREHOLE: 
    files = {'logger-data/logger-2023-05-05-down.csv': logger_2023, } 

scale = 0.75
fig = plt.figure(figsize=(scale*20,scale*10))
c_drill, c_drill2, c_logger, c_loggernew = '#1f78b4', '#9ecae1', '0.6', 'k'

xlims = {'temp': [-33, -10], 'incl': [0, 5.5], 'azim':[0,360], 'D':[128, 137]};

gs = gridspec.GridSpec(1, 4, figure=fig)
ax1 = fig.add_subplot(gs[0, 0])
ax2 = fig.add_subplot(gs[0, 1], sharey=ax1)
ax3 = fig.add_subplot(gs[0, 2], sharey=ax1)
ax4 = fig.add_subplot(gs[0, 3], sharey=ax1)

dz = 15 # dz is data bin size 
z_bin_full = np.arange(0, abs(Z_MIN)+dz, dz) # new z-axis
z_bin = z_bin_full[1:]

def binned_stats(df, depth):
    groups = df.groupby(pd.cut(depth, z_bin_full))
    meanbins, varbins = groups.mean().to_numpy(), groups.var().to_numpy()
    return meanbins[:], varbins[:] # binned: [ mean(inc), var(inc) ]
    
for fname in files:
    
    print('>>> %s'%(fname))
    
    f = os.path.join(os.path.dirname(__file__), "%s"%(fname)) # full path
    fobj = files[fname]
    df = pd.read_csv(f, names=fobj['fields'], header=fobj['header'], delim_whitespace=fobj['delim_whitespace']) # , names=fobj['fields'], header=fobj['header'], delim_whitespace=fobj['delim_whitespace']
    depth = (-1 if fobj['negdepth'] else +1) * df['depth'].to_numpy()
    
    groups = df.groupby(pd.cut(depth, z_bin_full))
    meanbins, varbins = groups.mean().to_numpy(), groups.var().to_numpy()

#    dazim = 0
    dazim = 290
    azim = df['azimuth'].to_numpy()+dazim
    azim[azim>360] -= 360 
    df['azimuth'][:] = azim
    
    depth_mean, _ = binned_stats(df['depth'], depth)
    incl_mean,  _ = binned_stats(df['inclination'], depth)
    azim_mean,  _ = binned_stats(df['azimuth'], depth)
    if fobj['isdrill']:
        temp_mean = depth_mean*np.nan
        Dlow_mean = depth_mean*np.nan
    else:
        temp_mean,  _ = binned_stats(df['thermistor_high'], depth)
        Dlow_mean,  _ = binned_stats(df['lower_diameter'], depth)

    incl = df['inclination'].to_numpy()
    azim = df['azimuth'].to_numpy()
    if fobj['isdrill']:
        temp = depth*np.nan
        Dlow = depth*np.nan
    else:
        temp = df['thermistor_high'].to_numpy() 
        Dlow = df['lower_diameter'].to_numpy() 

    if PLOT_PANELS:

        mss = 6**2
        lw = 2
        
        ax = ax1
        ax.scatter(temp, -depth, marker='o', s=mss, c='none', edgecolors=fobj['colorlight'], label=fobj['name'])
        ax.plot(temp_mean, -depth_mean, '-', lw=lw, c=fobj['color'])
        ax.set_xlim(xlims['temp']); 
        ax.set_ylim([Z_MIN,0])
        ax.set_ylabel('$z$ (km)'); 
        ax.set_xlabel('$T$ (C)')
        ax.set_yticks(np.arange(Z_MIN,0+1,200))
        ax.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
        ax.grid()
        ax.legend(loc=3)

        ax = ax2
        ax.scatter(incl, -depth, marker='o', s=mss, c='none', edgecolors=fobj['colorlight'], label=fobj['name'])
        ax.plot(incl_mean, -depth_mean, '-', lw=lw, c=fobj['color'])
        ax.set_xlim(xlims['incl']); 
        ax.set_ylim([Z_MIN,0])
    #    ax.set_ylabel('$z$ (km)'); 
        ax.set_xlabel(r'$\theta$ (deg.)')
        ax.set_yticks(np.arange(Z_MIN,0+1,200))
        ax.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
        ax.grid()
        ax.legend(loc=3)
        plt.setp(ax.get_yticklabels(), visible=False)
        
        ax = ax3
        ax.scatter(azim, -depth, marker='o', s=mss, c='none', edgecolors=fobj['colorlight'], label=fobj['name'])
        ax.plot(azim_mean, -depth_mean, '-', lw=lw, c=fobj['color'])
        ax.set_xlim(xlims['azim']); 
        ax.set_ylim([Z_MIN,0])
    #    ax.set_ylabel('$z$ (km)'); 
        ax.set_xlabel(r'$\phi$ + %i (deg.)'%(dazim))
        ax.set_yticks(np.arange(Z_MIN,0+1,200))
        ax.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
        ax.grid()
        ax.legend(loc=3)
        plt.setp(ax.get_yticklabels(), visible=False)
        
        ax = ax4
        ax.scatter(Dlow, -depth, marker='o', s=mss, c='none', edgecolors=fobj['colorlight'], label=fobj['name'])
        ax.plot(Dlow_mean, -depth_mean, '-', lw=lw, c=fobj['color'])
        ax.set_xlim(xlims['D']); 
        ax.set_ylim([Z_MIN,0])
    #    ax.set_ylabel('$z$ (km)'); 
        ax.set_xlabel(r'$D_{lower}$ (mm)')
        ax.set_yticks(np.arange(Z_MIN,0+1,200))
        ax.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
        ax.grid()
        ax.legend(loc=3)
        plt.setp(ax.get_yticklabels(), visible=False)
    
if PLOT_PANELS:   
    imgout = 'logger-plot.png'
    print('Saving %s'%(imgout))
    plt.savefig(imgout, dpi=300, bbox_inches='tight')


#######################################################

if PLOT_BOREHOLE:
   
    I = ~np.isnan(depth_mean)
    l = depth_mean[I] # length along borehole
    theta = incl_mean[I]
    phi = azim_mean[I]
    dl = np.diff(l) # incremental vector length

    r = np.zeros((3,len(l)))
    r[2,0] = l[0] # z-coordinate of first point on borehole curve

    for ii in np.arange(1,len(l)):
        t, p = np.deg2rad(theta[ii]), np.deg2rad(phi[ii])
        ct, st = np.cos(t), np.sin(t)
        cp, sp = np.cos(p), np.sin(p)
        rhat = np.array([st*cp,st*sp,ct]) 
        dr = dl[ii-1] * rhat
        r[:,ii] = r[:,ii-1] + dr 
   
    scale = 1.2
    fig = plt.figure(figsize=(scale*5,scale*5))
    ax = plt.figure().add_subplot(projection='3d')
    ax.view_init(elev=20, azim=80)

    ax.plot(r[0,:], r[1,:], Z_MIN, '.-', c='0.5')    
    ax.plot(r[0,:], r[1,:], -r[2,:], '.-', c='tab:red')

    ax.set_zlim([Z_MIN,0])    
    ax.set_zlabel('$z$ (m)')
    
    ax.set_xlabel('$x$ (m)')
    ax.set_ylabel('$y$ (m)')
    
    ax.set_title('EGRIP borehole geometry')
    
    imgout = 'logger-borehole-stem.png'
    print('Saving %s'%(imgout))
    plt.savefig(imgout, dpi=200, bbox_inches='tight')

