import sys, math, time
from math import copysign, fabs, sqrt, pi, sin, cos, asin, acos, atan2, exp, log
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d

from matplotlib.widgets import Slider, Button

from pyrotation import *

flowang = np.deg2rad(180 + 27)

c_lgreen = '#edf8e9'
c_dgreen = '#005a32'

c_lred = '#fee5d9'
c_dred = '#99000d'

c_lblue = '#eff3ff'
c_dblue = '#084594'

cx = c_dred
cy = c_dgreen
cz = c_dblue

lw_default = 3
alpha0 = 0.5

FS = 16
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
        
        ax.plot_surface(x, y, z, color=color, linewidth=0, alpha=alpha, antialiased=False)

    
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
        
        ticks = [-2,-1,0,1,2]
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.set_zticks(ticks)

        ax.set_xlim(-scale, scale)
        ax.set_ylim(-scale, scale)
        ax.set_zlim(-scale, scale/3)

        ax.set_xlabel('$x$', fontsize=FS+2)
        ax.set_ylabel('$y$', fontsize=FS+2)
        ax.set_zlabel('$z$', fontsize=FS+2)
        #ax.set_aspect('equal')

    def run(self):        

        #plt.ion()
        plt.show()
        #self.fig.canvas.draw()
        #self.fig.canvas.flush_events()

#        plt.show(False)
#        plt.draw()

        while True:
#            self.fig.canvas.draw()
#         
#            # This will run the GUI event
#            # loop until all UI events
#            # currently waiting have been processed
#            self.fig.canvas.flush_events()
            print('tick')
#            plt.show()
            time.sleep(1)
#            plt.draw()
#            self.s_ey.set_val( abs(np.random()*10) )

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
        
        self.reset_states()
        self.update_internal_states()
        self.setup_ui()

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
        
        self.euler_z_radian = self.euler_z_degree * np.pi / 180
        self.euler_y_radian = self.euler_y_degree * np.pi / 180
        self.euler_x_radian = self.euler_x_degree * np.pi / 180

        ### MY COORDINATE CHANGE
        self.euler_y_radian = np.pi/2 - self.euler_y_radian # elev -> incl
#        self.euler_z_radian = self.euler_z_radian - np.pi

        self.R = euler_zyx_to_rotation_matrix(self.euler_z_radian, self.euler_y_radian, self.euler_x_radian)


    def setup_ui(self):
        '''
        Set up the UI and the 3D plot.
        '''
        
        self.fig = plt.figure(figsize=(15, 10), facecolor='w', edgecolor='k')
