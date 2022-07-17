# N. Rathmann <rathmann@nbi.dk>, 2019-2022

import sys, os, signal, datetime
import numpy as np

from settings import *
from state_drill import *
from state_surface import *

from PyQt5.QtCore import * 
from PyQt5.QtWidgets import * 
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
import pyqtgraph as pg

#-------------------
# Settings
#-------------------

DT           = 1/8 # update rate in seconds for GUI/surface state
DTFRAC_DRILL = 4 # update the drill state every DTFRAC_DRILL times the GUI/surface state is updated

tavg = 3 # time-averging length in seconds for velocity estimate

ALWAYS_SHOW_DRILL_FIELDS = True # ignore if drill is offline and show last recorded redis fields for drill

FS = 13
FS_GRAPH_TITLE = 5 # font size for graph titles
PATH_SCREENSHOT = "/mnt/logs/screenshots"

# Print settings
print('%s: running with DT=%.3fs, DT_DRILL=%.3fs'%(sys.argv[0],DT,DT*DTFRAC_DRILL))
print('Using BNO055 for orientation? %s'%('Yes' if USE_BNO055_FOR_ORIENTATION else 'No'))

# GUI colors
COLOR_GRAYBG = '#f0f0f0'
COLOR_GREEN = '#66bd63'
COLOR_RED   = '#f46d43'
COLOR_DARKRED   = '#b2182b'
COLOR_DARKGREEN = '#1a9850'
COLOR_BLUE  = '#3182bd'

#-------------------
# Program start
#-------------------

class MainWidget(QWidget):

    runtime0 = None
    Nt = 0 # number of time steps taken

    loadmeasures      = {'hist_load':'Load', 'hist_loadnet':'Load - cable', 'hist_loadtare':'Tare load'}
    loadmeasure_inuse = 'hist_load'

    xlen            = [int(0.5*60), int(2*60), int(10*60), int(45*60)] 
    xlen_names      = ["1/2 min", "2 min", "10 min", "45 min"]
    xlen_samplerate = [1,1,1,1]  
    xlen_selector   = {'speed':0, 'load':0, 'current':0} # default selection
    
    minYRange_load = 20 # kg
    minYRange_speed = 10.5 # cm/s
    
    SHOW_BNO055_DETAILED = 0
    
    def __init__(self, parent=None):
    
        super(MainWidget, self).__init__(parent)

        ### State objects

        # REDIS_HOST determined in settings file
        self.ds = DrillState(redis_host=REDIS_HOST)   
        self.ss = SurfaceState(tavg, DT*DTFRAC_DRILL,redis_host=REDIS_HOST)

        ### pyqt graphs

        pg.setConfigOptions(background=COLOR_GRAYBG) # gray
        pg.setConfigOptions(foreground='k')

        # X-axis
        self.hist_time       = np.flipud(np.arange(0, self.xlen[-1]/60 +1e-9, DT/60))
        self.hist_time_drill = np.flipud(np.arange(0, self.xlen[-1]/60 +1e-9, DT*DTFRAC_DRILL/60))
        self.hist_load       = np.full(len(self.hist_time), 0.0)
        self.hist_loadnet    = np.full(len(self.hist_time), 0.0)
        self.hist_loadtare   = np.full(len(self.hist_time), 0.0)
        self.hist_speed      = np.full(len(self.hist_time), 0.0)
        self.hist_current    = np.full(len(self.hist_time_drill), 0.0)

        def setupaxis(obj):
            obj.invertX()
            obj.setXRange(0, self.xlen[0]/60, padding=0)
            obj.showAxis('right')
            obj.showAxis('top')      
            obj.setMenuEnabled(False)
            obj.setMouseEnabled(x=False, y=False)  
            obj.setLabel('right', "&nbsp;") # hacky way of adding spacing between graphs
            obj.setLabel('bottom', "Minutes ago")
            obj.showGrid(y=True,x=True)
            obj.getAxis('left').setGrid(False)
            obj.getAxis('bottom').setGrid(False)
            for ax in ['left', 'top']:
                obj.showAxis(ax)
                obj.getAxis(ax).setStyle(showValues=False)

        # Plots
        self.plot_load    = pg.PlotWidget(); 
        self.plot_speed   = pg.PlotWidget(); 
        self.plot_current = pg.PlotWidget(); 
        setupaxis(self.plot_load);
        setupaxis(self.plot_speed);
        setupaxis(self.plot_current);
        self.plot_load.setLimits(minYRange=self.minYRange_load) # minimum y-axis span for load (don't auto-zoom in too much)
