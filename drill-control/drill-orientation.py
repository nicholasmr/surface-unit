#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2023

import code # code.interact(local=locals())

import os, sys, math, time
import pandas as pd
from math import copysign, fabs, sqrt, pi, sin, cos, asin, acos, atan2, exp, log
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d
from matplotlib.widgets import Slider, Button, CheckButtons
from matplotlib.lines import Line2D

from settings import *
from state_drill import *
from state_surface import *

from pyrotation import *

SHOW_PLUMB_BUTTONS = False

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

#cx = '0.5'
cx = 'none'
cy = c_dblue
cz = c_dred

cex = c_red
cey = c_blue
cez = c_dgray

lw_default = 4.5
alpha0 = 0.09
frameec='0.15' # legend frame edge color

FS = 14
matplotlib.rcParams.update({'font.size': FS})

##############################################################################################            
##############################################################################################
##############################################################################################

def rotate_translate_points(p, rotation, t, method):
    '''
    Rotate and translate 3D points given a rotation representation in
    "rotation" and a translation vector "t". The rotation can be either a
    rotation matrix, a quaternion, or an angle-axis vector, indicated by
    the "method". There are three methods, as follows.
    
        (1) angle-axis, indicated by method = "u".
        (2) rotation matrix, indicated by method = "R".
        (3) quaternion, indicated by method = "q". 
    
    The input points "p" must be a numpy 3-by-n matrix, and the translation
    vector must be a numpy 3-by-1 matrix.    
    '''
    
    if method == 'u': # angle-axis
        p = rotate_points_by_angle_axis(p, rotation) + t
    elif method == 'R': # rotation matrix
        p = np.matmul(rotation, p) + t
    elif method == 'q': # quaternion
        p = rotation.rotate_points(p) + t
    else:
        raise ValueError('Unknown method: %s' % str(method))
    
    return p


class Arrow3D(FancyArrowPatch):
    '''
    3D arrow object the can be drawn with matplotlib. 
    '''

    def __init__(self, xs, ys, zs, *args, **kwargs):
        super().__init__((0,0), (0,0), *args, **kwargs)
        self._verts3d = xs, ys, zs

    def draw(self, renderer=None):
        xs3d, ys3d, zs3d = self._verts3d
        xs, ys, zs = proj3d.proj_transform(xs3d, ys3d, zs3d, self.axes.M)
        self.set_positions((xs[0],ys[0]),(xs[1],ys[1]))
        FancyArrowPatch.draw(self, renderer)

##############################################################################################            
##############################################################################################
##############################################################################################

