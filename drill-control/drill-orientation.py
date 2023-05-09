#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2023

import sys, math, time
from math import copysign, fabs, sqrt, pi, sin, cos, asin, acos, atan2, exp, log
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d
from matplotlib.widgets import Slider, Button, CheckButtons

from pyrotation import *
from settings import *
from state_drill import *

flowang = np.deg2rad(180 + 27)

c_green  = '#74c476'
c_lgreen = '#edf8e9'
c_dgreen = '#238b45'

c_red  = '#fb6a4a'
c_lred = '#fee5d9'
c_dred = '#cb181d'

c_blue  = '#6baed6'
c_lblue = '#eff3ff'
c_dblue = '#2171b5'

cx = c_dred
cy = c_dgreen
cz = c_dblue

lw_default = 4
alpha0 = 0.09

FS = 17
matplotlib.rcParams.update({'font.size': FS})


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

            

class EulerZYXVisualizer3D(RotationVisualizer3D):
    '''
    This class demonstrates 3D rotation in the Euler angle representation in
    z-y'-x" (intrinsic) convention with a 3D plot.
    
    The user can control the three angles with sliders.
    '''

    def __init__(self):
        '''
        Constructor.
        '''

        # RAW instrument values
        self.azim = 0
        self.incl = 0
        self.roll = 0
    
        # Offsets for true values
        self.offset_roll = 0
        self.offset_azim = 0
        self.offset_incl = 0
                
        self.reset_states()
        self.update_internal_states()
        self.setup_ui()
        self.drill_sync = True


    def reset_states(self):
        '''
        Reset to the initial states, where all three angles are zero, i.e.,
        no rotation.
        '''
        
        self.euler_z_degree = 0
        self.euler_y_degree = 0
        self.euler_x_degree = 0
        

    def update_internal_states(self):
        '''
        Converting angle states read from the sliders to internal states
        (i.e., angles in radian, etc.).
        
        Internally, a rotation matrix is used for calculation and plot.
        '''
        
        self.euler_z_radian = np.deg2rad(self.euler_z_degree)
        self.euler_y_radian = np.deg2rad(self.euler_y_degree)
        self.euler_x_radian = np.deg2rad(self.euler_x_degree)

        ### MY COORDINATE CHANGE
        self.euler_y_radian = np.pi/2 - self.euler_y_radian # elev -> incl