#        self.plot_speed.setLimits(minYRange=self.minYRange_speed+0.2, yMin=-0.2) # minimum y-axis span for speed (don't auto-zoom in too much)
        self.plot_current.setYRange(0, warn__motor_current[1]*1.2, padding=0.02)

        # init curves
        lw = 3
        plotpen_black = pg.mkPen(color='k', width=lw)
        self.curve_load    = self.plot_load.plot(    x=self.hist_time,y=self.hist_time*0-1e4, pen=plotpen_black)
        self.curve_speed   = self.plot_speed.plot(   x=self.hist_time,y=self.hist_time*0-1e4, pen=plotpen_black)
        self.curve_current = self.plot_current.plot( x=self.hist_time_drill,y=self.hist_time_drill*0-1e4, pen=plotpen_black)

        ### State fields

        self.create_gb_surface()
        self.create_gb_orientation()
        self.create_gb_temperature()
        self.create_gb_pressure()
        self.create_gb_other()
        self.create_gb_motor()
        self.create_gb_run()
        self.create_gb_status()
        self.create_gb_expert()

        ### QT Layout

        # Graphs (top)

        w_btn = 100
        s_btn = 15
        
        topLayout = QHBoxLayout() # graphs and associated buttons
        
        plotLayout1 = QVBoxLayout()
        plotLayout1.addWidget(self.plot_speed)
        plotLayout1btn = QHBoxLayout()
        plotLayout1btn.setSpacing(s_btn)
        plotLayout1btn.addStretch(1)
        speed_xlen_btn1 = QPushButton(self.xlen_names[0]); speed_xlen_btn1.clicked.connect(lambda: self.changed_xaxislen_speed(0)); speed_xlen_btn1.setMaximumWidth(w_btn); plotLayout1btn.addWidget(speed_xlen_btn1)
        speed_xlen_btn2 = QPushButton(self.xlen_names[1]); speed_xlen_btn2.clicked.connect(lambda: self.changed_xaxislen_speed(1)); speed_xlen_btn2.setMaximumWidth(w_btn); plotLayout1btn.addWidget(speed_xlen_btn2)
        speed_xlen_btn3 = QPushButton(self.xlen_names[2]); speed_xlen_btn3.clicked.connect(lambda: self.changed_xaxislen_speed(2)); speed_xlen_btn3.setMaximumWidth(w_btn); plotLayout1btn.addWidget(speed_xlen_btn3)
        speed_xlen_btn4 = QPushButton(self.xlen_names[3]); speed_xlen_btn4.clicked.connect(lambda: self.changed_xaxislen_speed(3)); speed_xlen_btn4.setMaximumWidth(w_btn); plotLayout1btn.addWidget(speed_xlen_btn4)
        plotLayout1btn.addStretch(2)
        plotLayout1.addLayout(plotLayout1btn)

        plotLayout2 = QVBoxLayout()
        plotLayout2.addWidget(self.plot_load)
        plotLayout2btn = QHBoxLayout()
        plotLayout2btn.setSpacing(s_btn)
        plotLayout2btn.addStretch(2)
        load_xlen_btn1 = QPushButton(self.xlen_names[0]); load_xlen_btn1.clicked.connect(lambda: self.changed_xaxislen_load(0)); load_xlen_btn1.setMaximumWidth(w_btn); plotLayout2btn.addWidget(load_xlen_btn1)
        load_xlen_btn2 = QPushButton(self.xlen_names[1]); load_xlen_btn2.clicked.connect(lambda: self.changed_xaxislen_load(1)); load_xlen_btn2.setMaximumWidth(w_btn); plotLayout2btn.addWidget(load_xlen_btn2)
        load_xlen_btn3 = QPushButton(self.xlen_names[2]); load_xlen_btn3.clicked.connect(lambda: self.changed_xaxislen_load(2)); load_xlen_btn3.setMaximumWidth(w_btn); plotLayout2btn.addWidget(load_xlen_btn3)
        load_xlen_btn4 = QPushButton(self.xlen_names[3]); load_xlen_btn4.clicked.connect(lambda: self.changed_xaxislen_load(3)); load_xlen_btn4.setMaximumWidth(w_btn); plotLayout2btn.addWidget(load_xlen_btn4)
        plotLayout2btn.addStretch(1)
        plotLayout2btn.addWidget(QLabel('Plot:'))
        self.cb_loadmeasure = QComboBox()
        self.cb_loadmeasure.addItems([self.loadmeasures[key] for key in self.loadmeasures.keys()])
        self.cb_loadmeasure.currentIndexChanged.connect(self.changed_loadmeasure)
        plotLayout2btn.addWidget(self.cb_loadmeasure)
        plotLayout2btn.addStretch(2)
        plotLayout2.addLayout(plotLayout2btn)
        
        plotLayout3 = QVBoxLayout()        
        plotLayout3.addWidget(self.plot_current)
        plotLayout3btn = QHBoxLayout()
        plotLayout3btn.setSpacing(s_btn)
        plotLayout3btn.addStretch(1)
        current_xlen_btn1 = QPushButton(self.xlen_names[0]); current_xlen_btn1.clicked.connect(lambda: self.changed_xaxislen_current(0)); current_xlen_btn1.setMaximumWidth(w_btn); plotLayout3btn.addWidget(current_xlen_btn1)
        current_xlen_btn2 = QPushButton(self.xlen_names[1]); current_xlen_btn2.clicked.connect(lambda: self.changed_xaxislen_current(1)); current_xlen_btn2.setMaximumWidth(w_btn); plotLayout3btn.addWidget(current_xlen_btn2)
        current_xlen_btn3 = QPushButton(self.xlen_names[2]); current_xlen_btn3.clicked.connect(lambda: self.changed_xaxislen_current(2)); current_xlen_btn3.setMaximumWidth(w_btn); plotLayout3btn.addWidget(current_xlen_btn3)
        current_xlen_btn4 = QPushButton(self.xlen_names[3]); current_xlen_btn4.clicked.connect(lambda: self.changed_xaxislen_current(3)); current_xlen_btn4.setMaximumWidth(w_btn); plotLayout3btn.addWidget(current_xlen_btn4)
        plotLayout3btn.addStretch(2)
        plotLayout3.addLayout(plotLayout3btn)
                
        topLayout.addLayout(plotLayout1,1)
        topLayout.addLayout(plotLayout2,2)
        topLayout.addLayout(plotLayout3,1)

        
        # State fields (bottom)
        botLayout = QHBoxLayout()

        depthbarLayout = QVBoxLayout()
        self.lbl_depthbar = QLabel(self.htmlfont('<b>Depth', FS_GRAPH_TITLE))
        depthbarLayout.addWidget(self.lbl_depthbar)
        depthbarLayoutInner = QHBoxLayout()
        depthbarLayoutInner.addStretch(1)
        self.depthbar = DepthProgressBar(DEPTH_MAX)
        depthbarLayoutInner.addWidget(self.depthbar)
        depthbarLayoutInner.addStretch(1)
        depthbarLayoutInner.setContentsMargins(10, 0, 20, 0)
        depthbarLayout.addLayout(depthbarLayoutInner)
        botLayout.addLayout(depthbarLayout,0)
        
        botLayout.addWidget(self.gb_surface)
        botLayout.addWidget(self.gb_orientation)
        botLayout.addWidget(self.gb_temperature)
        botLayoutSub1 = QVBoxLayout()
        botLayoutSub1.addWidget(self.gb_pressure)
        botLayoutSub1.addWidget(self.gb_other)
        botLayout.addLayout(botLayoutSub1)
        botLayout.addWidget(self.gb_motor)
        botLayout.addWidget(self.gb_run)
        botLayoutSub2 = QVBoxLayout()
        botLayoutSub2.addWidget(self.gb_status)
        botLayoutSub2.addWidget(self.gb_expert)
        botLayout.addLayout(botLayoutSub2)
        botLayout.addStretch(1)
        
        # Main (parent) layout
        mainLayout = QVBoxLayout()
        mainLayout.addLayout(topLayout, 1)
        mainLayout.addWidget(QLabel(''), 0) # spacer
        mainLayout.addLayout(botLayout, 0)
        self.setLayout(mainLayout)
        
        self.setWindowTitle("Drill Control Panel")
        
    def create_gb_surface(self, initstr='N/A'):
        self.gb_surface = QGroupBox("Surface")
        layout = QVBoxLayout()
        self.gb_surface_load            = self.MakeStateBox('surface_load',            'Load (kg)',            initstr)
        self.gb_surface_depth           = self.MakeStateBox('surface_depth',           'Depth (m)',            initstr)
        self.gb_surface_speed           = self.MakeStateBox('surface_speed',           'Inst. speed (cm/s)',   initstr)
        self.gb_surface_loadcable       = self.MakeStateBox('surface_loadcable',       'Load - cable (kg)',    initstr)
        self.gb_run_deltaload           = self.MakeStateBox('run_deltaload',  'Tare load (kg)',   initstr)
        self.gb_run_peakload            = self.MakeStateBox('run_peakload',   'Peak load, %is (kg)'%(self.xlen[0]), initstr)
        layout.addWidget(self.gb_surface_depth)
        layout.addWidget(self.gb_surface_speed)
        layout.addWidget(self.gb_surface_load)
        layout.addWidget(self.gb_surface_loadcable)
        layout.addWidget(self.gb_run_deltaload)
        layout.addWidget(self.gb_run_peakload)
        layout.addStretch(1)
        self.gb_surface.setLayout(layout)

    def create_gb_orientation(self, initstr='N/A'):
        self.gb_orientation = QGroupBox("Orientation")
