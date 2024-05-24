#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2024

# REQUIRES OLD MATPLOTLIB VERSION: sudo pip3 install matplotlib==3.4.3

import code # code.interact(local=locals())
import os, sys, math, time

import pandas as pd
from math import copysign, fabs, sqrt, pi, sin, cos, asin, acos, atan2, exp, log
import numpy as np

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button, CheckButtons
from matplotlib.lines import Line2D

from settings import *
from state_drill import *
from state_surface import *

from pyrotation import *

INCL_LIMS = [0,10] # x lims for inclination plot
AZIM_LIMS = [-180,+180] # x lims for azimuth plot
ROLL_LIMS = AZIM_LIMS # x lims for roll plot
Z_MIN = -2800 # y lim for inclination plot

cs_azim = 0 # frame azim offset 
#cs_azim = 180
flowang = np.deg2rad(cs_azim-180 + 27)
azim0, elev0 = -68+cs_azim, 22

c_green  = '#74c476'
c_lgreen = '#edf8e9'
c_dgreen = '#238b45'

c_red  = '#fb6a4a'
c_lred = '#fee5d9'
c_dred = '#cb181d'

c_blue  = '#6baed6'
c_lblue = '#eff3ff'
c_dblue = '#2171b5'

c_dgray = '0.3'
c_lgray = '0.5'

#cx = 'tab:green'
cx = c_dblue
cy = 'none'
cz = c_dred

cex = c_blue
cey = c_dgray
cez = c_red

lw_default = 4.5
alpha0 = 0.09
frameec='0.15' # legend frame edge color

FS = 14
matplotlib.rcParams.update({'font.size': FS})


##################################################
##################################################
##################################################


class QuaternionVisualizer3D():
    '''
    This class demonstrates 3D rotation in the unit quaternion representation
    with a 3D plot.
    '''

    def __init__(self, REDIS_HOST=None, AHRS_estimator=None, dt=1):
        '''
        Constructor.
        '''

        self.drill_sync = True
        self.view_followdrill = False
        
        self.show_sfus = 1
        self.show_ahrs = 0

        self.curr_oriplot = 'inclination'
#        self.curr_oriplot = 'azimuth' # debug

        self.ss = SurfaceState(redis_host=REDIS_HOST, tavg=1, dt_intended=dt)
        self.ds = DrillState(redis_host=REDIS_HOST, AHRS_estimator=AHRS_estimator)   

        self.reset_states()
        self.update_internal_states()
        
        self.setup_ui()
        self.setup_ui_profile(self.curr_oriplot)

    def reset_states(self):
        '''
        Reset to the inital states, where no rotation is applied.
        '''

        # Quat coordinates (x,y,z,w)
        self.qc_sfus = [0,0,0,1]
        self.qc_ahrs = [0,0,0,1]
        
        # Drill inclination history
        dt = 0.8 # update rate
