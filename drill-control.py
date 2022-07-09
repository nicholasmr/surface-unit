# N. Rathmann <rathmann@nbi.dk>, 2019-2022

import sys, os, signal, datetime
import numpy as np

from settings import *
from state_drill import *
from state_surface import *

from PyQt5.QtCore import * 
from PyQt5.QtWidgets import * 
import pyqtgraph as pg

#-------------------
# Settings
#-------------------

DT           = 1/8 # update rate in seconds for GUI/surface state
DTFRAC_DRILL = 4 # update the drill state every DTFRAC_DRILL times the GUI/surface state is updated
XAXISLEN     = 30 + 1 # seconds

SHOW_BNO055_DETAILED = 1

FS = 13
FS_GRAPH_TITLE = 4 # font size for graph titles
PATH_SCREENSHOT = "/mnt/logs/screenshots"

# Print settings
print('%s: running with DT=%.3fs, DT_DRILL=%.3fs (DTFRAC_DRILL=%i), XAXISLEN=%is'%(sys.argv[0],DT,DT*DTFRAC_DRILL,DTFRAC_DRILL,XAXISLEN))
print('Using BNO055 for orientation? %s'%('Yes' if USE_BNO055_FOR_ORIENTATION else 'No'))
print('Showing detailed BNO055 output? %s'%('Yes' if SHOW_BNO055_DETAILED else 'No'))

# GUI colors
COLOR_GREEN = '#66bd63'
COLOR_RED   = '#f46d43'
COLOR_BLUE  = '#3182bd'

#-------------------
# Program start
#-------------------

class MainWidget(QWidget):

    runtime0 = None
    Nt = 0 # number of time steps taken

    def __init__(self, parent=None):
    
        super(MainWidget, self).__init__(parent)

        ### State objects

        # REDIS_HOST determined in settings file
        self.ds = DrillState(  redis_host=REDIS_HOST)   
        self.ss = SurfaceState(redis_host=REDIS_HOST)

        ### pyqt graphs

        pg.setConfigOptions(background='f0f0f0') # gray
        pg.setConfigOptions(foreground='k')

        # X-axis
        self.hist_time       = np.flipud(np.arange(0,XAXISLEN+1e-9,DT))
        self.hist_time_drill = np.flipud(np.arange(0,XAXISLEN+1e-9,DT*DTFRAC_DRILL))
        self.hist_load     = np.full(len(self.hist_time), 0.0)
        self.hist_loadtare = np.full(len(self.hist_time), 0.0)
        self.hist_speed    = np.full(len(self.hist_time), 0.0)
        self.hist_current  = np.full(len(self.hist_time_drill), 0.0)

        def setupaxis(obj):
            obj.invertX()
            obj.setXRange(0, XAXISLEN, padding=0)
            obj.showAxis('right')
            obj.showAxis('top')        

        # Plots
        self.plot_load    = pg.PlotWidget(); 
        self.plot_speed   = pg.PlotWidget(); 
        self.plot_current = pg.PlotWidget(); 
        setupaxis(self.plot_load);
        setupaxis(self.plot_speed);
        setupaxis(self.plot_current);
        self.plot_load.setMenuEnabled(False)
        self.plot_speed.setMenuEnabled(False)
        self.plot_current.setMenuEnabled(False)
        self.plot_load.setMouseEnabled(x=False, y=False)
        self.plot_speed.setMouseEnabled(x=False, y=False)
        self.plot_current.setMouseEnabled(x=False, y=False)
    
        # init curves
        lw = 3
        plotpen_black = pg.mkPen(color='k', width=lw)
        plotpen_blue  = pg.mkPen(color=COLOR_BLUE, width=lw-1)
        self.curve_load     = self.plot_load.plot(    x=self.hist_time,y=self.hist_time*0-1e4, pen=plotpen_black)
        self.curve_speed    = self.plot_speed.plot(   x=self.hist_time,y=self.hist_time*0-1e4, pen=plotpen_black)
        self.curve_current  = self.plot_current.plot( x=self.hist_time_drill,y=self.hist_time_drill*0-1e4, pen=plotpen_black)
        
        # Titles
        # set in update() if also writing current value in title