#        self.gb_orientation.setMinimumWidth(290)
        layout = QVBoxLayout()
        layout.addWidget(self.MakeStateBox('orientation_inclination',  'Inclination (deg)',  initstr))
        layout.addWidget(self.MakeStateBox('orientation_azimuth',      'Azimuth (deg)',      initstr))
        layout.addWidget(self.MakeStateBox('orientation_spin',         'Drill spin (RPM)',   initstr))
        if USE_BNO055_FOR_ORIENTATION:
            layout.addWidget(self.MakeStateBox('orientation_drilldir', 'Orientation vector', initstr))
            self.gb_BNO055 = QGroupBox("BNO055 triaxial values") # create already here because self.cb_show_bno055.setChecked() below requires it be defined
#            layout.addWidget(self.MakeStateBox('orientation_quat', 'Quaternion (BNO055)',         initstr))
            layout_BNO055 = QVBoxLayout()
            layout_BNO055.addWidget(self.MakeStateBox('orientation_acceleration', 'Acceleration (m/s^2)', initstr))
            layout_BNO055.addWidget(self.MakeStateBox('orientation_magnetometer', 'Magnetometer (mT)',    initstr))
            layout_BNO055.addWidget(self.MakeStateBox('orientation_gyroscope',    'Gyroscope (deg/s)',    initstr))
            self.gb_BNO055.setLayout(layout_BNO055)
            self.cb_show_bno055 = QCheckBox("Show BNO055 details?")
            self.cb_show_bno055.toggled.connect(self.clicked_showhide_bno055)     
            self.cb_show_bno055.setChecked(self.SHOW_BNO055_DETAILED)
            self.clicked_showhide_bno055()
            layout.addWidget(self.cb_show_bno055)
            layout.addWidget(self.gb_BNO055)
        else:
            layout.addWidget(self.MakeStateBox('orientation_inclinometer', 'Inclinometer [x,y] (deg)', initstr))
                
        layout.addStretch(1)
        self.gb_orientation.setLayout(layout)
        
    def create_gb_pressure(self, initstr='N/A'):
        self.gb_pressure = QGroupBox("Pressure (mbar)")
        layout = QVBoxLayout()
        layout.addWidget(self.MakeStateBox('pressure_gear1',       'Gear 1, 2',      initstr))
