#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2023

import code # code.interact(local=locals())

import sys, math, time
from math import copysign, fabs, sqrt, pi, sin, cos, asin, acos, atan2, exp, log
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d
from matplotlib.widgets import Slider, Button, CheckButtons

from settings import *
from state_drill import *

from pyrotation import *

#flowang = np.deg2rad(180 + 27)
flowang = np.deg2rad(27)

c_green  = '#74c476'
c_lgreen = '#edf8e9'
c_dgreen = '#238b45'

c_red  = '#fb6a4a'
c_lred = '#fee5d9'
c_dred = '#cb181d'

c_blue  = '#6baed6'
c_lblue = '#eff3ff'
c_dblue = '#2171b5'

cy = c_dgreen
cx = c_dred
cz = c_dblue
cx,cz = cz,cx

lw_default = 4
alpha0 = 0.09

FS = 17
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

##############################################################################################            
##############################################################################################
##############################################################################################


class QuaternionVisualizer3D(RotationVisualizer3D):
    '''
    This class demonstrates 3D rotation in the unit quaternion representation
    with a 3D plot.
    '''

    def __init__(self):
        '''
        Constructor.
        '''

        self.drill_sync = True

        self.reset_states()
        self.update_internal_states()
        self.setup_ui()
        

    def reset_states(self):
        '''
        Reset to the inital states, where no rotation is applied.
        '''

        # Quat coordinates (x,y,z,w)
        self.qc      = [0,0,0,1]
        self.qc_ahrs = [0,0,0,1]
        
        # Calibration quat 
        self.qc_calib = Rotation.identity().as_quat()
        
        # Euler angles
        self.incl, self.azim = 0, 0


    def update_internal_states(self):
        '''
        Converting the values read from the sliders to internal states.
        Internally, a unit quaternion is used for calculation and plot.
        '''
        
        # Uncalibrated
        q_      = Rotation.from_quat(self.qc)
        q_ahrs_ = Rotation.from_quat(self.qc_ahrs)

        # Calibrated        
        q_calib = Rotation.from_quat(self.qc_calib)
        q       = q_     *q_calib
        q_ahrs  = q_ahrs_*q_calib
        
        # pyrotation Quaternion() objects
        self.q      = Quaternion(*self.xyzw_to_wxyz(q.as_quat()))
        self.q_ahrs = Quaternion(*self.xyzw_to_wxyz(q_ahrs.as_quat()))
        
    # copy from state_drill.py
    def xyzw_to_wxyz(self, q): return np.roll(q,1)
    def wxyz_to_xyzw(self, q): return np.roll(q,-1)
    
        
    def setup_ui(self):
        '''
        Set up the UI and the 3D plot.
        '''

        self.fig = plt.figure(10, figsize=(17, 10), facecolor='w', edgecolor='k')
        plt.get_current_fig_manager().set_window_title('Drill orientation')
        self.ax3d = self.fig.add_axes([0.0, 0.0, 0.85, 1], projection='3d')
        self.ax3d.view_init(azim=70+180, elev=30)
        
        ### Shared below 
        
        kwargs_text = {'fontsize':FS-1, 'transform':plt.gcf().transFigure}
        
        y0 = 0.85
        x0 = 0.74 # title string start
        x1 = x0+0.01 # box contet start (adjusted inward slightly)
        
        dy = 0.06 # vertical distance between rows of buttons
        dyt = 0.07 # delta y from title string to box content
        
        dl = 0.1 # botton width
        dh = 0.04 # button height

        self.ax_fake = self.fig.add_axes([x1, y0, dl, dh])
        self.ax_fake.axis('off')

        ### Orientation

        plt.text(x0, y0, '----- Orientation -----', fontweight='bold', **kwargs_text)        
        dy_ = 0.8*dy
        self.text_incl = plt.text(x1, y0-1*dy_, r'', **kwargs_text)
        self.text_azim = plt.text(x1, y0-1.8*dy_, r'', **kwargs_text)
                
                
        ### Calibrate/offset 

        y0 = y0-0.17

        plt.text(x0, y0, '----- Calibrate -----', fontweight='bold', **kwargs_text)        
        dl_ = dl*1.7
        ax_calib      = self.fig.add_axes([x1, y0-dyt-0*dy, dl_, dh])
        ax_calib_ahrs = self.fig.add_axes([x1, y0-dyt-1*dy, dl_, dh])
        ax_uncalib    = self.fig.add_axes([x1, y0-dyt-2*dy, dl_, dh])
        b_calib      = Button(ax_calib, r'Calibrate SFUSION')
        b_calib_ahrs = Button(ax_calib_ahrs, r'Calibrate AHRS')
        b_uncalib    = Button(ax_uncalib, r'Remove calibration')
        b_calib.on_clicked(self.set_calibrate)
        b_calib_ahrs.on_clicked(self.set_calibrate_ahrs)
        b_uncalib.on_clicked(self.set_uncalibrate)
        plt.b_calib = b_calib
        plt.b_calib_ahrs = b_calib_ahrs
        plt.b_uncalib = b_uncalib
        
        plt.text(x0, y0-4*dy, 'Calibration quaternion:', **kwargs_text)     
        self.text_calib = plt.text(x0, y0-4.5*dy, '', **kwargs_text)     
        

        ### View buttons

        y0 = y0-0.34
        
        plt.text(x0, y0, '----- Change view -----', fontweight='bold', **kwargs_text)
        axv_sideways = self.fig.add_axes([x1, y0-dyt-0*dy, dl, dh])
        axv_topdown  = self.fig.add_axes([x1, y0-dyt-1*dy, dl, dh])
        bv_sideways = Button(axv_sideways, 'Sideways')
        bv_topdown  = Button(axv_topdown, 'Top-down')
        bv_sideways.on_clicked(self.view_sideways)
        bv_topdown.on_clicked(self.view_topdown)
        plt.bv_sideways = bv_sideways
        plt.bv_topdown  = bv_topdown
        
        self.update_ax3d_plot()


    def view_sideways(self, *args, **kwargs):
        print('View = sideways')
        self.ax3d.view_init(azim=70+180, elev=30)
        plt.draw()
        
        
    def view_topdown(self, *args, **kwargs):
        print('View = top-down')
        self.ax3d.view_init(azim=90-180, elev=90)
        plt.draw()
        
        
    def set_calibrate(self, *args, **kwargs):
        print('Calibrating quaternion (SFUSION) to vertical frame')
        self.qc_calib = self.get_qc_calib(self.qc)
            
    def set_calibrate_ahrs(self, *args, **kwargs):
        print('Calibrating quaternion (AHRS) to vertical frame')
        self.qc_calib = self.get_qc_calib(self.qc_ahrs)

    def get_qc_calib(self, qc):
        E = -np.eye(3)
        M = Rotation.from_quat(qc).as_matrix()
        q_calib, _  = Rotation.align_vectors(M[[1,0,2],:],E[[0,1,2],:])
        qc_calib = q_calib.as_quat()
        return qc_calib

    def set_uncalibrate(self, *args, **kwargs):
        print('Removing calibration')
        self.qc_calib = Rotation.identity().as_quat()


    def update_ax3d_plot(self):
        '''
        Update the 3D plot based on internal states.
        
        All computations of rotation use unit quaternion.
        
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

        ### Draw orientation

        qi = Quaternion.identity()
        O = np.asarray((0, 0, 0)).reshape((3, 1))
        r = 2
        scale = 2

        u = self.q.to_angle_axis()

        # Plot the original XOY plane.

        # Plot the original axes.
        cf = '0.4'
        self.plot_circle(self.ax3d, qi, O, r, plane='xoy', style='-', color=cf, method='q')
        self.plot_xyz_axes(self.ax3d, qi, O, scale=scale, style='-', cx=cf, cy=cf, cz=cf, arrow=True, method='q')
#        self.plot_xyz_axes(self.ax3d, qi, O, scale=scale, style=':', cx=cx, cy=cy, cz=cz, arrow=False, method='q')

        # Plot the rotated axes.        
        self.plot_circle(self.ax3d, self.q,      O, r, plane='xoy', style='-', color=c_dred, method='q')
        self.plot_circle(self.ax3d, self.q_ahrs, O, r, plane='xoy', style='--', color=c_dred, method='q')
        self.plot_xyz_axes(self.ax3d, self.q, O, scale=scale, style='-', cx=cx, cy=cy, cz=cz, arrow=True, method='q')
        self.plot_xyz_axes(self.ax3d, self.q_ahrs, O, scale=scale, style='--', cx=cx, cy=cy, cz=cz, arrow=True, method='q')

        # Plot the rotation axis
        #self.plot_vector(self.ax3d, u[0], u[1], u[2], arrow=True)

        # Calib axes
        lwc = lw_default-1.5
        self.plot_vector(self.ax3d, -scale*1,0,0,  0,0,0,  style='-', color=c_green, lw=lwc, arrow=True)
        self.plot_vector(self.ax3d, 0,-scale*1,0,  0,0,0,  style='-', color=c_blue, lw=lwc, arrow=True)
        self.plot_vector(self.ax3d, 0,0,-scale*1,  0,0,0,  style='-', color=c_red, lw=lwc, arrow=True)

        self.adjust_axes(self.ax3d, scale=scale)

        from matplotlib.lines import Line2D
        custom_lines = [Line2D([0], [0], color=c_dred, ls='-', lw=lw_default), \
                        Line2D([0], [0], color=c_dred, ls='--', lw=lw_default), \
                        Line2D([0], [0], color=c_dblue, ls='-', lw=lw_default), \
                        Line2D([0], [0], color=c_dblue, ls='--', lw=lw_default)]
                        
        self.ax3d.legend(custom_lines, ['Drill axis (SFUSION)', 'Drill axis (AHRS)', 'Spring direction (SFUSION)', 'Spring direction (AHRS)'], loc=2, bbox_to_anchor=(-0.18,0.97), fancybox=False)




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
                self.qc      = ds.quat
                self.qc_ahrs = ds.quat_ahrs
                self.update_internal_states()

                self.update_ax3d_plot()

                self.text_incl.set_text(r'Inclination = %+.2f'%(self.incl))
                self.text_azim.set_text(r'Azimuth    = %+.2f'%(self.azim))
                self.text_calib.set_text(r'(x,y,z,w) = (%.2f, %.2f, %.2f, %.2f)'%(self.qc_calib[0],self.qc_calib[1],self.qc_calib[2],self.qc_calib[3]))     
            
            if debug: print('Tick dt=%.2f'%(dt))


##############################################################################################            
##############################################################################################
##############################################################################################

if __name__ == '__main__':

    plt.ion()
    vis = QuaternionVisualizer3D()
    vis.run(REDIS_HOST=REDIS_HOST, debug=False)
    pass