#        self.plot_load.setTitle(self.htmlfont('<b>Load (kg)', FS_GRAPH_TITLE)) 
#        self.plot_speed.setTitle(self.htmlfont('<b>Speed (cm/s)', FS_GRAPH_TITLE))        
#        self.plot_current.setTitle(self.htmlfont('<b>Current (A)', FS_GRAPH_TITLE))

        def setAxisTicksEtc(obj):
                obj.setLabel('right', "&nbsp;") # hacky way of adding spacing between graphs
                obj.setLabel('bottom', "Seconds ago")
                obj.showGrid(y=True,x=True)
                obj.getAxis('left').setGrid(False)
                obj.getAxis('bottom').setGrid(False)
                for ax in ['left', 'top']:
                    obj.showAxis(ax)
                    obj.getAxis(ax).setStyle(showValues=False)


        setAxisTicksEtc(self.plot_load)
        setAxisTicksEtc(self.plot_speed)                
        setAxisTicksEtc(self.plot_current)

        ### State fields

        self.create_gb_surface()
        self.create_gb_orientation()
        self.create_gb_temperature()
        self.create_gb_pressure()
        self.create_gb_motor()
        self.create_gb_expert()
        self.create_gb_run()

        ### QT Layout

        # Graphs (top)
        topLayout = QHBoxLayout()
        topLayout.addWidget(self.plot_speed, 1)
        topLayout.addWidget(self.plot_load, 2)
        topLayout.addWidget(self.plot_current, 1)
        
        # State fields (bottom)
        botLayout = QHBoxLayout()
        botLayout.addWidget(self.gb_surface)
        botLayout.addWidget(self.gb_orientation)
        botLayout.addWidget(self.gb_temperature)
        botLayout.addWidget(self.gb_pressure)
        botLayout.addWidget(self.gb_motor)
        botLayout.addWidget(self.gb_run)
        botLayout.addWidget(self.gb_expert)
        botLayout.addStretch(1)
        
        # Main (parent) layout
        mainLayout = QVBoxLayout()
        mainLayout.addLayout(topLayout, 1)
        mainLayout.addWidget(QLabel(''), 0)
        mainLayout.addLayout(botLayout, 0)
        self.setLayout(mainLayout)
        
        self.setWindowTitle("Drill Control Panel")
        
    def create_gb_surface(self, initstr='N/A'):
        self.gb_surface = QGroupBox("Surface")
        layout = QVBoxLayout()
        self.gb_surface_load            = self.MakeStateBox('surface_load',            'Load (kg)',            initstr)
        self.gb_surface_depth           = self.MakeStateBox('surface_depth',           'Depth (m)',            initstr)
        self.gb_surface_speed           = self.MakeStateBox('surface_speed',           'Speed (cm/s)',         initstr)
        self.gb_surface_loadcable       = self.MakeStateBox('surface_loadcable',       'Load - cable (kg)',    initstr)
        self.gb_surface_peakload        = self.MakeStateBox('surface_peakload',        'Peak load, %is (kg)'%(XAXISLEN), initstr)
        self.gb_surface_downholevoltage = self.MakeStateBox('surface_downholevoltage', 'Downhole vol. (V)',    initstr)
        layout.addWidget(self.gb_surface_load)
        layout.addWidget(self.gb_surface_depth)
        layout.addWidget(self.gb_surface_speed)
        layout.addWidget(self.gb_surface_loadcable)
        layout.addWidget(self.gb_surface_peakload)
        layout.addWidget(self.gb_surface_downholevoltage)
        layout.addStretch(1)
        self.gb_surface.setLayout(layout)

    def create_gb_orientation(self, initstr='N/A'):
        self.gb_orientation = QGroupBox("Orientation")
        layout = QVBoxLayout()
        layout.addWidget(self.MakeStateBox('orientation_inclination',  'Inclination (deg)',  initstr))
        layout.addWidget(self.MakeStateBox('orientation_azimuth',      'Azimuth (deg)',      initstr))
        layout.addWidget(self.MakeStateBox('orientation_spin',         'Drill spin (RPM)',   initstr))
        if USE_BNO055_FOR_ORIENTATION:
            layout.addWidget(self.MakeStateBox('orientation_drilldir', 'Orientation vector', initstr))
            if SHOW_BNO055_DETAILED:
#                layout.addWidget(self.MakeStateBox('orientation_quat', 'Quaternion (BNO055)',         initstr))
                self.gb_BNO055 = QGroupBox("BNO055 triaxial values")
                layout_BNO055 = QVBoxLayout()
                layout_BNO055.addWidget(self.MakeStateBox('orientation_acceleration', 'Acceleration (m/s^2)', initstr))
                layout_BNO055.addWidget(self.MakeStateBox('orientation_magnetometer', 'Magnetometer (mT)',    initstr))
                layout_BNO055.addWidget(self.MakeStateBox('orientation_gyroscope',    'Gyroscope (deg/s)',    initstr))
                self.gb_BNO055.setLayout(layout_BNO055)
                layout.addWidget(self.gb_BNO055)
        else:
            layout.addWidget(self.MakeStateBox('orientation_inclinometer', 'Inclinometer [x,y] (deg)', initstr))
                
        layout.addStretch(1)
        self.gb_orientation.setLayout(layout)
        
    def create_gb_pressure(self, initstr='N/A'):
        self.gb_pressure = QGroupBox("Pressure (mbar)")
        layout = QVBoxLayout()
        layout.addWidget(self.MakeStateBox('pressure_topplug',     'Top plug',    initstr))
        layout.addWidget(self.MakeStateBox('pressure_gear1',       'Gear 1',      initstr))
        layout.addWidget(self.MakeStateBox('pressure_gear2',       'Gear 2',      initstr))
        layout.addWidget(self.MakeStateBox('pressure_electronics', 'Electronics', initstr))
        layout.addWidget(self.MakeStateBox('hammer',               'Hammer (%)',         initstr))
        layout.addStretch(1)
        self.gb_pressure.setLayout(layout)

    def create_gb_temperature(self, initstr='N/A'):
        self.gb_temperature = QGroupBox("Temperature (C)")
        layout = QVBoxLayout()
        layout.addWidget(self.MakeStateBox('temperature_topplug',        'Top plug',         initstr))
        layout.addWidget(self.MakeStateBox('temperature_gear1',          'Gear 1',           initstr))
        layout.addWidget(self.MakeStateBox('temperature_gear2',          'Gear 2',           initstr))
        layout.addWidget(self.MakeStateBox('temperature_electronics',    'Electronics',      initstr))
        layout.addWidget(self.MakeStateBox('temperature_auxelectronics', 'Aux. electronics', initstr))
        layout.addWidget(self.MakeStateBox('temperature_motor',          'Motor',            initstr))
        layout.addWidget(self.MakeStateBox('temperature_motorctrl',      'Motor controller', initstr))
        layout.addStretch(1)
        self.gb_temperature.setLayout(layout)
        

    def create_gb_motor(self, initstr='N/A', btn_width=170):
        self.gb_motor = QGroupBox("Motor")
        layout = QGridLayout()
        layout.addWidget(self.MakeStateBox('motor_current',  'Current (A)',  initstr), 1,1)
        layout.addWidget(self.MakeStateBox('motor_speed',    'Speed (RPM)',  initstr), 1,2)
        layout.addWidget(self.MakeStateBox('motor_voltage',  'Voltage (V)',  initstr), 2,1)
        layout.addWidget(self.MakeStateBox('motor_throttle', 'Throttle (%)', initstr), 2,2)

        ### Throttle

        row = 3
        layout.addWidget(QLabel(), row,1)
        self.sl_throttle_label = QLabel('Throttle: 0%')
        layout.addWidget(self.sl_throttle_label, row+1,1, 1,2)
        self.sl_throttle = QSlider(Qt.Horizontal)
        self.sl_throttle.setMinimum(-100)
        self.sl_throttle.setMaximum(100)
        self.sl_throttle.setValue(0)
        self.sl_throttle.setTickPosition(QSlider.TicksBelow)
        self.sl_throttle.setTickInterval(20)
        self.sl_throttle.valueChanged.connect(self.changed_throttle) # sliderReleased
        layout.addWidget(self.sl_throttle, row+2,1, 1,2)
        layout.addWidget(QLabel('Press start to express'), row+3,1, 1,2)
        self.btn_motorstart = QPushButton("Start")
        self.btn_motorstart.setStyleSheet("background-color : %s"%(COLOR_GREEN))
        self.btn_motorstart.clicked.connect(self.clicked_motorstart)
        self.btn_motorstop = QPushButton("Stop")
        self.btn_motorstop.setStyleSheet("background-color : %s"%(COLOR_RED))
        self.btn_motorstop.clicked.connect(self.clicked_motorstop)
        self.btn_motorstart.setMinimumWidth(btn_width); self.btn_motorstart.setMaximumWidth(btn_width)
        self.btn_motorstop.setMinimumWidth(btn_width);  self.btn_motorstop.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_motorstart, row+4,1)
        layout.addWidget(self.btn_motorstop,  row+4,2)
        
        ### Inching
        
        row = 8
        layout.addWidget(QLabel(), row,1)
        self.sl_inching_label = QLabel('Inching: 0 deg')
        layout.addWidget(self.sl_inching_label, row+1,1)
        self.sl_inching = QSlider(Qt.Horizontal)
        self.sl_inching.setMinimum(-360)
        self.sl_inching.setMaximum(+360)
        self.sl_inching.setValue(0)
        self.sl_inching.setTickPosition(QSlider.TicksBelow)
        self.sl_inching.setTickInterval(int(180/4))
        self.sl_inching.valueChanged.connect(self.changed_sl_inching)
        layout.addWidget(self.sl_inching, row+2,1, 1,1)
        self.dial_inching = QDial()
        self.dial_inching.setNotchesVisible(True)
        self.dial_inching.setMinimum(-180)
        self.dial_inching.setMaximum(+180)
        self.dial_inching.setWrapping(True)
        self.dial_inching.setMaximumHeight(75)
        layout.addWidget(self.dial_inching, row+1,2, 3,1)
        layout.addWidget(QLabel('Press start to express'), row+3,1, 1,2)
        self.btn_inchingstart = QPushButton("Start")
        self.btn_inchingstart.setStyleSheet("background-color : %s"%(COLOR_GREEN))
        self.btn_inchingstart.clicked.connect(self.clicked_inchingstart)