#        layout.addWidget(self.MakeStateBox('pressure_gear2',       'Gear 2',      initstr))
        layout.addWidget(self.MakeStateBox('pressure_electronics', 'Electronics', initstr))
        layout.addWidget(self.MakeStateBox('pressure_topplug',     'Top plug',    initstr))
        layout.addStretch(1)
        self.gb_pressure.setLayout(layout)

    def create_gb_other(self, initstr='N/A'):
        self.gb_other = QGroupBox("Other")
        layout = QVBoxLayout()
        layout.addWidget(self.MakeStateBox('hammer', 'Hammer (%)', initstr))
        self.gb_surface_downholevoltage = self.MakeStateBox('surface_downholevoltage', 'Downhole volt. (V)',   initstr)
        layout.addWidget(self.gb_surface_downholevoltage)
        layout.addStretch(1)
        self.gb_other.setLayout(layout)

    def create_gb_temperature(self, initstr='N/A'):
        self.gb_temperature = QGroupBox("Temperature (C)")
        layout = QVBoxLayout()
        layout.addWidget(self.MakeStateBox('temperature_gear1',          'Gear 1, 2',           initstr))
#        layout.addWidget(self.MakeStateBox('temperature_gear2',          'Gear 2',           initstr))
        layout.addWidget(self.MakeStateBox('temperature_electronics',    'Electronics, Aux.',      initstr))
#        layout.addWidget(self.MakeStateBox('temperature_electronics',    'Electronics',      initstr))
#        layout.addWidget(self.MakeStateBox('temperature_auxelectronics', 'Aux. electronics', initstr))
        layout.addWidget(self.MakeStateBox('temperature_topplug',        'Top plug',         initstr))
        layout.addWidget(self.MakeStateBox('temperature_motor',          'Motor',            initstr))
        layout.addWidget(self.MakeStateBox('temperature_motorctrl',      'Motor ctrl. (VESC)', initstr))
        layout.addStretch(1)
        self.gb_temperature.setLayout(layout)
        

    def create_gb_motor(self, initstr='N/A', btn_width=170):
        self.gb_motor = QGroupBox("Motor")
        layout = QGridLayout()
        layout.addWidget(self.MakeStateBox('motor_current',    'Current (A)',  initstr), 1,1)
        layout.addWidget(self.MakeStateBox('motor_speed',      'Speed (RPM)',  initstr), 1,2)
        layout.addWidget(self.MakeStateBox('motor_voltage',    'Voltage (V)',  initstr), 2,1)
        layout.addWidget(self.MakeStateBox('motor_throttle',   'Throttle (%)', initstr), 2,2)

        ### Throttle

        row = 5
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
        
        row += 5
        layout.addWidget(QLabel(), row,1)
        self.sl_inching_label = QLabel('Inching: 0 deg')
        layout.addWidget(self.sl_inching_label, row+1,1)
        self.sl_inching = QSlider(Qt.Horizontal)
        self.sl_inching.setMinimum(-360)
        self.sl_inching.setMaximum(+360)
        self.sl_inching.setValue(0)
        self.sl_inching.setTickPosition(QSlider.TicksBelow)