#        self.euler_z_radian = self.euler_z_radian - np.pi

        self.R = euler_zyx_to_rotation_matrix(self.euler_z_radian, self.euler_y_radian, self.euler_x_radian)


    def setup_ui(self):
        '''
        Set up the UI and the 3D plot.
        '''
        
        self.fig = plt.figure(10, figsize=(20, 10), facecolor='w', edgecolor='k')
        plt.get_current_fig_manager().set_window_title('Drill orientation')
        self.ax3d = self.fig.add_axes([0.0, 0.0, 0.7, 1], projection='3d')
        self.ax3d.view_init(azim=70, elev=20)
        
        ### set up control sliders
        
        y0 = 0.90
        
        x0, dy = 0.74, 0.05
        dl, dh = 0.2, 0.03

        self.ax_ez = self.fig.add_axes([x0, y0-0*dy, dl, dh], facecolor=c_lblue)
        self.ax_ex = self.fig.add_axes([x0, y0-2*dy, dl, dh], facecolor=c_lred)
        self.ax_ey = self.fig.add_axes([x0, y0-1*dy, dl, dh], facecolor=c_lgreen)
        
        self.s_ez = Slider(self.ax_ez, r'Azimuth ($\alpha$)', -180, 180, valinit=self.euler_z_degree, color=c_dblue,  initcolor='k', valstep=1)
        self.s_ey = Slider(self.ax_ey, r'Inclination ($\beta$)', 0, 90,   valinit=self.euler_y_degree, color=c_dgreen, initcolor='k', valstep=0.1)
        self.s_ex = Slider(self.ax_ex, r'Roll ($\gamma$)', -180, 180,  valinit=self.euler_x_degree, color=c_dred,   initcolor='k', valstep=1)

        self.s_ez.on_changed(self.on_euler_angles_slider_update)
        self.s_ey.on_changed(self.on_euler_angles_slider_update)
        self.s_ex.on_changed(self.on_euler_angles_slider_update)
                 
        kwargs_text = {'fontsize':FS-1, 'transform':plt.gcf().transFigure}
        x0_ = 0.94*x0
        y0_ = y0-3.2*dy
        self.text_islive = plt.text(x0_, y0_, r'Drills is offline', color=c_dred, fontweight='bold', **kwargs_text)
        axsync = self.fig.add_axes([x0_ + 0.66*dl, 0.99*y0_, 0.13, dh])
        self.b_sync = Button(axsync, 'Disable sync')
        self.b_sync.on_clicked(self.sync_onoff)
        plt.b_sync = self.b_sync

        ### Shared below 
        
        x0 = 0.69 # title string start
        x1 = x0+0.01 # box contet start (adjusted inward slightly)
        dyt = 0.06 # delta y from title string to box content
        dl = 0.1 # botton width
        dy = 0.05 # vertical distance between rows of buttons
                
                
        ### Calibrate/offset 

        y0 = y0-0.24
        plt.text(x0, y0, '------------ Offset reference frame ------------', **kwargs_text)
        axf_azero  = self.fig.add_axes([x1, y0-dyt-0*dy, dl, dh])
        axf_bzero  = self.fig.add_axes([x1, y0-dyt-1*dy, dl, dh])
        axf_gzero  = self.fig.add_axes([x1, y0-dyt-2*dy, dl, dh])
        axf_clear  = self.fig.add_axes([x1, y0-dyt-3*dy, dl, dh])
        bf_azero  = Button(axf_azero, r'Zero $\alpha$')
        bf_bzero  = Button(axf_bzero, r'Zero $\beta$')
        bf_gzero  = Button(axf_gzero, r'Zero $\gamma$')
        bf_clear  = Button(axf_clear, 'Clear')
        bf_azero.on_clicked(self.offset_alpha)
        bf_bzero.on_clicked(self.offset_beta)
        bf_gzero.on_clicked(self.offset_gamma)
        bf_clear.on_clicked(self.clear_offsets)
        plt.bf_azero = bf_azero
        plt.bf_bzero = bf_bzero
        plt.bf_gzero = bf_gzero
        plt.bf_clear = bf_clear
        
        dy_ = 0.85*dy
        self.text_alpha = plt.text(x0+1.5*dl, y0-1*dy, r'$\alpha = \alpha_{raw} - %.2f$'%(self.offset_azim), **kwargs_text)
        self.text_beta  = plt.text(x0+1.5*dl, y0-2*dy, r'$\beta  = \beta_{raw} - %.2f$'%(self.offset_incl), **kwargs_text)
        self.text_gamma = plt.text(x0+1.5*dl, y0-3*dy, r'$\gamma = \gamma_{raw} - %.2f$'%(self.offset_roll), **kwargs_text)
        
        ### View buttons

        y0 = y0-0.28
        plt.text(x0, y0, '------------ Change view ------------', **kwargs_text)
        axv_sideways = self.fig.add_axes([x1, y0-dyt-0*dy, dl, dh])
        axv_topdown  = self.fig.add_axes([x1, y0-dyt-1*dy, dl, dh])
        bv_sideways = Button(axv_sideways, 'Sideways')
        bv_topdown  = Button(axv_topdown, 'Top-down')
        bv_sideways.on_clicked(self.view_sideways)
        bv_topdown.on_clicked(self.view_topdown)
        plt.bv_sideways = bv_sideways
        plt.bv_topdown  = bv_topdown
        
        ### Description

        y0 = y0-0.19
        dyt_alt = 0.04        
        dys = 0.035
        plt.text(x0, y0, '------------ Coordinate system ------------', **kwargs_text)
        plt.text(x1, y0-dyt_alt-0*dys, '$\\rightarrow$ Red arrow is direction of drill', color=c_dred, **kwargs_text)
        plt.text(x1, y0-dyt_alt-1*dys, '$\\rightarrow$ Green arrow is direction of spring', color=c_dgreen, **kwargs_text)
        plt.text(x1, y0-dyt_alt-2*dys, '$\\rightarrow$ $+x$ axis is along tower when horizontal', **kwargs_text)
        plt.text(x1, y0-dyt_alt-3*dys, '$\\rightarrow$ Angle betw. tower and flow is %i deg.'%(np.rad2deg(flowang)), **kwargs_text)

        self.update_ax3d_plot()
           
        
    def view_sideways(self, *args, **kwargs):
        print('View = sideways')
        self.ax3d.view_init(azim=70, elev=20)
        plt.draw()
        
    def view_topdown(self, *args, **kwargs):
        print('View = top-down')
        self.ax3d.view_init(azim=90, elev=90)
        plt.draw()
        
    def offset_alpha(self, *args, **kwargs):
        print('Setting alpha offset')
        self.offset_azim = self.s_ez.val
        
    def offset_beta(self, *args, **kwargs):
        print('Setting beta offset')
        self.offset_incl = self.s_ey.val
        
    def offset_gamma(self, *args, **kwargs):
        print('Setting gamma offset')
        self.offset_roll = self.s_ex.val
        
    def clear_offsets(self, *args, **kwargs):
        print('Clearing reference-frame offset')
        self.offset_azim = 0
        self.offset_roll = 0
        
    def sync_onoff(self, *args, **kwargs):
        print('Toggle drill synchronization')
        self.drill_sync = not self.drill_sync
        self.b_sync.label.set_text('Disable sync' if self.drill_sync else 'Enable sync')
        
    def update_ax3d_plot(self):
        '''
        Update the 3D plot based on internal states.
        All computations of rotation use rotation matrix.
        '''
        
        self.ax3d.clear()

        ### Draw horizontal flow field 
        
        scale = 2
        ds = scale/4
        xy_ = np.arange(-scale+ds, scale, scale/2)
        x, y, z = np.meshgrid(xy_, xy_, -scale)
        u = z*0 + np.cos(flowang)
        v = z*0 + np.sin(flowang)
        w = z*0 #+ 1e-2
        self.ax3d.quiver(x,y,z, u,v,w, length=0.45, lw=2.5, color='0.5', arrow_length_ratio=0.5, zorder=10)

        ### Draw gibmal geometry

        I = np.identity(3)
        r = 2
        scale = 2
        O = np.asarray((0, 0, 0)).reshape((3, 1))
        
        R = self.R

        # Calculate x-axis and y-axis after the yaw rotation. This is needed to plot the pitch angle.
        Rz = euler_zyx_to_rotation_matrix(self.euler_z_radian, 0, 0)
        nx = np.asarray((r, 0, 0)).reshape((3, 1))
        nx = np.matmul(Rz, nx).flatten()
        ny = np.asarray((0, r, 0)).reshape((3, 1))
        ny = np.matmul(Rz, ny).flatten()

        # Calculate z-axis after the yaw rotation and the pitch rotation. This is needed to plot the pitch angle.
        Rzy = euler_zyx_to_rotation_matrix(self.euler_z_radian, self.euler_y_radian, 0)
        mz = np.asarray((0, 0, r)).reshape((3, 1))
        mz = np.matmul(Rzy, mz).flatten()

        # Plot the original XOY plane.