#        self.btn_inchingstop = QPushButton("Stop")
#        self.btn_inchingstop.setStyleSheet("background-color : %s"%(COLOR_RED))
#        self.btn_inchingstop.clicked.connect(self.clicked_motorstop)
        self.btn_inchingstart.setMinimumWidth(btn_width); self.btn_inchingstart.setMaximumWidth(btn_width)
#        self.btn_inchingstop.setMinimumWidth(btn_width);  self.btn_inchingstop.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_inchingstart, row+4,1)
#        layout.addWidget(self.btn_inchingstop,  row+4,2)
              
        ###              
        layout.setRowStretch(row+5, 1)
        self.gb_motor.setLayout(layout)
        
    def create_gb_run(self, initstr='N/A'):
        self.gb_run = QGroupBox("Current run")
        layout = QVBoxLayout()
        self.btn_startrun = QPushButton("Start")
        self.btn_startrun.setCheckable(True)
        self.btn_startrun.clicked.connect(self.clicked_startstop_run)
        self.btn_startrun.setStyleSheet("background-color : %s"%(COLOR_GREEN))
        layout.addWidget(self.btn_startrun)

        self.cbox_plotdeltaload = QCheckBox("Plot tare load")
        self.cbox_plotdeltaload.toggled.connect(self.clicked_plotdeltaload)     
        layout.addWidget(self.cbox_plotdeltaload)  
        
        self.btn_screenshot = QPushButton("Screenshot")
        self.btn_screenshot.clicked.connect(self.take_screenshot)
        layout.addWidget(self.btn_screenshot)

        layout.addWidget(self.MakeStateBox('run_time', 'Run time', initstr))
        self.gb_run_startdepth = self.MakeStateBox('run_startdepth', 'Start depth (m)',  initstr)
        self.gb_run_deltadepth = self.MakeStateBox('run_deltadepth', 'Delta depth (m)',  initstr)
        self.gb_run_startload  = self.MakeStateBox('run_startload',  'Start load (kg)',  initstr)
        self.gb_run_deltaload  = self.MakeStateBox('run_deltaload',  'Tare load (kg)',   initstr)
        layout.addWidget(self.gb_run_startdepth)
        layout.addWidget(self.gb_run_deltadepth)
        layout.addWidget(self.gb_run_startload)
        layout.addWidget(self.gb_run_deltaload)
        layout.addStretch(1)
        self.gb_run.setLayout(layout)

    def create_gb_expert(self, default_inchingthrottle=5, initstr='N/A'):
        self.gb_expert = QGroupBox("Expert control")
        layout = QVBoxLayout()
        self.cbox_unlockexpert = QCheckBox("Unlock")
        self.cbox_unlockexpert.toggled.connect(self.clicked_unlockexpert)     
        layout.addWidget(self.cbox_unlockexpert)

        layout.addWidget(QLabel(''))        
        self.sl_inchingthrottle_label = QLabel('Inching throttle: %i%%'%(default_inchingthrottle))
        self.sl_inchingthrottle_label.setEnabled(False)
        layout.addWidget(self.sl_inchingthrottle_label)
        self.sl_inchingthrottle = QSlider(Qt.Horizontal)
        self.sl_inchingthrottle.setMinimum(0)
        self.sl_inchingthrottle.setMaximum(15)
        self.sl_inchingthrottle.setValue(default_inchingthrottle) 
        self.sl_inchingthrottle.setTickPosition(QSlider.TicksBelow)
        self.sl_inchingthrottle.setTickInterval(20)
        self.sl_inchingthrottle.setEnabled(False)
        self.sl_inchingthrottle.valueChanged.connect(self.changed_inchingthrottle) 
        layout.addWidget(self.sl_inchingthrottle)
        
        layout.addWidget(QLabel(''))
        self.cb_motorconfig_label = QLabel('Motor config:')
        self.cb_motorconfig_label.setEnabled(False)
        layout.addWidget(self.cb_motorconfig_label)
        self.cb_motorconfig = QComboBox()
        self.cb_motorconfig.addItems(["parvalux", "skateboard", "hacker", "plettenberg"])
        self.cb_motorconfig.currentIndexChanged.connect(self.changed_motorconfig)
        self.cb_motorconfig.setEnabled(False)
        layout.addWidget(self.cb_motorconfig)

        layout.addStretch(1)
        self.gb_expert.setLayout(layout)
        
    ### User actions 
    
    # Motor
    
    def changed_throttle(self):
        self.sl_throttle_label.setText('Throttle: %i%%'%(self.sl_throttle.value()))
        
    def changed_sl_inching(self):
        deg = self.sl_inching.value()
        self.dial_inching.setValue(deg)
        self.sl_inching_label.setText('Inching: %+i deg'%(deg))
        
    def clicked_motorstart(self):
        throttle_pct = int(self.sl_throttle.value())
        self.ds.start_motor__throttle(throttle_pct)
        
    def clicked_inchingstart(self):
        deg = self.sl_inching.value()
        self.ds.start_motor__degrees(deg, throttle_pct=int(self.sl_inchingthrottle.value()))
        
    def clicked_motorstop(self):
        self.ds.stop_motor()
        
    # Expert control 
    
    def clicked_unlockexpert(self):
        unlocked = self.cbox_unlockexpert.isChecked()

        self.cb_motorconfig_label.setEnabled(unlocked)
        self.cb_motorconfig.setEnabled(unlocked)

        self.sl_inchingthrottle_label.setEnabled(unlocked)
        self.sl_inchingthrottle.setEnabled(unlocked)


    def changed_motorconfig(self):
        pass

    def changed_inchingthrottle(self):
        self.sl_inchingthrottle_label.setText('Inching throttle: %i%%'%(self.sl_inchingthrottle.value()))

    # Logging/run-status panel
    
    def clicked_startstop_run(self):
        if self.btn_startrun.isChecked(): # start pressed
            self.btn_startrun.setText('Stop')
            self.btn_startrun.setStyleSheet("background-color : %s"%(COLOR_RED))
            self.cbox_plotdeltaload.setChecked(True)
            self.runtime0 = datetime.datetime.now()
            self.ss.set_loadtare(self.ss.load)
            self.ss.set_depthtare(self.ss.depth)
        else:
            self.btn_startrun.setText('Start')
            self.btn_startrun.setStyleSheet("background-color : %s"%(COLOR_GREEN))
            self.cbox_plotdeltaload.setChecked(False)
    
    def take_screenshot(self):
        fname = '%s/%s.png'%(PATH_SCREENSHOT, datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
        command = 'scrot -F "%s"'%(fname)
        os.system(command)
        print('Saving screenshot to %s'%(fname))
    
    def clicked_plotdeltaload(self):
        pass
        
    ### State update
    
    def MakeStateBox(self, id, name, value, margin_left=6, margin_right=0, margin_topbot=3):
        gb = QGroupBox(name)
        layout = QHBoxLayout()
        lbl = QLabel(value)
        setattr(self, id, lbl)
        layout.addWidget(lbl)
        layout.setContentsMargins(margin_left, margin_topbot, margin_right, margin_topbot)
        gb.setLayout(layout)
        return gb
      
    def updateStateBox(self, id, value, warnthres):
        lbl = getattr(self, id)
        lbl.setText(str(value))
        if isinstance(value, float) or isinstance(value, int):
            if warnthres[0] <= value <= warnthres[1]: lbl.setStyleSheet("background: none")
            else:                                     lbl.setStyleSheet("background: %s"%(COLOR_RED))
            
    def eventListener(self):

        warn__nothres = [-np.inf, np.inf]

        #-----------------------
        # Update surface state
        #-----------------------
        
        self.ss.update()

        ### Update graphs
        self.hist_speed = np.roll(self.hist_speed, -1); self.hist_speed[-1] = self.ss.speed*100
        self.curve_speed.setData(x=self.hist_time,y=self.hist_speed)
        self.hist_load = np.roll(self.hist_load,  -1); self.hist_load[-1]  = self.ss.load
        self.hist_loadtare = self.hist_load-self.ss.loadtare
        self.curve_load.setData( x=self.hist_time,y=self.hist_loadtare if self.cbox_plotdeltaload.isChecked() else self.hist_load)

        if self.cbox_plotdeltaload.isChecked(): self.plot_load.setTitle(self.htmlfont('<b>Tare load = %.2f kg'%(self.ss.load-self.ss.loadtare), FS_GRAPH_TITLE))
        else:                                   self.plot_load.setTitle(self.htmlfont('<b>Load = %.2f kg'%(self.ss.load), FS_GRAPH_TITLE))
        self.plot_speed.setTitle(self.htmlfont('<b>Speed = %.2f cm/s'%(self.ss.speed), FS_GRAPH_TITLE))        
        self.plot_current.setTitle(self.htmlfont('<b>Current = %.1f A'%(self.ds.motor_current), FS_GRAPH_TITLE))

        ### Update state fields
        self.updateStateBox('surface_depth',           round(self.ss.depth,PRECISION_DEPTH),  warn__nothres)  # precision to match physical display
        self.updateStateBox('surface_speed',           round(self.ss.speed*100,2),            warn__velocity*100)
        self.updateStateBox('surface_load',            round(self.ss.load,PRECISION_LOAD),    warn__load) # precision to match physical display
        self.updateStateBox('surface_loadcable',       round(self.ss.loadnet,PRECISION_LOAD), warn__nothres)
        self.updateStateBox('surface_peakload',        round(np.amax(self.hist_load),PRECISION_LOAD), warn__nothres)
        self.updateStateBox('surface_downholevoltage', round(self.ds.downhole_voltage,1),     warn__nothres)

        if self.btn_startrun.isChecked(): 
            self.runtime1 = datetime.datetime.now() # update run time
            if self.runtime0 is not None:
                druntime = self.runtime1-self.runtime0
                self.updateStateBox('run_time',       self.timestamp(druntime),                                 warn__nothres)
                self.updateStateBox('run_startdepth', round(self.ss.depthtare,PRECISION_DEPTH),                 warn__nothres)    
                self.updateStateBox('run_startload',  round(self.ss.loadtare,PRECISION_LOAD),                   warn__nothres)    
                self.updateStateBox('run_deltadepth', round(self.ss.depth - self.ss.depthtare,PRECISION_DEPTH), warn__corelength)    
                self.updateStateBox('run_deltaload',  round(self.ss.load  - self.ss.loadtare,PRECISION_LOAD),   warn__nothres)
                

        #-----------------------
        # Update drill state
        #-----------------------
        
        if self.Nt % DTFRAC_DRILL == 0:

            self.ds.update()

            ### Update graphs
            self.hist_current  = np.roll(self.hist_current,  -1); self.hist_current[-1]  = self.ds.motor_current
            self.curve_current.setData(  x=self.hist_time_drill,y=self.hist_current)

            if not self.ds.isdead:
               
                ### Update state fields
                str_incvec   = '[%.1f, %.1f]'%(self.ds.inclination_x,self.ds.inclination_x)
                self.updateStateBox('orientation_inclination',  round(self.ds.inclination,1), warn__nothres)
                self.updateStateBox('orientation_azimuth',      round(self.ds.azimuth,1),     warn__nothres)
                self.updateStateBox('orientation_spin',         round(self.ds.spin,1),        warn__spin)
                if USE_BNO055_FOR_ORIENTATION:
                    str_drilldir = '[%.1f, %.1f, %.1f]'%(self.ds.drilldir[0],self.ds.drilldir[1],self.ds.drilldir[2])
                    self.updateStateBox('orientation_drilldir', str_drilldir,  warn__nothres)
                    if SHOW_BNO055_DETAILED:
    #                    str_quat = '[%.1f, %.1f, %.1f, %.1f]'%(self.ds.quat[0],self.ds.quat[1],self.ds.quat[2],self.ds.quat[3])
    #                    self.updateStateBox('orientation_quat',         str_quat,   warn__nothres)
                        str_aclvec   = '[%.1f, %.1f, %.1f], %.2f'%(self.ds.accelerometer_x,self.ds.accelerometer_y,self.ds.accelerometer_z, self.ds.accelerometer_magnitude)
                        str_magvec   = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.magnetometer_x,self.ds.magnetometer_y,self.ds.magnetometer_z, self.ds.magnetometer_magnitude)
                        str_spnvec   = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.gyroscope_x,self.ds.gyroscope_y,self.ds.gyroscope_z, self.ds.gyroscope_magnitude)
                        self.updateStateBox('orientation_acceleration', str_aclvec, warn__nothres)
                        self.updateStateBox('orientation_magnetometer', str_magvec, warn__nothres)
                        self.updateStateBox('orientation_gyroscope',    str_spnvec, warn__nothres)
                else:
                    self.updateStateBox('orientation_inclinometer', str_incvec,          warn__nothres)

                self.updateStateBox('pressure_electronics', round(self.ds.pressure_electronics,1), warn__pressure)
                self.updateStateBox('pressure_topplug',     round(self.ds.pressure_topplug,1),     warn__pressure)
                self.updateStateBox('pressure_gear1',       round(self.ds.pressure_gear1,1),       warn__pressure)
                self.updateStateBox('pressure_gear2',       round(self.ds.pressure_gear2,1),       warn__pressure)
                self.updateStateBox('hammer',               round(self.ds.hammer,1),               warn__hammer)

                self.updateStateBox('temperature_electronics',    round(self.ds.temperature_electronics,1),    warn__temperature_electronics)
                self.updateStateBox('temperature_topplug',        round(self.ds.temperature_topplug,1),        warn__temperature_electronics)
                self.updateStateBox('temperature_gear1',          round(self.ds.temperature_gear1,1),          warn__temperature_electronics)
                self.updateStateBox('temperature_gear2',          round(self.ds.temperature_gear1,1),          warn__temperature_electronics)
                self.updateStateBox('temperature_auxelectronics', round(self.ds.temperature_auxelectronics,1), warn__temperature_electronics)
                self.updateStateBox('temperature_motor',          round(self.ds.temperature_motor,1),          warn__temperature_motor)    
                self.updateStateBox('temperature_motorctrl',      round(self.ds.motor_controller_temp,1),      warn__temperature_motor)    
                
                self.updateStateBox('motor_current',  round(self.ds.motor_current,1),  warn__motor_current)
                self.updateStateBox('motor_speed',    round(self.ds.motor_rpm,1),      warn__motor_rpm)    
                self.updateStateBox('motor_voltage',  round(self.ds.motor_voltage,1),  warn__nothres)    
                self.updateStateBox('motor_throttle', round(self.ds.motor_throttle,0), warn__nothres)
        
        ### Disabled widgets if drill state is dead
        
        self.gb_orientation.setEnabled(not self.ds.isdead)
        self.gb_pressure.setEnabled(not self.ds.isdead)
        self.gb_temperature.setEnabled(not self.ds.isdead)
        self.gb_motor.setEnabled(not self.ds.isdead)
        self.gb_expert.setEnabled(not self.ds.isdead)
        self.gb_surface_downholevoltage.setEnabled(not self.ds.isdead)

        ### Disabled widgets if winch encoder is dead

        for f in ['gb_surface_depth','gb_surface_speed', 'gb_run_startdepth','gb_run_deltadepth']:
            lbl = getattr(self, f)
            lbl.setEnabled(not self.ss.isloadcelldead)
                        