#        H = 0.001# show trail for this number of hours
        H = 0.4 # show trail for this number of hours
        N = int(H*60*60/dt) # number of points to save for incl plot
        print('depth-inclination history length = %i'%(N))
        
        self.drill_depth = np.zeros(N)*np.nan
        self.drill_incl_ahrs = np.zeros(N)*np.nan
        self.drill_incl_sfus = np.zeros(N)*np.nan
        self.drill_azim_ahrs = np.zeros(N)*np.nan
        self.drill_azim_sfus = np.zeros(N)*np.nan
        self.drill_roll_ahrs = np.zeros(N)*np.nan
        self.drill_roll_sfus = np.zeros(N)*np.nan
        

    def update_internal_states(self):
        '''
        Converting the values read from the sliders to internal states.
        Internally, a unit quaternion is used for calculation and plot.
        '''

        # pyrotation Quaternion() objects
        self.q_sfus = Quaternion(*self.xyzw_to_wxyz(self.qc_sfus))
        self.q_ahrs = Quaternion(*self.xyzw_to_wxyz(self.qc_ahrs))
        
    # copy from state_drill.py
    def xyzw_to_wxyz(self, q): return np.roll(q,1)
    def wxyz_to_xyzw(self, q): return np.roll(q,-1)
    
        
    def setup_ui(self):
        '''
        Set up the UI and the 3D plot.
        '''

        self.fig = plt.figure(10, figsize=(7, 9.8), facecolor='w', edgecolor='k')
        plt.get_current_fig_manager().set_window_title('Drill orientation')

        gs = self.fig.add_gridspec(1,1) #, width_ratios=[2,1])
        gs.update(left=0.2, right=0.7, top=0.98, bottom=0.08, wspace=-0.05)

        self.axp  = self.fig.add_subplot(gs[0,0]); 
        
        ### Shared below 
        
        kwargs_text = {'fontsize':FS-1, 'transform':plt.gcf().transFigure}
        
        y0 = 0.97

        x0 = 0.75 # title string start
        x1 = x0+0.01 # box contet start (adjusted inward slightly)
        
        dy = 0.05 # vertical distance between rows of buttons
        dyt = 0.07 # delta y from title string to box content
        
        dl = 2 * 0.09 # botton width
        dh = 0.037 # button height

        self.ax_fake = self.fig.add_axes([x1, y0, dl, dh])
        self.ax_fake.axis('off')

        ### Orientation plot buttons
        
        x0 = 0.75
        y0 = 0.14
        
        plt.text(x0, y0+1.25*dy, 'Orientation plot', fontweight='bold', **kwargs_text)
        axp_incl = self.fig.add_axes([x0, y0-0*dy, dl, dh])
        axp_azim = self.fig.add_axes([x0, y0-1*dy, dl, dh])
        axp_roll = self.fig.add_axes([x0, y0-2*dy, dl, dh])
        self.bp_incl = Button(axp_incl, 'Show incl')
        self.bp_azim = Button(axp_azim, 'Show azim')
        self.bp_roll = Button(axp_roll, 'Show roll')
        self.bp_incl.on_clicked(self.show_incl)
        self.bp_azim.on_clicked(self.show_azim)
        self.bp_roll.on_clicked(self.show_roll)
        
        
        ### Static legend entries
        
        self.legend_lines = [\
                                Line2D([0], [0], color=cex, ls='-', lw=lw_default),\
                                Line2D([0], [0], color=cey, ls='-', lw=lw_default),\
                                Line2D([0], [0], color=cez, ls='-', lw=lw_default),\
                                Line2D([0], [0], color=c_dred, ls='-', lw=lw_default), \
                                Line2D([0], [0], color=c_dblue, ls='-', lw=lw_default), \
                             ]
        
    def setup_ui_profile(self, oriplot):
    
        fields = ['azimuth', 'bottom_sensor', 'compass', 'depth', 'fluxgate_1_raw', 'fluxgate_2_raw', 'inclination', 'inclinometer_1_raw', 'inclinometer_2_raw', 'lower_diameter', \
                  'lower_diameter_max_raw', 'lower_diameter_min_raw', 'pressure', 'pressure_raw', 'record_number', 'temperature_pressure_transducer', 'thermistor_high', 'thermistor_high_raw', \
                  'upper_diameter', 'upper_diameter_max_raw', 'upper_diameter_min_raw', 'thermistor_low', 'thermistor_low_raw']
        self.fname_logger = 'logger-2023-05-05-down.csv' # Logger data
        flogger = os.path.join(os.path.dirname(__file__), "../logging/logger-data/%s"%(self.fname_logger))
        df_logger = pd.read_csv(flogger, names=fields, header=1)
        intvl = 4
        self.logger_depth = df_logger['depth'].to_numpy()[::intvl]
        self.logger_incl  = df_logger['inclination'].to_numpy()[::intvl]
        self.logger_azim  = df_logger['azimuth'].to_numpy()[::intvl]  - 180
        self.logger_roll  = self.logger_azim*np.nan
        
        self.c_logger = 'k'
        self.c_drill  = '#e31a1c'
        self.c_drill2 = '#fb9a99'
        
        self.curr_oriplot = oriplot
        self.axp.clear()

        if self.curr_oriplot == 'inclination':
            self.axp.scatter(self.logger_incl, -self.logger_depth, marker='o', s=3**2, ec=self.c_logger, c='none', label='Logger', zorder=8)
            self.h_oriplot_sfus, = self.axp.plot(self.drill_incl_sfus, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill, label='SFUS', zorder=10)
            self.h_oriplot_ahrs, = self.axp.plot(self.drill_incl_ahrs, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill2, label='AHRS', zorder=9)
            self.axp.set_xlim(INCL_LIMS); 
            self.axp.set_xticks(np.arange(INCL_LIMS[0],INCL_LIMS[1]+1,1))
            self.axp.set_xlabel(r'Inclination (deg)')

        elif self.curr_oriplot == 'azimuth':
            self.axp.scatter(self.logger_azim, -self.logger_depth, marker='o', s=3**2, ec=self.c_logger, c='none', label='Logger', zorder=8)
            self.h_oriplot_sfus, = self.axp.plot(self.drill_azim_sfus, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill, label='SFUS', zorder=10)
            self.h_oriplot_ahrs, = self.axp.plot(self.drill_azim_ahrs, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill2, label='AHRS', zorder=9)
            self.axp.set_xlim(AZIM_LIMS); 
            self.axp.set_xticks(np.arange(AZIM_LIMS[0],AZIM_LIMS[1]+1,90))
            self.axp.set_xlabel(r'Azimuth (deg)')

        elif self.curr_oriplot == 'roll':
            self.h_oriplot_sfus, = self.axp.plot(self.drill_roll_sfus, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill, label='SFUS', zorder=10)
            self.h_oriplot_ahrs, = self.axp.plot(self.drill_roll_ahrs, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill2, label='AHRS', zorder=9)
            self.axp.set_xlim(ROLL_LIMS); 
            self.axp.set_xticks(np.arange(ROLL_LIMS[0],ROLL_LIMS[1]+1,90))
            self.axp.set_xlabel(r'Roll (deg)')

        self.axp.set_ylim([Z_MIN,0])
        self.axp.set_ylabel(r'z (m)')
        self.axp.set_yticks(np.arange(Z_MIN,0+1,200))
        self.axp.set_yticks(np.arange(Z_MIN,0+1,100),minor=True)
        self.axp.grid(); 

        kwargs_legend = {'fancybox':False, 'fontsize':FS}
        self.axp.legend(frameon=True, framealpha=1, edgecolor=frameec, facecolor='w', loc=1, **kwargs_legend); 
        bbox = bbox=dict(boxstyle="square,pad=0.6", ec=frameec, fc='w',)
        self.axp.text(0.875, 0.5, 'If profile does not match logger,\norientation sensor is not well-calibrated.', bbox=bbox, rotation=90, ha='center', va='center', transform=self.axp.transAxes, fontsize=FS)
                
        self.update_axp_plot()
        

    def show_incl(self, *args, **kwargs): self.setup_ui_profile('inclination')
    def show_azim(self, *args, **kwargs): self.setup_ui_profile('azimuth')
    def show_roll(self, *args, **kwargs): self.setup_ui_profile('roll')
    

    def update_axp_plot(self):

        self.h_oriplot_ahrs.set_ydata(self.drill_depth)
        self.h_oriplot_sfus.set_ydata(self.drill_depth)

        if self.curr_oriplot == 'inclination':
            self.h_oriplot_ahrs.set_xdata(self.drill_incl_ahrs)
            self.h_oriplot_sfus.set_xdata(self.drill_incl_sfus)
            
        elif self.curr_oriplot == 'azimuth':
            self.h_oriplot_ahrs.set_xdata(self.drill_azim_ahrs)
            self.h_oriplot_sfus.set_xdata(self.drill_azim_sfus)
            
        elif self.curr_oriplot == 'roll':
            self.h_oriplot_ahrs.set_xdata(self.drill_roll_ahrs)
            self.h_oriplot_sfus.set_xdata(self.drill_roll_sfus)


    def run(self, dt=1, debug=False, REDIS_HOST=REDIS_HOST, AHRS_estimator='SAAM'):

        nn = 0

        while True:

            fignums = plt.get_fignums()
            if len(fignums)==0 or fignums[0] != 10: sys.exit('Figure closed. Exiting.')

            # Let GUI event loop run for this amount before exiting and updating orientation state.
            # This is similar to plt.pause(dt), but does not steal focus on every update.
            plt.gcf().canvas.draw_idle()
            plt.gcf().canvas.start_event_loop(dt)

            if self.drill_sync:

                try:
                    self.ss.update()                    
                    self.ds.update()
                except:
                    print('unable to update SurfaceState and DrillState... skipping')
                    continue

                #self.qc0_sfus = self.qc0_ahrs = Rotation.identity().as_quat()
                #self.qc_sfus = self.qc_ahrs = Rotation.identity().as_quat()

                self.qc0_sfus = self.ds.quat0_sfus
                self.qc0_ahrs = self.ds.quat0_ahrs
                self.qc_sfus = self.ds.quat_sfus
                self.qc_ahrs = self.ds.quat_ahrs
                