#        self.plot_disk(self.ax3d, I, O, r, plane='xoy', color='w')
        self.plot_circle(self.ax3d, I, O, r, plane='xoy', style=':', color='k')
                
        # --- yaw ---
        
        # Plot the yaw angle
        self.plot_arc(self.ax3d, 0, self.euler_z_radian, I, O, r, style='--', color=c_blue, arrow=True)        

        # --- pitch ---
        
        # Plot the pitch angle on the ZOX plane after the yaw rotation.
#        self.plot_arc(self.ax3d, np.pi/2, self.euler_y_radian, Rz, O, r, plane='zox', style='-', color=c_dgreen, arrow=True) # old for elev
        self.plot_arc(self.ax3d, np.pi, self.euler_y_radian-np.pi/2, Rz, O, r, plane='zox', style='--', color=c_green, arrow=True) # new for incl.
        
        # Plot x-axis and y-axis after the yaw rotation.
        #self.plot_vector(self.ax3d, nx[0], nx[1], nx[2], style=':', color=c_dred)
        #self.plot_vector(self.ax3d, ny[0], ny[1], ny[2], style=':', color=c_dgreen)


        # --- roll ---
        
        # Plot the roll angle on the YOZ plane after yaw and pitch.
#        self.plot_disk(self.ax3d, R, O, r, plane='yoz', color='0.5') 
        self.plot_circle(self.ax3d, R, O, r, plane='yoz', style='-', color='k')
        self.plot_arc(self.ax3d, 0, self.euler_x_radian, Rzy, O, r, plane='yoz', style='--', color=c_red, arrow=True)

        # Plot z-axis after the yaw rotation and the pitch rotation.
        #self.plot_vector(self.ax3d, mz[0], mz[1], mz[2], style=':', color=c_dblue)

        # Plot the original axes.
        c_ = '0.3'
        I_ = I # upward-pointing z axis
        I_ = np.diag([1,1,-1]) # downward-pointing z axis
        self.plot_xyz_axes(self.ax3d, I_, O, scale=scale, style='-', cx=c_, cy=c_, cz=c_, arrow=True)