#        if self.ss.isloadcelldead: self.curve_load.hide()
#        else:                      self.curve_load.show()
                        
        ### Disabled widgets if load cell is dead
                        
        for f in ['gb_surface_load','gb_surface_loadcable','gb_surface_peakload',  'gb_run_startload','gb_run_deltaload']:
            lbl = getattr(self, f)
            lbl.setEnabled(not self.ss.isdepthcounterdead)
            
        
        ### END
                    
        self.Nt += 1
        
    def timestamp(self, turnaround):
        total_seconds = int(turnaround.total_seconds())
        hours, remainder = divmod(total_seconds,60*60)
        minutes, seconds = divmod(remainder,60)
        return "%02i:%02i:%02i"%(hours,minutes,seconds)
        
    def htmlfont(self, text,fsize, color='#000000'): return '<font size="%i" color="%s">%s</font>'%(fsize,color,text)
        
if __name__ == '__main__':

    def sigint_handler(*args): QApplication.quit()
    signal.signal(signal.SIGINT, sigint_handler)

    app = QApplication(sys.argv)
    app.setStyle('Fusion') # Windows | Fusion | chameleon
    font = app.font() #QFont('Helvetica'); 
    font.setPointSizeF(FS);
    app.setFont(font)
    
    main = MainWidget()
    main.show()
    dH = 30
    H = QDesktopWidget().availableGeometry().height()-dH
    W = 0 # setting width = 0 effectively sets the minimal window width allowed by the widgets enclosed
    main.setGeometry(0, dH, W, H)
    
    # Update main window with latest field values ever DT seconds
    timer1 = QTimer()
    timer1.timeout.connect(main.eventListener)
    timer1.start(int(DT*1000))
    
    sys.exit(app.exec())