#        plt.ion()
        self.ax3d = self.fig.add_axes([0.0, 0.0, 0.7, 1], projection='3d')
        self.ax3d.view_init(azim=70, elev=20)
        
        # set up control sliders
        
        x0, dy, y0 = 0.75, 0.05, 0.7
        dl, dh = 0.2, 0.03

        self.ax_ez = self.fig.add_axes([x0, y0+2*dy, dl, dh], facecolor=c_lblue)
        self.ax_ex = self.fig.add_axes([x0, y0+0*dy, dl, dh], facecolor=c_lred)
        self.ax_ey = self.fig.add_axes([x0, y0+1*dy, dl, dh], facecolor=c_lgreen)
        
        self.s_ez = Slider(self.ax_ez, r'Azimuth ($\alpha$)', -180, 180, valinit=self.euler_z_degree, color=c_dblue,  initcolor='k', valstep=1)
        self.s_ey = Slider(self.ax_ey, r'Inclination ($\beta$)', 0, 90,   valinit=self.euler_y_degree, color=c_dgreen, initcolor='k', valstep=0.1)
        self.s_ex = Slider(self.ax_ex, r'Roll ($\gamma$)', -180, 180,  valinit=self.euler_x_degree, color=c_dred,   initcolor='k', valstep=1)
         
        self.s_ez.on_changed(self.on_euler_angles_slider_update)
        self.s_ey.on_changed(self.on_euler_angles_slider_update)
        self.s_ex.on_changed(self.on_euler_angles_slider_update)

        
        ### Description
        kwargs_text = {'fontsize':FS-1, 'transform':plt.gcf().transFigure}
        
        x0 = 0.67
        y0 = 0.40
        dy = 0.035
        plt.text(x0, y0+1*dy, '------------ Coordinate system ------------', **kwargs_text)
        plt.text(x0, y0-0*dy, '$\\rightarrow$ Red arrow is direction of drill', **kwargs_text)
        plt.text(x0, y0-1*dy, '$\\rightarrow$ Green arrow is direction of spring', **kwargs_text)
        plt.text(x0, y0-2*dy, '$\\rightarrow$ $+x$ axis is along tower when horizontal', **kwargs_text)

        ### View buttons

        y0 = 0.3
        dy = 0.05
        x0_bot =  0.67
        dl_bot = 0.1
        plt.text(x0_bot, y0-1*dy, '------------ Change view ------------', **kwargs_text)
        axv_reset   = self.fig.add_axes([x0_bot+0.05*dl_bot, y0-2*dy, dl_bot, dh])
        axv_topdown = self.fig.add_axes([x0_bot+1.2*dl_bot, y0-2*dy, dl_bot, dh])
        bv_reset   = Button(axv_reset, 'Reset')
        bv_topdown = Button(axv_topdown, 'Top-down')
        bv_reset.on_clicked(self.view_reset)
        bv_topdown.on_clicked(self.view_topdown)
        plt.bv_reset   = bv_reset
        plt.bv_topdown = bv_topdown
        
        self.update_ax3d_plot()
        
    def view_reset(self, *args, **kwargs):
        print('view reset')
        self.ax3d.view_init(azim=70, elev=20)
        plt.draw()
        
    def view_topdown(self, *args, **kwargs):
        print('view top-down')
        self.ax3d.view_init(azim=90, elev=90)
        plt.draw()
        
    def update_ax3d_plot(self):
        '''
        Update the 3D plot based on internal states.
        All computations of rotation use rotation matrix.
        '''
        
        self.ax3d.clear()

        # horizontal flow field 
        scale = 2
        ds = scale/4
        xy_ = np.arange(-scale+ds, scale, scale/2)
        x, y, z = np.meshgrid(xy_, xy_, -scale)
        u = z*0 + np.cos(flowang)
        v = z*0 + np.sin(flowang)
        w = z*0 + 1e-2
        self.ax3d.quiver(x, y, z, u, v, w, length=0.45, lw=2.5, color='0.5', arrow_length_ratio=0.3, zorder=10)

        ###

        I = np.identity(3)
        r = 2
        scale = 2
        O = np.asarray((0, 0, 0)).reshape((3, 1))
        
        R = self.R

        # Calculate x-axis and y-axis after the yaw rotation. This is needed
        # to plot the pitch angle.
        Rz = euler_zyx_to_rotation_matrix(self.euler_z_radian, 0, 0)
        nx = np.asarray((r, 0, 0)).reshape((3, 1))
        nx = np.matmul(Rz, nx).flatten()
        ny = np.asarray((0, r, 0)).reshape((3, 1))
        ny = np.matmul(Rz, ny).flatten()

        # Calculate z-axis after the yaw rotation and the pitch rotation.
        # This is needed to plot the pitch angle.
        Rzy = euler_zyx_to_rotation_matrix(self.euler_z_radian, self.euler_y_radian, 0)
        mz = np.asarray((0, 0, r)).reshape((3, 1))
        mz = np.matmul(Rzy, mz).flatten()

        # Plot the original XOY plane.
#        self.plot_disk(self.ax3d, I, O, r, plane='xoy', color='w')
        self.plot_circle(self.ax3d, I, O, r, plane='xoy', style=':', color='k')
                
        # ---------- yaw -----------------
        
        # Plot the yaw angle
        self.plot_arc(self.ax3d, 0, self.euler_z_radian, I, O, r, style='-', color=c_dblue, arrow=True)        

        # ---------- pitch -----------------
        
        # Plot the pitch angle on the ZOX plane after the yaw rotation.
#        self.plot_arc(self.ax3d, np.pi/2, self.euler_y_radian, Rz, O, r, plane='zox', style='-', color=c_dgreen, arrow=True) # old for elev
        self.plot_arc(self.ax3d, np.pi, self.euler_y_radian-np.pi/2, Rz, O, r, plane='zox', style='-', color=c_dgreen, arrow=True) # new for incl.
        
        # Plot x-axis and y-axis after the yaw rotation.
        #self.plot_vector(self.ax3d, nx[0], nx[1], nx[2], style=':', color=c_dred)
        #self.plot_vector(self.ax3d, ny[0], ny[1], ny[2], style=':', color=c_dgreen)


        # ---------- roll -----------------
        
        # Plot the roll angle on the YOZ plane after yaw and pitch.
#        self.plot_disk(self.ax3d, R, O, r, plane='yoz', color='r') 
        self.plot_circle(self.ax3d, R, O, r, plane='yoz', style='-', color='k')
        self.plot_arc(self.ax3d, 0, self.euler_x_radian, Rzy, O, r, plane='yoz', style='-', color=c_dred, arrow=True)

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
        self.euler_y_degree = self.s_ey.val ### TODO
        self.euler_x_degree = self.s_ex.val
        
        self.update_internal_states()
        self.update_ax3d_plot()
        


if __name__ == '__main__':
    
    vis = EulerZYXVisualizer3D()
    vis.run()
    pass