#        self.plot_xyz_axes(self.ax3d, I, O, scale=scale, style='--', cx='r', cy='g', cz='b', arrow=False)

        # Plot the rotated reference frame.
        self.plot_xyz_axes(self.ax3d, R, O, scale=2, arrow=True)
        
        self.adjust_axes(self.ax3d, scale=scale)
        

    def on_euler_angles_slider_update(self, val):
        '''
        Event handler of the sliders.
        '''
        
        del val
        
        self.euler_z_degree = self.s_ez.val
        self.euler_y_degree = self.s_ey.val
        self.euler_x_degree = self.s_ex.val
        
        self.update_internal_states()
        self.update_ax3d_plot()
        


    def run(self, dt=0.5, debug=False, REDIS_HOST=REDIS_HOST):

        ds = DrillState(redis_host=REDIS_HOST)   

        while True:

            fignums = plt.get_fignums()
            if len(fignums)==0 or fignums[0] != 10: sys.exit('Figure closed. Exiting.')

            # Let GUI event loop run for this amount before exiting and updating orientation state.
            # This is similar to plt.pause(dt), but does not steal focus on every update.
            plt.gcf().canvas.draw_idle()
            plt.gcf().canvas.start_event_loop(dt)


            if self.drill_sync:
                
                ds.update()
                self.azim = ds.azimuth     # euler_z_degree
                self.incl = ds.inclination # euler_y_degree
                self.roll = ds.roll        # euler_x_degree
                euler_z_degree = self.azim - self.offset_azim
                euler_y_degree = self.incl - self.offset_incl
                euler_x_degree = self.roll - self.offset_roll

                if debug:
                    euler_z_degree = abs(np.random.random())*30
                    euler_y_degree = abs(np.random.random())*30
                    euler_x_degree = abs(np.random.random())*30

    #            else:
    #                euler_z_degree = self.euler_z_degree
    #                euler_y_degree = self.euler_y_degree
    #                euler_x_degree = self.euler_x_degree

                self.s_ez.set_val(euler_z_degree)
                self.s_ey.set_val(euler_y_degree)
                self.s_ex.set_val(euler_x_degree)

                self.on_euler_angles_slider_update(0)

            self.text_alpha.set_text(r'$\alpha = \alpha_{raw} %+.2f$'%(self.offset_azim))
            self.text_beta.set_text(r'$\beta = \beta_{raw} %+.2f$'%(self.offset_incl))
            self.text_gamma.set_text(r'$\gamma = \gamma_{raw} %+.2f$'%(self.offset_roll))
            
            self.text_islive.set_text(r'Drill is %s'%('online' if ds.islive else 'offline'))
            self.text_islive.set_color(c_dgreen if ds.islive else c_dred)
            
            if debug: print('Tick dt=%.2f'%(dt))


if __name__ == '__main__':

    plt.ion()
    vis = EulerZYXVisualizer3D()
    vis.run(REDIS_HOST=REDIS_HOST, debug=False)
    pass