class RotationVisualizer3D(object):
    '''
    Abstract visualizer class which contains a bunch of helper functions.
    This class can not be used directly for visualizing a 3D rotation.
    '''        

    def plot_arrow(self, ax, ox, oy, oz, ux, uy, uz, color='k', lw=lw_default):
        '''
        Plot an 3D arrow from (ox, oy, oz) to (ux, uy, uz).
        '''
        arrow = Arrow3D((ox, ux), (oy, uy), (oz, uz), mutation_scale=30, lw=lw, arrowstyle="-|>", color=color)    
        ax.add_artist(arrow)
        

    def plot_vector(self, ax, x, y, z, ox=0, oy=0, oz=0, style='-', color='k', lw=lw_default, lwax=lw_default, arrow=False, arrow_rho=0.94):
        '''
        Plot a 3D vector from (ox, oy, oz) to (x, y, z).
        '''
        
        ax.plot((ox, x), (oy, y), (oz, z), style, lw=lw, color=color)
        
        if arrow:
            aox = ox * (1 - arrow_rho) + x * arrow_rho
            aoy = oy * (1 - arrow_rho) + y * arrow_rho
            aoz = oz * (1 - arrow_rho) + z * arrow_rho
            self.plot_arrow(ax, aox, aoy, aoz, x, y, z, color=color, lw=lw)


    def plot_xyz_axes(self, ax, rotation, t, scale=1, style='-', cx=cx, cy=cy, cz=cz, arrow=False, method='R'):
        '''
        Plot the xyz axes indication using three short line segments in red, green 
        and blue, given the new reference frame indicated by (R, t). 
        '''
    
        x = np.asarray([[0, 0, 0], [scale, 0, 0]]).T
        x = rotate_translate_points(x, rotation, t, method)
    
        y = np.asarray([[0, 0, 0], [0, scale, 0]]).T
        y = rotate_translate_points(y, rotation, t, method)
    
        z = np.asarray([[0, 0, 0], [0, 0, scale]]).T
        z = rotate_translate_points(z, rotation, t, method)

        self.plot_vector(ax, x[0, 1], x[1, 1], x[2, 1],  x[0, 0], x[1, 0], x[2, 0],  style=style, color=cx, arrow=arrow)
        self.plot_vector(ax, y[0, 1], y[1, 1], y[2, 1],  y[0, 0], y[1, 0], y[2, 0],  style=style, color=cy, arrow=arrow)
        self.plot_vector(ax, z[0, 1], z[1, 1], z[2, 1],  z[0, 0], z[1, 0], z[2, 0],  style=style, color=cz, arrow=arrow)

    
    def plot_arc_points(self, ax, x, y, z, rotation, t, style='-', color='k', lw=lw_default, arrow=False, method='R'):
        '''
        Plot a sequence of 3D points of an arc.
        '''
        
        nr_points = x.shape[0]
        
        p = np.zeros((3, nr_points))
        p[0, :] = x
        p[1, :] = y
        p[2, :] = z
        
        p = rotate_translate_points(p, rotation, t, method)
        
        ax.plot(p[0, :], p[1, :], p[2, :], style, lw=lw, color=color)

        if arrow: self.plot_arrow(ax, p[0, -2], p[1, -2], p[2, -2], p[0, -1], p[1, -1], p[2, -1], color=color)
            

    def plot_surface(self, ax, x, y, z, rotation, t, color='w', alpha=alpha0, method='R'):
        '''
        Fill a surface in the 3D space using a set of points.
        
        CAUTION: matplotlib is not a full-fledged 3D rendering engine!
        There might be problems when multiple surfaces are plotted.
        '''
        s = x.shape
        x = x.flatten()
        y = y.flatten()
        z = z.flatten()
        
        p = np.zeros((3, x.shape[0]))
        p[0, :] = x
        p[1, :] = y
        p[2, :] = z
        
        p = rotate_translate_points(p, rotation, t, method)
          
        x = p[0, :].reshape(s)
        y = p[1, :].reshape(s)
        z = p[2, :].reshape(s)
        
        ax.plot_surface(x, y, z, color=color, linewidth=0, alpha=alpha, antialiased=True)

    
    def generate_arc_angles(self, start, angle, step=0.02):
        '''
        Generate a sequence of angles on an arc.
        '''
        
        if fabs(angle) < step * 2:
            return None
        
        if angle > 2 * np.pi:  angle = 2 * np.pi
        if angle < -2 * np.pi: angle = -2 * np.pi
        a = np.linspace(start, start + angle, int(fabs(angle) // step))

        return a
    
    
    def generate_sector_radius_and_angles(self, start, angle, r, step=0.02):
        '''
        Generate a sequence of radius and angles on a sector.
        CAUTION: This uses numpy.meshgrid().
        '''
        
        if fabs(angle) < 0.04 or fabs(r) < 0.1:
            return None
        
        if angle > 2 * np.pi:  angle = 2 * np.pi
        if angle < -2 * np.pi: angle = -2 * np.pi

        rs = np.linspace(0, r, int(r // 0.1))
        ps = np.linspace(start, start + angle, int(fabs(angle) // 0.1))
        RS, PS = np.meshgrid(rs, ps)
    
        return RS, PS
    
    
    def plot_arc(self, ax, start, angle, rotation, t, r, plane='xoy', style='-', lw=lw_default, color='k', arrow=False, method='R'):
        '''
        Plot an arc in 3D.
        '''
        
        a = self.generate_arc_angles(start, angle)
        
        if a is not None:
            
            if plane == 'xoy':
                x = r * np.cos(a)
                y = r * np.sin(a)
                z = np.zeros(a.shape)
                
            elif plane == 'yoz':
                x = np.zeros(a.shape)
                y = r * np.cos(a)
                z = r * np.sin(a)
                
            elif plane == 'zox':
                x = r * np.sin(a)
                y = np.zeros(a.shape)
                z = r * np.cos(a)
                
            else:
                raise ValueError('Unknown plane: %s' % str(plane))
                
            self.plot_arc_points(ax, x, y, z, rotation, t, style=style, color=color, lw=lw, arrow=arrow, method=method)

        

    def plot_circle(self, ax, rotation, t, r, plane='xoy', style='-', color='k', arrow=False, method='R'):
        '''
        Plot a circle in 3D.
        '''
        
        self.plot_arc(ax, 0, 2 * np.pi, rotation, t, r, plane=plane, style=style, color=color, arrow=arrow, lw=3, method=method)
    
    def plot_sector(self, ax, start, angle, rotation, t, r, plane='xoy', color='w', alpha=alpha0, method='R'):
        '''
        Plot a sector in 3D.
        '''
        
        tup = self.generate_sector_radius_and_angles(start, angle, r)
        
        if tup is not None:
            
            RS, PS = tup
            
            if plane == 'xoy':
                x = RS * np.cos(PS)
                y = RS * np.sin(PS)
                z = np.zeros(x.shape)
                
            elif plane == 'yoz':
                y = RS * np.cos(PS)
                z = RS * np.sin(PS)
                x = np.zeros(y.shape)
                
            elif plane == 'zox':
                z = RS * np.cos(PS)
                x = RS * np.sin(PS)
                y = np.zeros(z.shape)
                
            else:
                raise ValueError('Unknown plane: %s' % str(plane))
            
            self.plot_surface(ax, x, y, z, rotation, t, color=color, alpha=alpha, method=method)
            

    def plot_disk(self, ax, rotation, t, r, plane='xoy', color='w', alpha=alpha0, method='R'):
        '''
        Plot a disk in 3D.
        '''

        self.plot_sector(ax, 0, 2 * np.pi, rotation, t, r, plane=plane, color=color, alpha=alpha, method=method)
    
    
    def adjust_axes(self, ax, scale=2):
        '''
        Adjust the limite and aspect ratio of a 3D plot.
        '''
        
        ticks = [-1,+1]
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.set_zticks(ticks)

        ticks = [-2,-1,0,+1,+2]
        ax.set_xticks(ticks, minor=True)
        ax.set_yticks(ticks, minor=True)
        ax.set_zticks(ticks, minor=True)
        
        ax.set_xlim(-scale, scale)
        ax.set_ylim(-scale, scale)
        ax.set_zlim(-scale, scale/3)

        ax.set_xlabel('$x$', fontsize=FS+2)
        ax.set_ylabel('$y$', fontsize=FS+2)
        ax.set_zlabel('$z$', fontsize=FS+2)


##################################################
##################################################
##################################################


class QuaternionVisualizer3D(RotationVisualizer3D):
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
        
        # Calibration quat 
        self.qc_calib_sfus = Rotation.identity().as_quat()
        self.qc_calib_ahrs = Rotation.identity().as_quat()
        
        # Euler angles
        self.incl, self.azim = 0, 0
        
        # Drill inclination history
        dt = 0.8 # update rate
#        H = 0.001# show trail for this number of hours
        H = 0.4 # show trail for this number of hours
        N = int(H*60*60/dt) # number of points to save for incl plot
        print('depth-inclination history length = %i'%(N))
        
        self.drill_depth = np.zeros(N)*np.nan
        self.drill_inclination_ahrs = np.zeros(N)*np.nan
        self.drill_inclination_sfus = np.zeros(N)*np.nan
        self.drill_azimuth_ahrs = np.zeros(N)*np.nan
        self.drill_azimuth_sfus = np.zeros(N)*np.nan
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

        self.fig = plt.figure(10, figsize=(20, 9.8), facecolor='w', edgecolor='k')
        plt.get_current_fig_manager().set_window_title('Drill orientation')

        gs = self.fig.add_gridspec(1,3, width_ratios=[2,8,3])
        gs.update(left=0.07, right=1, top=0.98, bottom=0.08, wspace=-0.25)

        self.axp  = self.fig.add_subplot(gs[0,0]); 
        self.ax3d = self.fig.add_subplot(gs[0,1], projection='3d'); 

#        self.ax3d = self.fig.add_axes([0.0, 0.0, 0.70, 1], projection='3d')
        self.ax3d.view_init(azim=azim0, elev=elev0)
        
        ### Shared below 
        
        kwargs_text = {'fontsize':FS-1, 'transform':plt.gcf().transFigure}
        
        y0 = 0.97

        x0 = 0.75 # title string start
        x1 = x0+0.01 # box contet start (adjusted inward slightly)
        
        dy = 0.05 # vertical distance between rows of buttons
        dyt = 0.07 # delta y from title string to box content
        
        dl = 0.09 # botton width
        dh = 0.037 # button height

        self.ax_fake = self.fig.add_axes([x1, y0, dl, dh])
        self.ax_fake.axis('off')

        plt.text(x0, y0, 'Calibration procedure', fontweight='bold', **kwargs_text)        

#        bbox = bbox=dict(boxstyle="square,pad=0.6", ec=frameec, fc='w',)
        bbox = None
        plt.text(x0, y0-0.35*dy, \
'''Orientation sensor must be re-calibrated before every run:
(1) Power drill off for 10 seconds and then on. Leave the drill horizontally on the tower, completely still, for 10 seconds to calibrate the gyroscope.
(2) While horizontal on tower, rotate the drill slowly in approx. 90 deg. increments, leaving it for ~10 seconds each time.
(3) Rotate drill so the *true* direction of spring is opposite of driller's cabin and click "SFUS horiz." and "AHRS horiz." buttons below; drill and spring direction should now align with the trench frame-of-reference. 
(4) Tilt tower to vertical and repeat 90 deg. rotations (but do not click the buttons).
(5) Rotate drill back to horizontal. If drill axis and spring direction do not *approx. match* the calibration made at step 3, then repeat steps 2-5. If they approx. match, you are ready to go!''', \
ha='left', va='top', wrap=True, bbox=bbox, fontsize=FS-2, linespacing=1+0.25, transform=plt.gcf().transFigure)        

                
        ### Calibrate/offset 

        y0 = y0-0.53
        plt.text(x0, y0, 'Rotate to trench frame-of-reference', fontweight='bold', **kwargs_text)        
        dl_ = dl*1.2

        ax_calib_ahrs0 = self.fig.add_axes([x1, y0-dyt-1*dy, dl_, dh])
        ax_calib_sfus0 = self.fig.add_axes([x1, y0-dyt-0*dy, dl_, dh])
        b_calib_ahrs0 = Button(ax_calib_ahrs0, r'AHRS horiz.')
        b_calib_sfus0 = Button(ax_calib_sfus0, r'SFUS horiz.')
        b_calib_ahrs0.on_clicked(self.set_calibrate_ahrs0)
        b_calib_sfus0.on_clicked(self.set_calibrate_sfus0)
        plt.b_calib_ahrs0 = b_calib_ahrs0
        plt.b_calib_sfus0 = b_calib_sfus0

        if SHOW_PLUMB_BUTTONS:
            ax_calib_ahrs1 = self.fig.add_axes([x1+1.2*dl_, y0-dyt-1*dy, dl_, dh])
            ax_calib_sfus1 = self.fig.add_axes([x1+1.2*dl_, y0-dyt-0*dy, dl_, dh])
            b_calib_ahrs1 = Button(ax_calib_ahrs1, r'AHRS plumb')
            b_calib_sfus1 = Button(ax_calib_sfus1, r'SFUS plumb')
            b_calib_ahrs1.on_clicked(self.set_calibrate_ahrs1)
            b_calib_sfus1.on_clicked(self.set_calibrate_sfus1)
            plt.b_calib_ahrs1 = b_calib_ahrs1
            plt.b_calib_sfus1 = b_calib_sfus1

        ax_uncalib0 = self.fig.add_axes([x1,         y0-dyt-2*dy, dl_, dh])
        b_uncalib0  = Button(ax_uncalib0, r'Clear horiz.')
        b_uncalib0.on_clicked(self.set_uncalibrate0)
        plt.b_uncalib0 = b_uncalib0        

        if SHOW_PLUMB_BUTTONS:
            ax_uncalib1 = self.fig.add_axes([x1+1.2*dl_, y0-dyt-2*dy, dl_, dh])
            b_uncalib1  = Button(ax_uncalib1, r'Clear plumb')
            b_uncalib1.on_clicked(self.set_uncalibrate1)
            plt.b_uncalib1 = b_uncalib1

#        y0_ = 0.925
        y0_ = 0.05
        x0_ = 0.51
#        bbox = bbox=dict(boxstyle="square,pad=0.6", ec=frameec, fc='w',)
        bbox = None
        self.text_calib_title = plt.text(x0_, y0_+1.1*dy, 'Frame-of-reference offset', fontweight='bold', bbox=bbox, **kwargs_text)
        self.text_calib = plt.text(x0_, y0_-0*dy, '', bbox=bbox, **kwargs_text)


        ### View buttons

        y0 = y0-0.22
        
        plt.text(x0, y0, 'Change view', fontweight='bold', **kwargs_text)
        axv_sideways   = self.fig.add_axes([x1, y0-dyt-0*dy, dl, dh])
        axv_topdown    = self.fig.add_axes([x1, y0-dyt-1*dy, dl, dh])
        axv_alongdrill = self.fig.add_axes([x1, y0-dyt-2*dy, dl, dh])
        bv_sideways   = Button(axv_sideways, 'Sideways')
        bv_topdown    = Button(axv_topdown, 'Top-down')
        bv_alongdrill = Button(axv_alongdrill, 'Along drill')
        bv_sideways.on_clicked(self.view_sideways)
        bv_topdown.on_clicked(self.view_topdown)
        bv_alongdrill.on_clicked(self.view_alongdrill)
        plt.bv_sideways   = bv_sideways
        plt.bv_topdown    = bv_topdown
        plt.bv_alongdrill = bv_alongdrill

        axv_ahrs = self.fig.add_axes([x1+1.3*dl, y0-dyt-1*dy, dl, dh])
        axv_sfus = self.fig.add_axes([x1+1.3*dl, y0-dyt-0*dy, dl, dh])
        bv_ahrs = Button(axv_ahrs, 'Toggle AHRS')
        bv_sfus = Button(axv_sfus, 'Toggle SFUS')
        bv_ahrs.on_clicked(self.toggle_ahrs)
        bv_sfus.on_clicked(self.toggle_sfus)
        plt.bv_ahrs = bv_ahrs
        plt.bv_sfus = bv_sfus
        
        ### Orientation plot buttons
        
        x0 = 0.275
        y0 = 0.14
        plt.text(x0, y0+1.25*dy, 'Orientation plot', fontweight='bold', **kwargs_text)
        axp_incl = self.fig.add_axes([x0, y0-0*dy, dl, dh])
        axp_azim = self.fig.add_axes([x0, y0-1*dy, dl, dh])
        axp_roll = self.fig.add_axes([x0, y0-2*dy, dl, dh])
        self.bp_incl = Button(axp_incl, 'Show inclination')
        self.bp_azim = Button(axp_azim, 'Show azimuth')
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
        
        ### Finish
        
        self.update_ax3d_plot()
        

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
            self.h_oriplot_sfus, = self.axp.plot(self.drill_inclination_sfus, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill, label='SFUS', zorder=10)
            self.h_oriplot_ahrs, = self.axp.plot(self.drill_inclination_ahrs, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill2, label='AHRS', zorder=9)
            self.axp.set_xlim(INCL_LIMS); 
            self.axp.set_xticks(np.arange(INCL_LIMS[0],INCL_LIMS[1]+1,1))
            self.axp.set_xlabel(r'Inclination (deg)')

        elif self.curr_oriplot == 'azimuth':
            self.axp.scatter(self.logger_azim, -self.logger_depth, marker='o', s=3**2, ec=self.c_logger, c='none', label='Logger', zorder=8)
            self.h_oriplot_sfus, = self.axp.plot(self.drill_azimuth_sfus, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill, label='SFUS', zorder=10)
            self.h_oriplot_ahrs, = self.axp.plot(self.drill_azimuth_ahrs, self.drill_depth, ls='none', marker='o', markersize=6, color=self.c_drill2, label='AHRS', zorder=9)
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
        

    def view_sideways(self, *args, **kwargs):
        print('View = sideways')
        self.view_followdrill = False
        self.ax3d.view_init(azim=azim0, elev=elev0)
        plt.draw()
        
    def view_topdown(self, *args, **kwargs):
        print('View = top-down')
        self.view_followdrill = False
        self.ax3d.view_init(azim=-90-cs_azim, elev=90)
        plt.draw()
        
    def view_alongdrill(self, *args, **kwargs):
        print('View = top-down')
        self.view_followdrill = True
        plt.draw()
        
    def toggle_ahrs(self, *args, **kwargs): self.show_ahrs = not self.show_ahrs 
    def toggle_sfus(self, *args, **kwargs): self.show_sfus = not self.show_sfus

    def set_uncalibrate0(self, *args, **kwargs): 
        self.ds.set_oricalib_horiz(None, 'sfus')
        self.ds.set_oricalib_horiz(None, 'ahrs')

    def set_uncalibrate1(self, *args, **kwargs): 
        self.ds.set_oricalib_vert(None, 'sfus')
        self.ds.set_oricalib_vert(None, 'ahrs')

    def set_calibrate_sfus0(self, *args, **kwargs): self.ds.set_oricalib_horiz(self.ds.quat0_sfus, 'sfus')
    def set_calibrate_sfus1(self, *args, **kwargs): self.ds.set_oricalib_vert(self.ds.quat0_sfus,  'sfus')

    def set_calibrate_ahrs0(self, *args, **kwargs): self.ds.set_oricalib_horiz(self.ds.quat0_ahrs, 'ahrs')
    def set_calibrate_ahrs1(self, *args, **kwargs): self.ds.set_oricalib_vert(self.ds.quat0_ahrs,  'ahrs')

    def show_incl(self, *args, **kwargs): self.setup_ui_profile('inclination')
    def show_azim(self, *args, **kwargs): self.setup_ui_profile('azimuth')
    def show_roll(self, *args, **kwargs): self.setup_ui_profile('roll')
    

    def update_axp_plot(self):

        self.h_oriplot_ahrs.set_ydata(self.drill_depth)
        self.h_oriplot_sfus.set_ydata(self.drill_depth)

        if self.curr_oriplot == 'inclination':
            self.h_oriplot_ahrs.set_xdata(self.drill_inclination_ahrs)
            self.h_oriplot_sfus.set_xdata(self.drill_inclination_sfus)
            
        elif self.curr_oriplot == 'azimuth':
            self.h_oriplot_ahrs.set_xdata(self.drill_azimuth_ahrs)
            self.h_oriplot_sfus.set_xdata(self.drill_azimuth_sfus)
            
        elif self.curr_oriplot == 'roll':
            self.h_oriplot_ahrs.set_xdata(self.drill_roll_ahrs)
            self.h_oriplot_sfus.set_xdata(self.drill_roll_sfus)

    
    def update_ax3d_plot(self):
        '''
        Update the 3D plot based on internal states.
        
        All computations of rotation use unit quaternion.
        
        '''
        
        self.ax3d.clear()

        if self.view_followdrill:
            azim, incl, roll = quat_to_euler(self.qc_sfus)
#            self.ax3d.view_init(azim=azim+90, elev=90-incl)
            self.ax3d.view_init(azim=2*90, elev=90-incl)

        ### Draw horizontal flow field 
        
        scale = 2
        ds = scale/4
        xy_ = np.arange(-scale+ds, scale, scale/2)
        x, y, z = np.meshgrid(xy_, xy_, -scale)
        r = scale/5
        for x0,y0 in zip(x.flatten(),y.flatten()):
            self.plot_vector(self.ax3d, x0+r*np.cos(flowang),y0+r*sin(flowang),-scale,  x0,y0,-scale,  style='-', color=c_lgray, lw=lw_default-2, arrow=True)

        i,j = -1,0
        dy = dx = scale/5
        self.ax3d.text(x[i,i][0]+0*dx,y[j,j][0]-1.4*dy,z[0,0][0], 'Ice flow', 'x', color=c_lgray, fontweight='bold', fontsize=FS-0.5)

        ### Draw orientation

        qi = Quaternion.identity()
        O = np.asarray((0, 0, 0)).reshape((3, 1))
        r = 2
        scale = 2

        # Plot the original XOY plane, plot the original axes.
        self.plot_circle(self.ax3d, qi, O, r, plane='xoy', style='-', color=c_dgray, method='q')
#        self.plot_xyz_axes(self.ax3d, qi, O, scale=scale, style='-', cx=cf, cy=cf, cz=cf, arrow=True, method='q')
#        self.plot_xyz_axes(self.ax3d, qi, O, scale=scale, style=':', cx=cx, cy=cy, cz=cz, arrow=False, method='q')

        # Plot the rotated axes.        
        if self.show_sfus: self.plot_circle(self.ax3d, self.q_sfus, O, r, plane='xoy', style='-', color=c_dred, method='q')
        if self.show_ahrs: self.plot_circle(self.ax3d, self.q_ahrs, O, r, plane='xoy', style='--', color=c_dred, method='q')
        if self.show_sfus: self.plot_xyz_axes(self.ax3d, self.q_sfus, O, scale=scale, style='-', cx=cx, cy=cy, cz=cz, arrow=True, method='q')
        if self.show_ahrs: self.plot_xyz_axes(self.ax3d, self.q_ahrs, O, scale=scale, style='--', cx=cx, cy=cy, cz=cz, arrow=True, method='q')

        # Trench frame
        lwc = lw_default-1
        self.plot_vector(self.ax3d, scale*1,0,0,  0,0,0,  style='-', color=cex, lw=lwc, arrow=True)
        self.plot_vector(self.ax3d, 0,scale*1,0,  0,0,0,  style='-', color=cey, lw=lwc, arrow=True)
        self.plot_vector(self.ax3d, 0,0,-scale*1,  0,0,0,  style='-', color=cez, lw=lwc, arrow=True)

        self.adjust_axes(self.ax3d, scale=scale)

        self.ax3d.legend(self.legend_lines, ['$+x$ axis: Trench parallel', '$+y$ axis: Trench perp.', '$-z$ axis: Plumb line', 'Drill axis (SFUS)', 'Spring direction (SFUS)', ], \
                            loc=2, bbox_to_anchor=(+0.05,1.01), ncol=1, fancybox=False, framealpha=1, frameon=True, edgecolor=frameec)


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

                self.ss.update()                    
                self.ds.update()

                #self.qc0_sfus = self.qc0_ahrs = Rotation.identity().as_quat()
                #self.qc_sfus = self.qc_ahrs = Rotation.identity().as_quat()

                self.qc0_sfus = self.ds.quat0_sfus
                self.qc0_ahrs = self.ds.quat0_ahrs
                self.qc_sfus = self.ds.quat_sfus
                self.qc_ahrs = self.ds.quat_ahrs

                self.drill_depth[nn] = -abs(self.ss.depth)
                self.drill_inclination_ahrs[nn] = self.ds.inclination_ahrs
                self.drill_inclination_sfus[nn] = self.ds.inclination_sfus
                self.drill_azimuth_ahrs[nn] = self.ds.azimuth_ahrs
                self.drill_azimuth_sfus[nn] = self.ds.azimuth_sfus
                self.drill_roll_ahrs[nn] = self.ds.roll_ahrs
                self.drill_roll_sfus[nn] = self.ds.roll_sfus
                nn += 1
                if nn > len(self.drill_depth)-1: nn = 0 # wrap around
                
                self.update_internal_states()
                self.update_ax3d_plot()
                self.update_axp_plot()

                self.text_calib.set_text('SFUS: (azim, incl, roll) = (%i, %.1f, %i)\nAHRS: (azim, incl, roll) = (%i, %.1f, %i)'%(self.ds.oricalib_sfus[0],self.ds.oricalib_sfus[1],self.ds.oricalib_sfus[2], self.ds.oricalib_ahrs[0],self.ds.oricalib_ahrs[1],self.ds.oricalib_ahrs[2]) )
               

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