#        self.sl_inching.setTickInterval(int(180/4))
        self.sl_inching.setTickInterval(60)
        self.sl_inching.setSingleStep(5)
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
        self.btn_inchingstart.setMinimumWidth(btn_width); self.btn_inchingstart.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_inchingstart, row+4,1)
#        layout.addWidget(QLabel(''), row,1)
              
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

        self.cbox_settareload = QPushButton("Reset tare load")
        self.cbox_settareload.clicked.connect(self.clicked_resettareload)
        layout.addWidget(self.cbox_settareload)

        
        self.btn_screenshot = QPushButton("Screenshot")
        self.btn_screenshot.clicked.connect(self.take_screenshot)
        layout.addWidget(self.btn_screenshot)

        layout.addWidget(self.MakeStateBox('run_time', 'Run time',                 initstr))
        layout.addWidget(self.MakeStateBox('run_startdepth', 'Start depth (m)',    initstr))
        layout.addWidget(self.MakeStateBox('run_deltadepth', 'Delta depth (m)',    initstr))
        layout.addWidget(self.MakeStateBox('run_startload',  'Start load (kg)',    initstr))
        layout.addWidget(self.MakeStateBox('motor_tachometer', 'Tachometer (rev)', initstr))

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

    def create_gb_status(self):
        self.gb_status = QGroupBox("Status")
        layout = QGridLayout()
        self.status_drill        = QLabel('Offline')
        self.status_loadcell     = QLabel('Offline')
        self.status_depthcounter = QLabel('Offline')
        layout.addWidget(QLabel('Drill:'),1,1)
        layout.addWidget(QLabel('Load cell:'),2,1)
        layout.addWidget(QLabel('Winch enc.:'),3,1)
        layout.addWidget(self.status_drill,1,2)
        layout.addWidget(self.status_loadcell,2,2)
        layout.addWidget(self.status_depthcounter,3,2)
        layout.rowStretch(1)
        self.gb_status.setLayout(layout)

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
        
    def clicked_resettacho(self):
        self.ds.set_tacho(0)
        
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

    # Plot control
    
    def changed_xaxislen_speed(self, idx):
        self.xlen_selector['speed'] = idx #self.cb_xaxislen_speed.currentIndex()
        self.plot_speed.setXRange(0, self.xlen[self.xlen_selector['speed']]/60*1.01, padding=0)

    def changed_xaxislen_load(self, idx):
        self.xlen_selector['load'] = idx #self.cb_xaxislen_load.currentIndex()
        self.plot_load.setXRange(0, self.xlen[self.xlen_selector['load']]/60*1.01, padding=0)
        
    def changed_xaxislen_current(self, idx):
        self.xlen_selector['current'] = idx #self.cb_xaxislen_current.currentIndex()
        self.plot_current.setXRange(0, self.xlen[self.xlen_selector['current']]/60*1.01, padding=0)
        
    def changed_loadmeasure(self):
        loadmeasure = self.cb_loadmeasure.currentText()
        if loadmeasure == 'Load':         self.loadmeasure_inuse = 'hist_load'
        if loadmeasure == 'Load - cable': self.loadmeasure_inuse = 'hist_loadnet'
        if loadmeasure == 'Tare load':    self.loadmeasure_inuse = 'hist_loadtare'

    # Logging/run-status panel
    
    def clicked_startstop_run(self):
        if self.btn_startrun.isChecked(): # start pressed
            self.btn_startrun.setText('Stop')
            self.btn_startrun.setStyleSheet("background-color : %s"%(COLOR_RED))
            self.runtime0 = datetime.datetime.now()
            self.ss.set_depthtare(self.ss.depth)
            self.ds.set_tacho(0)
#            self.clicked_resettareload() 
        else:
            self.btn_startrun.setText('Start')
            self.btn_startrun.setStyleSheet("background-color : %s"%(COLOR_GREEN))