#                print(self.ds.inclination_sfus, self.ds.azimuth_sfus, self.ds.roll_sfus)

                self.drill_depth[nn] = -abs(self.ss.depth)
                self.drill_incl_ahrs[nn] = self.ds.incl_ahrs
                self.drill_incl_sfus[nn] = self.ds.incl_sfus
                self.drill_azim_ahrs[nn] = self.ds.azim_ahrs
                self.drill_azim_sfus[nn] = self.ds.azim_sfus
                self.drill_roll_ahrs[nn] = self.ds.roll_ahrs
                self.drill_roll_sfus[nn] = self.ds.roll_sfus
                nn += 1
                if nn > len(self.drill_depth)-1: nn = 0 # wrap around
                
                self.update_internal_states()
#                self.update_ax3d_plot()
                self.update_axp_plot()


            if debug: print('Tick dt=%.2f'%(dt))


##############################################################################################            
##############################################################################################
##############################################################################################

if __name__ == '__main__':

    AHRS_estimator = 'SAAM' if len(sys.argv) < 2 else sys.argv[1]
    dt = 1
    plt.ion()
    vis = QuaternionVisualizer3D(REDIS_HOST=REDIS_HOST, AHRS_estimator=AHRS_estimator, dt=dt)
    vis.run(dt=dt, debug=False)
    pass