#            self.ss.set_depthtare(self.ss.depth)
    
    def take_screenshot(self):
        fname = '%s/%s.png'%(PATH_SCREENSHOT, datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
        command = 'scrot "%s"'%(fname)
        os.system(command)
        print('Saving screenshot to %s'%(fname))
    
    def clicked_resettareload(self):
        loadtare_new = self.ss.load
        print('Setting tare load to %.2f'%(loadtare_new))
        self.hist_loadtare += self.ss.loadtare
        self.hist_loadtare -= loadtare_new
        self.ss.set_loadtare(loadtare_new)
        
    # Other
    
    def clicked_showhide_bno055(self):
        self.SHOW_BNO055_DETAILED = self.cb_show_bno055.isChecked()
        if self.SHOW_BNO055_DETAILED: self.gb_BNO055.show()
        else:                         self.gb_BNO055.hide()

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
        lbl.setText(str(value) if not isinstance(value, list) else ', '.join(value))
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
        self.hist_speed = np.roll(self.hist_speed, -1); self.hist_speed[-1] = abs(self.ss.speed)
        sel = self.xlen_selector['speed']
        I0 = -int(self.xlen[sel]/DT)
        x = self.hist_time[ I0:len(self.hist_time):self.xlen_samplerate[sel]]
        y = self.hist_speed[I0:len(self.hist_time):self.xlen_samplerate[sel]]
        self.curve_speed.setData(x=x, y=y)
        self.plot_speed.setYRange(0, np.amax([self.minYRange_speed, np.amax(y)*1.075]), padding=0.02)
        
        self.hist_load     = np.roll(self.hist_load,  -1);     self.hist_load[-1]     = self.ss.load
        self.hist_loadtare = np.roll(self.hist_loadtare,  -1); self.hist_loadtare[-1] = self.ss.load - self.ss.loadtare
        self.hist_loadnet  = np.roll(self.hist_loadnet,  -1);  self.hist_loadnet[-1]  = self.ss.loadnet
        hist_loadmeas = getattr(self,self.loadmeasure_inuse)
        sel = self.xlen_selector['load']
        I0 = -int(self.xlen[sel]/DT)
        x = self.hist_time[I0:len(self.hist_time):self.xlen_samplerate[sel]]
        y = hist_loadmeas[ I0:len(self.hist_time):self.xlen_samplerate[sel]]
        self.curve_load.setData(x=x,y=y)

        self.plot_load.setTitle(   self.htmlfont('<b>%s = %.1f kg'%(self.loadmeasures[self.loadmeasure_inuse], hist_loadmeas[-1]), FS_GRAPH_TITLE))
        self.plot_speed.setTitle(  self.htmlfont('<b>|Avg. speed| = %.1f cm/s'%(self.hist_speed[-1]), FS_GRAPH_TITLE))        
        self.plot_current.setTitle(self.htmlfont('<b>Current = %.1f A'%(self.ds.motor_current), FS_GRAPH_TITLE))

        self.depthbar.setValue(self.ss.depth, self.ss.depthtare)
        self.lbl_depthbar.setText(self.htmlfont('<b>Depth<br>%0.1fm'%(self.ss.depth), FS_GRAPH_TITLE))

        ### Update state fields
        self.updateStateBox('surface_depth',           round(self.ss.depth,PRECISION_DEPTH),  warn__nothres)  # precision to match physical display
        self.updateStateBox('surface_speed',           round(self.ss.speedinst,2),            warn__velocity)
        self.updateStateBox('surface_load',            round(self.ss.load,PRECISION_LOAD),    warn__load) # precision to match physical display
        self.updateStateBox('surface_loadcable',       round(self.ss.loadnet,PRECISION_LOAD), warn__nothres)
        self.updateStateBox('surface_downholevoltage', round(self.ds.downhole_voltage,1),     warn__downholevoltage)
        self.updateStateBox('run_peakload',            round(np.amax(self.hist_load),PRECISION_LOAD), warn__nothres)
        self.updateStateBox('run_deltaload',           round(self.ss.load  - self.ss.loadtare,PRECISION_LOAD),   warn__nothres)
                
        if self.btn_startrun.isChecked(): 
            self.runtime1 = datetime.datetime.now() # update run time
            if self.runtime0 is not None:
                druntime = self.runtime1-self.runtime0
                self.updateStateBox('run_time',       self.timestamp(druntime),                                 warn__nothres)
                self.updateStateBox('run_startdepth', round(self.ss.depthtare,PRECISION_DEPTH),                 warn__nothres)    
                self.updateStateBox('run_startload',  round(self.ss.loadtare,PRECISION_LOAD),                   warn__nothres)    
                self.updateStateBox('run_deltadepth', round(self.ss.depth - self.ss.depthtare,PRECISION_DEPTH), warn__corelength)    
                

        #-----------------------
        # Update drill state
        #-----------------------
        
        if self.Nt % DTFRAC_DRILL == 0:

            self.ds.update()

            ### Update graphs
            self.hist_current  = np.roll(self.hist_current,  -1); self.hist_current[-1]  = self.ds.motor_current
            sel = self.xlen_selector['current']
            I0 = -int(self.xlen[sel]/(DT*DTFRAC_DRILL))
            x = self.hist_time_drill[I0:len(self.hist_time_drill):self.xlen_samplerate[sel]]
            y = self.hist_current[   I0:len(self.hist_time_drill):self.xlen_samplerate[sel]]
            self.curve_current.setData(x=x,y=y)

            ### Check components statuses
            self.status_drill.setText('Online' if self.ds.islive else 'Offline')
            if self.ds.islive: self.status_drill.setStyleSheet("font-weight: normal; color: %s;"%(COLOR_DARKGREEN))
            else:              self.status_drill.setStyleSheet("font-weight: normal; color: %s;"%(COLOR_DARKRED))
            self.status_loadcell.setText('Online' if self.ss.islive_loadcell else 'Offline')
            if self.ss.islive_loadcell: self.status_loadcell.setStyleSheet("font-weight: normal; color: %s;"%(COLOR_DARKGREEN))
            else:                       self.status_loadcell.setStyleSheet("font-weight: normal; color: %s;"%(COLOR_DARKRED))
            self.status_depthcounter.setText('Online' if self.ss.islive_depthcounter else 'Offline')
            if self.ss.islive_depthcounter: self.status_depthcounter.setStyleSheet("font-weight: normal; color: %s;"%(COLOR_DARKGREEN))
            else:                           self.status_depthcounter.setStyleSheet("font-weight: normal; color: %s;"%(COLOR_DARKRED))


            if self.ds.islive or ALWAYS_SHOW_DRILL_FIELDS:
               
                ### Update state fields
                str_incvec   = '[%.1f, %.1f]'%(self.ds.inclination_x,self.ds.inclination_x)
                self.updateStateBox('orientation_inclination',  round(self.ds.inclination,1), warn__nothres)
                self.updateStateBox('orientation_azimuth',      round(self.ds.azimuth,1),     warn__nothres)
                self.updateStateBox('orientation_spin',         round(self.ds.spin,1),        warn__spin)
                if USE_BNO055_FOR_ORIENTATION:
                    str_drilldir = '[%.2f, %.2f, %.2f]'%(self.ds.drilldir[0],self.ds.drilldir[1],self.ds.drilldir[2])
                    self.updateStateBox('orientation_drilldir', str_drilldir,  warn__nothres)
                    if self.SHOW_BNO055_DETAILED:
    #                    str_quat = '[%.1f, %.1f, %.1f, %.1f]'%(self.ds.quat[0],self.ds.quat[1],self.ds.quat[2],self.ds.quat[3])
    #                    self.updateStateBox('orientation_quat',         str_quat,   warn__nothres)
                        str_aclvec   = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.accelerometer_x,self.ds.accelerometer_y,self.ds.accelerometer_z, self.ds.accelerometer_magnitude)
                        str_magvec   = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.magnetometer_x,self.ds.magnetometer_y,self.ds.magnetometer_z, self.ds.magnetometer_magnitude)
                        str_spnvec   = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.gyroscope_x,self.ds.gyroscope_y,self.ds.gyroscope_z, self.ds.gyroscope_magnitude)
                        self.updateStateBox('orientation_acceleration', str_aclvec, warn__nothres)
                        self.updateStateBox('orientation_magnetometer', str_magvec, warn__nothres)
                        self.updateStateBox('orientation_gyroscope',    str_spnvec, warn__nothres)
                else:
                    self.updateStateBox('orientation_inclinometer', str_incvec,          warn__nothres)

                self.updateStateBox('pressure_electronics', round(self.ds.pressure_electronics,1), warn__pressure)
                self.updateStateBox('pressure_topplug',     round(self.ds.pressure_topplug,1),     warn__pressure)
                self.updateStateBox('pressure_gear1',       (round(self.ds.pressure_gear1,1),round(self.ds.pressure_gear2,1)), warn__pressure)
#                self.updateStateBox('pressure_gear2',       round(self.ds.pressure_gear2,1),       warn__pressure)
                self.updateStateBox('hammer',               round(self.ds.hammer,1),               warn__hammer)

                self.updateStateBox('temperature_topplug',        round(self.ds.temperature_topplug,1),        warn__temperature_electronics)
                self.updateStateBox('temperature_gear1',          (round(self.ds.temperature_gear1,1), round(self.ds.temperature_gear1,1)), warn__temperature_electronics)
#                self.updateStateBox('temperature_gear2',          round(self.ds.temperature_gear1,1),          warn__temperature_electronics)
                self.updateStateBox('temperature_electronics',    (round(self.ds.temperature_electronics,1),round(self.ds.temperature_auxelectronics,1)), warn__temperature_electronics)
#                self.updateStateBox('temperature_electronics',    round(self.ds.temperature_electronics,1),    warn__temperature_electronics)
#                self.updateStateBox('temperature_auxelectronics', round(self.ds.temperature_auxelectronics,1), warn__temperature_electronics)
                self.updateStateBox('temperature_motor',          round(self.ds.temperature_motor,1),          warn__temperature_motor)    
                self.updateStateBox('temperature_motorctrl',      round(self.ds.motor_controller_temp,1),      warn__temperature_motor)    
                
                self.updateStateBox('motor_current',    round(self.ds.motor_current,1),  warn__motor_current)
                self.updateStateBox('motor_speed',      round(self.ds.motor_rpm,1),      warn__motor_rpm)    
                self.updateStateBox('motor_voltage',    round(self.ds.motor_voltage,1),  warn__nothres)    
                self.updateStateBox('motor_throttle',   round(self.ds.motor_throttle,0), warn__nothres)
                self.updateStateBox('motor_tachometer', round(self.ds.tachometer*TACHO_PRE_REV,2), warn__nothres)
        
        ### Disabled widgets if drill state is dead
        
        if not ALWAYS_SHOW_DRILL_FIELDS:
            self.gb_orientation.setEnabled(self.ds.islive)
            self.gb_pressure.setEnabled(self.ds.islive)
            self.gb_temperature.setEnabled(self.ds.islive)
            self.gb_surface_downholevoltage.setEnabled(self.ds.islive)

        self.gb_motor.setEnabled(self.ds.islive)
        self.gb_expert.setEnabled(self.ds.islive)

        ### Disabled widgets if winch encoder is dead

        for f in ['gb_surface_depth','gb_surface_speed']:
            lbl = getattr(self, f)
            lbl.setEnabled(self.ss.islive_loadcell)
                        
        ### Disabled widgets if load cell is dead
                        
        for f in ['gb_surface_load','gb_surface_loadcable','gb_run_peakload']:
            lbl = getattr(self, f)
            lbl.setEnabled(self.ss.islive_depthcounter)
            
        
        ### END
                    
        self.Nt += 1
        
    def timestamp(self, turnaround):
        total_seconds = int(turnaround.total_seconds())
        hours, remainder = divmod(total_seconds,60*60)
        minutes, seconds = divmod(remainder,60)
        return "%02i:%02i:%02i"%(hours,minutes,seconds)
        
    def htmlfont(self, text,fsize, color='#000000'): return '<font size="%i" color="%s">%s</font>'%(fsize,color,text)
        

class DepthProgressBar(QWidget):

    def __init__(self, iceThickness):
        super().__init__()

        self.minval = 0 # min depth
        self.maxval = iceThickness # max depth (bedrock)
        self.iceval = self.maxval*2/3 # ice depth (last max drilling depth)
        self.curval = self.maxval*1/3 # current drill depth (position)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding
        )

    def sizeHint(self):
        return QtCore.QSize(80,300)
        
    def setValue(self, currentDepth, iceDepth):
        self.curval = currentDepth
        self.iceval = iceDepth
        self.repaint()

    def paintEvent(self, e):
        painter = QtGui.QPainter(self)

        c_ice   = '#6baed6'
        c_icehatch = '#252525' # 737373
        c_fluid = COLOR_GRAYBG 
        c_drill = '#252525'
        
        H, W = painter.device().height(), painter.device().width()

        ### backgorund (fluid)
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor(c_fluid))
        brush.setStyle(Qt.SolidPattern)
        rect = QtCore.QRect(0, 0, W, H)
        painter.fillRect(rect, brush)
        
        ### undrilled ice
        ystart_ice = self.maxval
        yend_ice   = int(self.iceval/self.maxval * painter.device().height()) # in px
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor(c_ice))
        brush.setStyle(Qt.SolidPattern)
        rect = QtCore.QRect(0, ystart_ice, W, yend_ice-ystart_ice)
        painter.fillRect(rect, brush)
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor(c_icehatch))
        brush.setStyle(Qt.BDiagPattern)
        painter.fillRect(rect, brush)
        
        ### drill position
        cablewidth = int(0.75/10*W)
        drillwidth = int(7/10*W)
        drillheight = int(1.5/10 * H) # in px
        y_drill = int(self.curval/self.maxval * H) # in px
        xc = int(W/2)
        # cable
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor(c_drill))
        brush.setStyle(Qt.SolidPattern)
        rect = QtCore.QRect(xc-int(cablewidth/2), 0, cablewidth, y_drill)
        painter.fillRect(rect, brush)
        # dirll
        rect = QtCore.QRect(xc-int(drillwidth/2), y_drill-drillheight, drillwidth, drillheight)
        painter.fillRect(rect, brush)
        
        ### Walls
        painter.setBrush(Qt.black)
        painter.setPen(QtGui.QPen(Qt.black, 4, Qt.SolidLine))
        painter.drawLine(0,0,0,H)
        painter.drawLine(W,0,W,H)
        painter.drawLine(0,H,W,H)
        painter.drawLine(0,0,W,0)
        
        painter.end()

    def _trigger_refresh(self):
        self.update()
        
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
