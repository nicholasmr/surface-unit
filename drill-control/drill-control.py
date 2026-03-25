#!/usr/bin/python
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2017-

import sys, os, signal, datetime
import numpy as np
import random
from functools import partial

from settings import *
from state_drill import *
from state_surface import *

from PyQt5.QtCore import * 
from PyQt5.QtWidgets import * 
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

#import qwt # https://pypi.org/project/PythonQwt/
import pyqtgraph as pg

"""
Settings
"""

### GUI update rate

DT     = 1/8 # GUI update rate in seconds
DTFRAC = 3 # update the drill state every DTFRAC times the GUI/surface state is updated

tavg = 3 # time averaging length in seconds for velocity estimate

print('%s: running with DT=%.3fs, DT_DRILL=%.3fs'%(sys.argv[0], DT, DT*DTFRAC))

### Flags

ALWAYS_SHOW_DRILL_FIELDS = True # show last recorded redis fields for drill even though it is offline
ENABLE_SOUNDS            = False

### Screenshots

PATH_SCREENSHOT = "/mnt/logs/screenshots"
os.system('mkdir -p %s'%(PATH_SCREENSHOT))

### GUI style

FS       = 13
FS_TITLE = 5 # graph title

COLOR_GRAYBG    = '#f0f0f0'
COLOR_GREEN     = '#66bd63'
COLOR_RED       = '#f4a582'
COLOR_DARKRED   = '#b2182b'
COLOR_DARKGREEN = '#1a9850'

COLOR_DIAL1  = '#01665e'
COLOR_DIAL1l = '#c7eae5'
COLOR_DIAL2  = '#8c510a'
COLOR_DIAL2l = '#dfc27d'

COLOR_SLOT0 = '#3182bd'
COLOR_SLOT1 = '#969696'

### Keyboard shortcuts

sc_startdrill = "Ctrl+Return"
sc_stopdrill  = "Ctrl+Backspace"
sc_startrun   = "Ctrl+Space"

"""
Main class
"""

class MainWidget(QWidget):

    runtime0 = None
    Nt       = 0 # number of time increments realized so far

    loadmeasures      = {'hist_load':'Load', 'hist_loadnet':'Load - cable', 'hist_loadtare':'Tare load'}
    loadmeasure_inuse = 'hist_load'

    xlen            = [int(0.5*60), int(2*60), int(10*60), int(45*60)] 
    xlen_names      = ["0.5m", "2m", "10m", "45m"]
    xlen_samplerate = [1,1,1,1]  
    xlen_selector   = {'speed':0, 'load':0, 'current':0, 'incl':2} # default selection
    
    minYRange_load  = 20 # kg
    minYRange_speed = 4 # cm/s
    maxYRange_speed = 150 # cm/s
    
    style_onoffline = ["font-weight: bold; color: %s;"%(COLOR_DARKRED), "font-weight: bold; color: %s;"%(COLOR_DARKGREEN)]
    
    def __init__(self, parent=None):
    
        super(MainWidget, self).__init__(parent)

        ### State objects

        self.ds = DrillState(redis_host=REDIS_HOST) # REDIS_HOST determined in settings file
        self.ss = SurfaceState(tavg, DT*DTFRAC,redis_host=REDIS_HOST)

        ### Sound clips
        
        self.sound_startrun   = ["WC1_Human_acknowledge2.wav", "Luigi3.wav"]
        self.sound_stoprun    = ["WC1_Human_work_complete.wav", "0A - 000E Thank you so much.wav"]
        self.sound_inching    = ["WC1_Orc_select3.wav","Mario8.wav"]
        self.sound_startmotor = ["engine-rev-1.wav", "RunnerYes3.wav", "08 - 001A - Let's a go.wav", "08 - 000C - Here we go.wav"]
        self.sound_stopmotor  = ["WC1_Human_work_complete.wav","Mario10.wav","Mario11.wav"] 
        
        """
        BOXES
        """

        self.makebox_surface()
        self.makebox_orientation()
        self.makebox_temperature()
        self.makebox_pressure()
        self.makebox_other()
        self.makebox_motor()
        self.makebox_run()
        self.makebox_status()
        self.makebox_bno055calib()
        self.makebox_expert()
        
        """
        GRAPHS
        """

        pg.setConfigOptions(background=COLOR_GRAYBG) # gray
        pg.setConfigOptions(foreground='k')

        self.hist_time       = np.flipud(np.arange(0, self.xlen[-1]/60 +1e-9, DT/60))
        self.hist_time_drill = np.flipud(np.arange(0, self.xlen[-1]/60 +1e-9, DT*DTFRAC/60))
        self.hist_load       = np.full(len(self.hist_time), 0.0)
        self.hist_loadnet    = np.full(len(self.hist_time), 0.0)
        self.hist_loadtare   = np.full(len(self.hist_time), 0.0)
        self.hist_speed      = np.full(len(self.hist_time), 0.0)
        self.hist_current    = np.full(len(self.hist_time_drill), 0.0)
        self.hist_depth      = np.full(len(self.hist_time_drill), 0.0)
        self.hist_incl       = np.full(len(self.hist_time_drill), 0.0)
        
        # debug profile
        #self.hist_depth     = np.linspace(0.3,0,len(self.hist_time_drill)) 
        #self.hist_incl_ahrs = np.linspace(-5,0,len(self.hist_time_drill)) 

        ### Set up axes

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

        self.plot_load    = pg.PlotWidget(); 
        self.plot_speed   = pg.PlotWidget(); 
        self.plot_current = pg.PlotWidget(); 
        
        setupaxis(self.plot_load);
        setupaxis(self.plot_speed);
        setupaxis(self.plot_current);

        self.plot_load.setLimits(minYRange=self.minYRange_load) # minimum y-axis span for load (prevent aggressive auto zoom)
        self.plot_current.setYRange(0, warn__motor_current[1]*1.2, padding=0.02)

        self.plot_incl = pg.PlotWidget();  
        self.plot_incl.setXRange(0, 8, padding=0)
        self.plot_incl.setYRange(3, 0, padding=0)
        self.plot_incl.invertY()
        self.plot_incl.showAxis('right')
        self.plot_incl.showAxis('top')      
        self.plot_incl.setMenuEnabled(False)
        self.plot_incl.setMouseEnabled(x=False, y=False)  
        self.plot_incl.setLabel('right', "Depth (km)") 
        self.plot_incl.setLabel('bottom', "Inclination (deg.)")
        self.plot_incl.showGrid(y=True,x=True)
        self.plot_incl.getAxis('left').setGrid(False)
        self.plot_incl.getAxis('bottom').setGrid(False)
        for ax in ['left', 'top']:
            self.plot_incl.showAxis(ax)
            self.plot_incl.getAxis(ax).setStyle(showValues=False)

        ### Initial plots
        
        plotpen_black = pg.mkPen(color='k', width=3)
        self.curve_load    = self.plot_load.plot(x=self.hist_time, y=self.hist_time*0-1e4, pen=plotpen_black)
        self.curve_speed   = self.plot_speed.plot(x=self.hist_time, y=self.hist_time*0-1e4, pen=plotpen_black)
        self.curve_current = self.plot_current.plot(x=self.hist_time_drill,y=self.hist_time_drill*0-1e4, pen=plotpen_black)

        self.incl_scatter = pg.ScatterPlotItem(size=8, pen=None, brush=pg.mkBrush(0,0,0))
        self.plot_incl.addItem(self.incl_scatter)

        """
        Build QT layout
        """

        ### TOP (GRAPHS)

        w_btn, s_btn = 60, 15
       
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

        depthbarLayout = QVBoxLayout()
        self.lbl_depthbar = QLabel(self.htmlfont('Depth', FS_TITLE))
        self.lbl_depthbar.setAlignment(QtCore.Qt.AlignCenter)
        depthbarLayout.addWidget(self.lbl_depthbar)
        depthbarLayoutInner = QHBoxLayout()
        depthbarLayoutInner.addStretch(1)
        self.depthbar = DepthProgressBar()
        depthbarLayoutInner.addWidget(self.depthbar)
        depthbarLayoutInner.addStretch(1)
        depthbarLayoutInner.setContentsMargins(20, 0, 25, 0)
        depthbarLayout.addLayout(depthbarLayoutInner)

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
                
        plotLayout4 = QVBoxLayout() 
        plotLayout4.addWidget(self.plot_incl)
        plotLayout4btn = QHBoxLayout()
        plotLayout4btn.setSpacing(s_btn)
        plotLayout4btn.addStretch(1)
        incl_xlen_btn1 = QPushButton(self.xlen_names[0]); incl_xlen_btn1.clicked.connect(lambda: self.changed_xaxislen_incl(0)); incl_xlen_btn1.setMaximumWidth(w_btn); plotLayout4btn.addWidget(incl_xlen_btn1)
        incl_xlen_btn3 = QPushButton(self.xlen_names[2]); incl_xlen_btn3.clicked.connect(lambda: self.changed_xaxislen_incl(2)); incl_xlen_btn3.setMaximumWidth(w_btn); plotLayout4btn.addWidget(incl_xlen_btn3)
        incl_xlen_btn4 = QPushButton(self.xlen_names[3]); incl_xlen_btn4.clicked.connect(lambda: self.changed_xaxislen_incl(3)); incl_xlen_btn4.setMaximumWidth(w_btn); plotLayout4btn.addWidget(incl_xlen_btn4)
        plotLayout4btn.addStretch(2)
        plotLayout4.addLayout(plotLayout4btn)

        topLayout.addLayout(plotLayout1,1)
        topLayout.addLayout(depthbarLayout,0)
        topLayout.addLayout(plotLayout2,3)
        topLayout.addLayout(plotLayout3,1)
        topLayout.addLayout(plotLayout4,1)

        ### BOTTOM (SURFACE + DRILL STATE FIELDS)
        
        botLayout = QHBoxLayout()
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
        botLayoutSub2.addWidget(self.gb_bno005calib)
        botLayoutSub2.addWidget(self.gb_expert)
        botLayout.addLayout(botLayoutSub2)
        botLayout.addStretch(1)
        
        ### MAIN LAYOUT
        
        mainLayout = QVBoxLayout()
        mainLayout.addLayout(topLayout, 1)
        mainLayout.addWidget(QLabel(''), 0) # spacer
        mainLayout.addLayout(botLayout, 0)
        self.setLayout(mainLayout)
        self.setWindowTitle("Drill Control Panel")

        
    def randsound(self, arr):
    
        script_path = os.path.abspath(__file__)
        script_directory = os.path.dirname(script_path)
        if ENABLE_SOUNDS: return QSound.play('%s/sound/%s'%(script_directory, random.choice(arr)))
        
        
    def makebox_surface(self, initstr='N/A'):
    
        self.gb_surface_load      = self.makestatebox('surface_load',      'Load (kg)',            initstr)
        self.gb_surface_depth     = self.makestatebox('surface_depth',     'Depth (m)',            initstr)
        self.gb_surface_speed     = self.makestatebox('surface_speed',     'Inst. speed (cm/s)',   initstr)
        self.gb_surface_loadcable = self.makestatebox('surface_loadcable', 'Load - cable (kg)',    initstr)
        self.gb_run_deltaload     = self.makestatebox('run_deltaload',     'Tare load (kg)',       initstr)
        self.gb_run_peakload      = self.makestatebox('run_peakload',      'Peak load (kg)',       initstr)
        self.gb_run_corelength    = self.makestatebox('run_corelength',    'Core len. disp. (m)',  initstr)

        layout = QVBoxLayout()
        layout.addWidget(self.gb_surface_depth)
        layout.addWidget(self.gb_surface_speed)
        layout.addWidget(self.gb_surface_load)
        layout.addWidget(self.gb_surface_loadcable)
        layout.addWidget(self.gb_run_deltaload)
        layout.addWidget(self.gb_run_peakload)
        layout.addWidget(self.gb_run_corelength)
        layout.addStretch(1)

        self.gb_surface = QGroupBox("Surface")        
        self.gb_surface.setLayout(layout)


    def makebox_orientation(self, initstr='N/A'):
    
        self.gb_orientation = QGroupBox("Orientation (deg)")
#        self.gb_orientation.setMinimumWidth(330)
        layout = QVBoxLayout()

        dlayout = QGridLayout()
        dlayout.addWidget(self.makestatebox('orientation_inclination',      'Incl., Roll (BNO)',  initstr), 1,1)
        dlayout.addWidget(self.makestatebox('orientation_inclination_alt',  'Incl., Roll (alt)',  initstr), 1,2)

        cdial = dict(dial_roll=COLOR_DIAL1, dial_roll_alt=COLOR_DIAL2)
        for tt in ['dial_roll','dial_roll_alt']:
            d = QDial()
            d.setNotchesVisible(True)
            d.setMinimum(-180)
            d.setMaximum(+180)
            d.setWrapping(True)
            d.setMinimumHeight(110)
            d.setMaximumHeight(150)
            d.setInvertedAppearance(True)
            d.setInvertedControls(True)
            d.setStyleSheet("background-color: %s; border : 2px solid black;"%(cdial[tt]));
            setattr(self, tt, d)
        dlayout.addWidget(self.dial_roll,     2,1)
        dlayout.addWidget(self.dial_roll_alt, 2,2)
        lbl1 = QLabel('slow response,\nhigh accuracy')
        lbl2 = QLabel('fast response,\nlow accuracy')
        lbl1.setAlignment(Qt.AlignCenter)
        lbl2.setAlignment(Qt.AlignCenter)
        dlayout.addWidget(lbl1, 3,1)
        dlayout.addWidget(lbl2, 3,2)
        layout.addLayout(dlayout)

        layout.addWidget(QLabel(''))
        layout.addWidget(self.makestatebox('orientation_gravity',      'Gravity (m/s^2)',     initstr))
        layout.addWidget(self.makestatebox('orientation_acceleration', 'Acceleration (m/s^2)', initstr))
        layout.addWidget(self.makestatebox('orientation_magnetometer', 'Magnetometer (mT)',    initstr))   
#        layout.addWidget(self.makestatebox('orientation_gyroscope',    'Gyroscope (deg/s)',    initstr))
#        layout.addWidget(self.makestatebox('orientation_linearacceleration', 'Linear accel. (m/s^2)', initstr))
#        layout.addWidget(self.makestatebox('orientation_inclinometer',       'Inclinometer (...)',  initstr))
        
        layout.addStretch(1)
        self.gb_orientation.setLayout(layout)
        
        
    def makebox_pressure(self, initstr='N/A'):
    
        self.gb_pressure = QGroupBox("Pressure (mbar)")
        layout = QVBoxLayout()
        layout.addWidget(self.makestatebox('pressure_gear1',       'Gear 1, 2',      initstr))
        layout.addWidget(self.makestatebox('pressure_electronics', 'Electronics', initstr))
        layout.addWidget(self.makestatebox('pressure_topplug',     'Top plug',    initstr))
        layout.addStretch(1)
        self.gb_pressure.setLayout(layout)


    def makebox_other(self, initstr='N/A'):
    
        self.gb_other = QGroupBox("Other")
        layout = QVBoxLayout()
        layout.addWidget(self.makestatebox('hammer', 'Hammer (%)', initstr))
        layout.addWidget(self.makestatebox('orientation_spin', 'Drill spin (RPM)',   initstr))
        self.gb_surface_downholevoltage = self.makestatebox('surface_downholevoltage', 'Downhole volt. (V)',   initstr)
        layout.addWidget(self.gb_surface_downholevoltage)
        layout.addStretch(1)
        self.gb_other.setLayout(layout)


    def makebox_temperature(self, initstr='N/A'):
    
        self.gb_temperature = QGroupBox("Temperature (C)")
        layout = QVBoxLayout()
        layout.addWidget(self.makestatebox('temperature_gear1',       'Gear 1, 2',         initstr))
        layout.addWidget(self.makestatebox('temperature_electronics', 'Electronics, Aux.', initstr))
        layout.addWidget(self.makestatebox('temperature_topplug',     'Top plug',          initstr))
        layout.addWidget(self.makestatebox('temperature_motor',       'Motor',             initstr))
        layout.addWidget(self.makestatebox('temperature_motorctrl',   'Motor ctrl (VESC)', initstr))
        layout.addStretch(1)
        self.gb_temperature.setLayout(layout)
        
        
    def makebox_motor(self, initstr='N/A', btn_width=150):
    
        ### State
    
        self.gb_motor = QGroupBox("Motor")
        layout = QGridLayout()
        layout.addWidget(self.makestatebox('motor_current',  'Current (A)',  initstr), 1,1)
        layout.addWidget(self.makestatebox('motor_speed',    'Speed (RPM)',  initstr), 1,2)
        layout.addWidget(self.makestatebox('motor_voltage',  'Voltage (V)',  initstr), 2,1)
        layout.addWidget(self.makestatebox('motor_throttle', 'Throttle (%)', initstr), 2,2)

        ### Throttle

        row = 3
        layout.addWidget(QHSeparationLine(), row, 1, 1,2)
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
        
        self.btn_motorstart = QPushButton("Start")
        self.btn_motorstart.setStyleSheet("font-weight: bold; background-color : %s"%(COLOR_GREEN))
        self.btn_motorstart.clicked.connect(self.clicked_motorstart)
        self.btn_motorstart.setShortcut(sc_startdrill)
        self.btn_motorstart.setMinimumWidth(btn_width); self.btn_motorstart.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_motorstart, row+4,1)
        
        self.btn_motorstop = QPushButton("Stop")
        self.btn_motorstop.setStyleSheet("font-weight: bold; background-color : %s"%(COLOR_RED))
        self.btn_motorstop.clicked.connect(self.clicked_motorstop)
        self.btn_motorstop.setShortcut(sc_stopdrill)
        self.btn_motorstop.setMinimumWidth(btn_width);  self.btn_motorstop.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_motorstop,  row+4,2)
        
        ### Inching
        
        row += 5
        layout.addWidget(QHSeparationLine(), row, 1, 1,2)   
        
        dlayout = QGridLayout()
        mw = 50
        cfwd, crev = '#e08214', '#8073ac'
        
        b = QPushButton("-180")
        b.clicked.connect(self.clicked_inching_m180)
        b.setMaximumWidth(mw)
        b.setStyleSheet("font-weight: bold; background-color : %s"%(crev))
        dlayout.addWidget(b, 0,1)
              
        b = QPushButton("-60")
        b.clicked.connect(self.clicked_inching_m60)
        b.setMaximumWidth(mw)
        b.setStyleSheet("font-weight: bold; background-color : %s"%(crev))
        dlayout.addWidget(b, 0,2)
        
        b = QPushButton("-10")
        b.clicked.connect(self.clicked_inching_m10)
        b.setMaximumWidth(mw)
        b.setStyleSheet("font-weight: bold; background-color : %s"%(crev))
        dlayout.addWidget(b, 0,3)
              
        b = QPushButton("+10")
        b.clicked.connect(self.clicked_inching_p10)
        b.setMaximumWidth(mw)
        b.setStyleSheet("font-weight: bold; background-color : %s"%(cfwd))
        dlayout.addWidget(b, 0,4)
              
        b = QPushButton("+60")
        b.clicked.connect(self.clicked_inching_p60)
        b.setMaximumWidth(mw)
        b.setStyleSheet("font-weight: bold; background-color : %s"%(cfwd))
        dlayout.addWidget(b, 0,5)
        
        b = QPushButton("+180")
        b.clicked.connect(self.clicked_inching_p180)
        b.setMaximumWidth(mw)
        b.setStyleSheet("font-weight: bold; background-color : %s"%(cfwd))
        dlayout.addWidget(b, 0,6)
              
        layout.addLayout(dlayout,row+5, 1, 1, 2)
        
        row += 6
        layout.addWidget(QHSeparationLine(), row, 1, 1,2)
        self.sl_inching_label = QLabel('Inching: 0 deg')
        layout.addWidget(self.sl_inching_label, row+1,1)
        self.sl_inching = QSlider(Qt.Horizontal)
        self.sl_inching.setMinimum(-360)
        self.sl_inching.setMaximum(+360)
        self.sl_inching.setValue(0)
        self.sl_inching.setTickPosition(QSlider.TicksBelow)
        self.sl_inching.setTickInterval(60)
        self.sl_inching.setSingleStep(5)
        self.sl_inching.valueChanged.connect(self.changed_sl_inching)
        layout.addWidget(self.sl_inching, row+2,1, 1,1)

        self.btn_inchingstart = QPushButton("Start")
        self.btn_inchingstart.setStyleSheet("background-color : %s"%(COLOR_GREEN))
        self.btn_inchingstart.clicked.connect(self.clicked_inchingstart)
        self.btn_inchingstart.setMinimumWidth(btn_width); self.btn_inchingstart.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_inchingstart, row+4,1)

        default_inchingthrottle = 10
        self.sl_inchingthrottle_label = QLabel('Inching throttle: %i%%'%(default_inchingthrottle))
        layout.addWidget(self.sl_inchingthrottle_label, row+1, 2)
        self.sl_inchingthrottle = QSlider(Qt.Horizontal)
        self.sl_inchingthrottle.setMinimum(0)
        self.sl_inchingthrottle.setMaximum(20)
        self.sl_inchingthrottle.setValue(default_inchingthrottle) 
        self.sl_inchingthrottle.setTickPosition(QSlider.TicksBelow)
        self.sl_inchingthrottle.setTickInterval(5)
        self.sl_inchingthrottle.valueChanged.connect(self.changed_inchingthrottle) 
        layout.addWidget(self.sl_inchingthrottle, row+2,2)

        ### Add to layout
        
        layout.setRowStretch(row+5, 1)
        self.gb_motor.setLayout(layout)
        
        
    def makebox_run(self, initstr='N/A', btn_width=150):
    
        self.gb_run = QGroupBox("Current run")
        layout = QVBoxLayout()
        
        self.btn_startrun = QPushButton("Start")
        self.btn_startrun.setCheckable(True)
        self.btn_startrun.clicked.connect(self.clicked_startstop_run)
        self.btn_startrun.setStyleSheet("font-weight: bold; background-color : %s"%(COLOR_GREEN))
        #self.btn_startrun.setMinimumWidth(btn_width); self.btn_startrun.setMaximumWidth(btn_width)
        self.btn_startrun.setShortcut(sc_startrun)
        layout.addWidget(self.btn_startrun)

        self.cbox_settareload = QPushButton("Tare load")
        self.cbox_settareload.clicked.connect(self.clicked_resettareload)
        #self.cbox_settareload.setMinimumWidth(btn_width); self.cbox_settareload.setMaximumWidth(btn_width)
        layout.addWidget(self.cbox_settareload)
        
        self.btn_screenshot = QPushButton("Screenshot")
        self.btn_screenshot.clicked.connect(self.take_screenshot)
        #self.btn_screenshot.setMinimumWidth(btn_width); self.btn_screenshot.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_screenshot)

        layout.addWidget(self.makestatebox('run_deltadepth', 'Delta depth (m)',    initstr))
        layout.addWidget(self.makestatebox('run_time', 'Run time',                 initstr))
        layout.addWidget(self.makestatebox('run_startdepth', 'Start depth (m)',    initstr))
        layout.addWidget(self.makestatebox('run_startload',  'Start load (kg)',    initstr))
        layout.addWidget(self.makestatebox('motor_tachometer', 'Tachometer (rev)', initstr))

        layout.addStretch(1)
        self.gb_run.setLayout(layout)


    def makebox_expert(self, initstr='N/A'):
    
        self.gb_expert = QGroupBox("Expert control")
        layout = QVBoxLayout()

        self.cbox_unlockexpert = QCheckBox("Unlock")
        self.cbox_unlockexpert.toggled.connect(self.clicked_unlockexpert)     
        layout.addWidget(self.cbox_unlockexpert)
        
        self.cb_motorconfig_label = QLabel('Motor config:')
        self.cb_motorconfig_label.setEnabled(False) # ***danger zone*** don't allow user to change this by disabling bottons
        layout.addWidget(self.cb_motorconfig_label)
        self.cb_motorconfig = QComboBox()
        self.cb_motorconfig.addItems(["parvalux", "skateboard", "hacker", "plettenberg"])
        self.cb_motorconfig.currentIndexChanged.connect(self.changed_motorconfig)
        self.cb_motorconfig.setEnabled(False)
        layout.addWidget(self.cb_motorconfig)

        layout.addStretch(3)
        self.gb_expert.setLayout(layout)


    def makebox_status(self):
    
        self.gb_status = QGroupBox("Status")
        layout = QGridLayout()
        self.status_drill        = QLabel('Offline')
        self.status_loadcell     = QLabel('Offline')
        self.status_depthcounter = QLabel('Offline')
        layout.addWidget(QLabel('Drill:'),1,1)
        layout.addWidget(QLabel('Load cell:'),2,1)
        layout.addWidget(QLabel('Depth enc:'),3,1)
        layout.addWidget(self.status_drill,1,2)
        layout.addWidget(self.status_loadcell,2,2)
        layout.addWidget(self.status_depthcounter,3,2)
        layout.rowStretch(2)
        self.gb_status.setLayout(layout)


    def makebox_bno055calib(self, initstr='N/A'):
    
        self.gb_bno005calib = QGroupBox("BNO055 calibration")
        layout = QGridLayout()

        btn_width = 70
        row = 0
        self.btn_savecalib = {}
        self.btn_loadcalib = {}
        
        for index in range(0,2):
            self.btn_loadcalib[index] = QPushButton("Load %i"%(index), parent=self)
            self.btn_loadcalib[index].setStyleSheet("background-color : %s"%(COLOR_SLOT0 if index==0 else COLOR_SLOT1))
            self.btn_loadcalib[index].clicked.connect(partial(self.clicked_loadcal, index))
            self.btn_loadcalib[index].setMaximumWidth(btn_width)
            layout.addWidget(self.btn_loadcalib[index], row, index)

            self.btn_savecalib[index] = QPushButton("Save %i"%(index), parent=self)
            self.btn_savecalib[index].setStyleSheet("background-color : %s"%(COLOR_SLOT0 if index==0 else COLOR_SLOT1))
            self.btn_savecalib[index].clicked.connect( partial(self.clicked_savecal, index))
            self.btn_savecalib[index].setMaximumWidth(btn_width)
            layout.addWidget(self.btn_savecalib[index], row+1, index)
            
        self.gb_bno005calib.setEnabled(False) # disable feature?
        self.gb_bno005calib.setLayout(layout)


    """ 
    USER ACTIONS 
    """
    
    ### Motor
    
    def changed_throttle(self):
    
        self.sl_throttle_label.setText('Throttle: %i%%'%(self.sl_throttle.value()))
        
        
    def changed_sl_inching(self):
    
        deg = self.sl_inching.value()
        self.sl_inching_label.setText('Inching: %+i deg'%(deg))
        
        
    def clicked_motorstart(self):
    
        throttle_pct = int(self.sl_throttle.value())
        self.ds.start_motor__throttle(throttle_pct)
        self.randsound(self.sound_startmotor)
        
        
    def clicked_inchingstart(self):
    
        deg = self.sl_inching.value()
        self.randsound(self.sound_inching)
        self.ds.start_motor__degrees(deg, throttle_pct=int(self.sl_inchingthrottle.value()))
        
        
    def start_inching(self, ang):
    
        self.randsound(self.sound_inching)
        self.ds.start_motor__degrees(ang, throttle_pct=int(self.sl_inchingthrottle.value()))


    def clicked_inching_p10(self):  self.start_inching(+10)
    def clicked_inching_p60(self):  self.start_inching(+60)
    def clicked_inching_p180(self): self.start_inching(+180)

    def clicked_inching_m10(self):  self.start_inching(-10)
    def clicked_inching_m60(self):  self.start_inching(-60)
    def clicked_inching_m180(self): self.start_inching(-180)
    
    
    def clicked_motorstop(self):
        self.ds.stop_motor()
        self.randsound(self.sound_stopmotor)
        
        
    def clicked_resettacho(self):
        self.ds.set_tacho(0)
        
        
    ### Expert control 
    
    def clicked_unlockexpert(self):
        unlocked = self.cbox_unlockexpert.isChecked()

        self.cb_motorconfig_label.setEnabled(unlocked)
        self.cb_motorconfig.setEnabled(unlocked)

        self.sl_inchingthrottle_label.setEnabled(unlocked)
        self.sl_inchingthrottle.setEnabled(unlocked)


    def changed_motorconfig(self): 
        self.ds.set_motorconfig(self.cb_motorconfig.currentIndex())


    def changed_inchingthrottle(self):
        self.sl_inchingthrottle_label.setText('Inching throttle: %i%%'%(self.sl_inchingthrottle.value()))


    def clicked_savecal(self, i):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Save BNO055 calibration?")
        dlg.setText("Are you sure you want to overwrite slot #%i?"%(i))
        dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dlg.setIcon(QMessageBox.Question)
        button = dlg.exec()
        if button == QMessageBox.Yes:
            #print('drill-control: Saving calibration in slot %d'% i)
            self.ds.save_bno055_calibration(i)
        else:
#            print('save ignored...')           
            pass
        
        
    def clicked_loadcal(self, i):
        #print('drill-control: Loading calibration from slot %d'% i)
        self.ds.load_bno055_calibration(i)
        

    ### Plot control
    
    def changed_xaxislen_speed(self, idx):
    
        self.xlen_selector['speed'] = idx #self.cb_xaxislen_speed.currentIndex()
        self.plot_speed.setXRange(0, self.xlen[self.xlen_selector['speed']]/60*1.01, padding=0)

    def changed_xaxislen_load(self, idx):
    
        self.xlen_selector['load'] = idx #self.cb_xaxislen_load.currentIndex()
        self.plot_load.setXRange(0, self.xlen[self.xlen_selector['load']]/60*1.01, padding=0)
        
        
    def changed_xaxislen_current(self, idx):
        self.xlen_selector['current'] = idx #self.cb_xaxislen_current.currentIndex()
        self.plot_current.setXRange(0, self.xlen[self.xlen_selector['current']]/60*1.01, padding=0)
        
        
    def changed_xaxislen_incl(self, idx):
    
        self.xlen_selector['incl'] = idx #self.cb_xaxislen_current.currentIndex()
#        self.plot_incl.setXRange(0, self.xlen[self.xlen_selector['incl']]/60*1.01, padding=0)
        
        
    def changed_loadmeasure(self):
    
        loadmeasure = self.cb_loadmeasure.currentText()
        if loadmeasure == 'Load':         self.loadmeasure_inuse = 'hist_load'
        if loadmeasure == 'Load - cable': self.loadmeasure_inuse = 'hist_loadnet'
        if loadmeasure == 'Tare load':    self.loadmeasure_inuse = 'hist_loadtare'


    ### Run panel
    
    def clicked_startstop_run(self):
    
        if self.btn_startrun.isChecked(): # start pressed
            self.btn_startrun.setText('Stop')
            self.btn_startrun.setStyleSheet("font-weight: bold; background-color : %s"%(COLOR_RED))
            self.runtime0 = datetime.datetime.now()
            self.ss.set_depthtare(self.ss.depth)
            self.ds.set_tacho(0)
            self.btn_startrun.setShortcut(sc_startrun)
            self.randsound(self.sound_startrun)
#            self.clicked_resettareload() 
        else:
            self.btn_startrun.setText('Start')
            self.btn_startrun.setStyleSheet("font-weight: bold; background-color : %s"%(COLOR_GREEN))
            self.btn_startrun.setShortcut(sc_startrun)
            self.randsound(self.sound_stoprun)
            self.ss.set_depthtare(self.ss.depth)
    
    
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
        
        
    ### State update
    
    def makestatebox(self, id, name, value, margin_left=6, margin_right=0, margin_topbot=3):
        gb = QGroupBox(name)
        layout = QHBoxLayout()
        lbl = QLabel(value)
        setattr(self, id, lbl)
        layout.addWidget(lbl)
        layout.setContentsMargins(margin_left, margin_topbot, margin_right, margin_topbot)
        gb.setLayout(layout)
        return gb
      
      
    def updatestatebox(self, id, value, warnthres):
        lbl = getattr(self, id)
        lbl.setText(str(value) if not isinstance(value, list) else ', '.join(value))
        if isinstance(value, float) or isinstance(value, int):
            if warnthres[0] <= value <= warnthres[1]: lbl.setStyleSheet("background: none")
            else:                                     lbl.setStyleSheet("background: %s"%(COLOR_RED))
            
            
    def eventListener(self):

        warn__nothres = [-np.inf, np.inf]

        """
        SURFACE STATE
        """
        
        self.ss.update() # update state against redis server

        # Roll history 
        self.hist_speed = np.roll(self.hist_speed, -1); self.hist_speed[-1] = abs(self.ss.speed)
        self.hist_load     = np.roll(self.hist_load,  -1);     self.hist_load[-1]     = self.ss.load
        self.hist_loadtare = np.roll(self.hist_loadtare,  -1); self.hist_loadtare[-1] = self.ss.load - self.ss.loadtare
        self.hist_loadnet  = np.roll(self.hist_loadnet,  -1);  self.hist_loadnet[-1]  = self.ss.loadnet

        ### GRAPHS
        
        sel = self.xlen_selector['speed']
        I0 = -int(self.xlen[sel]/DT)
        x = self.hist_time[ I0:len(self.hist_time):self.xlen_samplerate[sel]]
        y = self.hist_speed[I0:len(self.hist_time):self.xlen_samplerate[sel]]
        self.curve_speed.setData(x=x, y=y)
        self.plot_speed.setYRange(0, np.amax([self.minYRange_speed, np.amax(y)*1.075]), padding=0.02)
        
        hist_loadmeas = getattr(self,self.loadmeasure_inuse)
        sel = self.xlen_selector['load']
        I0 = -int(self.xlen[sel]/DT)
        x = self.hist_time[I0:len(self.hist_time):self.xlen_samplerate[sel]]
        y = hist_loadmeas[ I0:len(self.hist_time):self.xlen_samplerate[sel]]
        self.curve_load.setData(x=x,y=y)

        self.plot_load.setTitle(   self.htmlfont('<b>%s = %.1f kg'%(self.loadmeasures[self.loadmeasure_inuse], hist_loadmeas[-1]), FS_TITLE))
        self.plot_speed.setTitle(  self.htmlfont('<b>Speed = %.1f cm/s'%(self.hist_speed[-1]), FS_TITLE))        

        ### DEPTH BAR
        
        self.depthbar.setValue(self.ss.depth, self.ss.depthtare)
        self.lbl_depthbar.setText(self.htmlfont('<b>%0.1fm'%(self.ss.depth), FS_TITLE))

        ### STATE FIELDS
        
        self.updatestatebox('surface_depth',           round(self.ss.depth,PRECISION_DEPTH),  warn__nothres)  # precision to match physical display
        self.updatestatebox('surface_speed',           round(self.ss.speedinst,2),            warn__velocity)
        self.updatestatebox('surface_load',            round(self.ss.load,PRECISION_LOAD),    warn__load) # precision to match physical display
        self.updatestatebox('surface_loadcable',       round(self.ss.loadnet,PRECISION_LOAD), warn__nothres)
        self.updatestatebox('surface_downholevoltage', round(self.ds.downhole_voltage,1),     warn__downholevoltage)
        self.updatestatebox('run_peakload',            round(np.amax(self.hist_load),PRECISION_LOAD), warn__nothres)
        self.updatestatebox('run_deltaload',           round(self.ss.load  - self.ss.loadtare,PRECISION_LOAD),   warn__nothres)
        self.updatestatebox('run_corelength',          round(self.ss.corelength,PRECISION_DEPTH), warn__nothres)
        
        if self.btn_startrun.isChecked(): 
            self.runtime1 = datetime.datetime.now() # update run time
            if self.runtime0 is not None:
                druntime = self.runtime1-self.runtime0
                self.updatestatebox('run_time',       self.timestamp(druntime),                 warn__nothres)
                self.updatestatebox('run_startdepth', round(self.ss.depthtare,PRECISION_DEPTH), warn__nothres)    
                self.updatestatebox('run_startload',  round(self.ss.loadtare,PRECISION_LOAD),   warn__nothres)    
                dL = self.ss.depth - self.ss.depthtare
                self.updatestatebox('run_deltadepth', round(dL,PRECISION_DEPTH), warn__corelength)

        """
        DRILL STATE
        """
        
        if self.Nt % DTFRAC == 0:

            self.ds.update() # update state against redis server

            # Roll history            
            self.hist_current = np.roll(self.hist_current,  -1); self.hist_current[-1] = self.ds.motor_current
            self.hist_depth   = np.roll(self.hist_depth, -1);    self.hist_depth[-1]   = np.abs(self.ss.depth) * 1e-3
            self.hist_incl    = np.roll(self.hist_incl, -1);     self.hist_incl[-1]    = self.ds.incl

            ### GRAPHS

            sel = self.xlen_selector['current']
            I0 = -int(self.xlen[sel]/(DT*DTFRAC))
            x = self.hist_time_drill[I0:len(self.hist_time_drill):self.xlen_samplerate[sel]]
            y = self.hist_current[   I0:len(self.hist_time_drill):self.xlen_samplerate[sel]]
            self.curve_current.setData(x=x,y=y)
            self.plot_current.setTitle(self.htmlfont('<b>Current = %.1f A'%(self.ds.motor_current), FS_TITLE))

            sel = self.xlen_selector['incl']
            I0 = -int(self.xlen[sel]/(DT*DTFRAC))
            x = self.hist_depth[I0:len(self.hist_depth):self.xlen_samplerate[sel]]
            y0 = self.hist_incl
            y = y0[I0:len(y0):self.xlen_samplerate[sel]]
            self.incl_scatter.setData(x=y, y=x)
            self.plot_incl.setYRange(0, np.amax([0.3, np.amax(x)*1.03]), padding=0.02)
            self.plot_incl.setTitle(self.htmlfont('<b>Inc = %.1f deg'%(self.ds.incl), FS_TITLE))

            ### STATE FIELDS

            if self.ds.islive or ALWAYS_SHOW_DRILL_FIELDS:

                self.updatestatebox('pressure_electronics', round(self.ds.pressure_electronics,1), warn__pressure)
                self.updatestatebox('pressure_topplug',     round(self.ds.pressure_topplug,1),     warn__pressure)
                self.updatestatebox('pressure_gear1',       (round(self.ds.pressure_gear1,1),round(self.ds.pressure_gear2,1)), warn__pressure)
                self.updatestatebox('hammer',               round(self.ds.hammer,1), warn__hammer)

                self.updatestatebox('temperature_topplug',     round(self.ds.temperature_topplug,1),        warn__temperature_electronics)
                self.updatestatebox('temperature_gear1',       (round(self.ds.temperature_gear1,1), round(self.ds.temperature_gear2,1)), warn__temperature_electronics)
                self.updatestatebox('temperature_electronics', (round(self.ds.temperature_electronics,1),round(self.ds.temperature_auxelectronics,1)), warn__temperature_electronics)
                self.updatestatebox('temperature_motor',       round(self.ds.temperature_motor,1),          warn__temperature_motor)    
                self.updatestatebox('temperature_motorctrl',   round(self.ds.motor_controller_temp,1),      warn__temperature_motor)    
                
                self.updatestatebox('motor_current',    round(self.ds.motor_current,1),  warn__motor_current)
                self.updatestatebox('motor_speed',      round(self.ds.motor_rpm,1),      warn__motor_rpm)    
                self.updatestatebox('motor_voltage',    round(self.ds.motor_voltage,1),  warn__nothres)    
                self.updatestatebox('motor_throttle',   int(self.ds.motor_throttle), warn__nothres)
                self.updatestatebox('motor_tachometer', round(self.ds.tachometer*TACHO_PRE_REV,2), warn__nothres)               

                # ORIENTATION
               
                self.updatestatebox('orientation_inclination',     '%.1f,&nbsp; <font color="%s">%.0f</font>'%(self.ds.incl,     COLOR_DIAL1, self.ds.roll),     warn__nothres)
                self.updatestatebox('orientation_inclination_alt', '%.1f,&nbsp; <font color="%s">%.0f</font>'%(self.ds.incl_alt, COLOR_DIAL2, self.ds.roll_alt), warn__nothres)
                self.updatestatebox('orientation_spin', "%.2f"%(self.ds.spin), warn__nothres)
                
                str_gravvec   = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.gravity_x,self.ds.gravity_y,self.ds.gravity_z, self.ds.gravity_mag)
                str_aclvec    = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.accelerometer_x,self.ds.accelerometer_y,self.ds.accelerometer_z, self.ds.accelerometer_mag)
                str_magvec    = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.magnetometer_x,self.ds.magnetometer_y,self.ds.magnetometer_z, self.ds.magnetometer_mag)
#                str_spnvec    = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.gyroscope_x,self.ds.gyroscope_y,self.ds.gyroscope_z, self.ds.gyroscope_mag)
#                str_linaclvec = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.linearaccel_x,self.ds.linearaccel_y,self.ds.linearaccel_z, self.ds.linearaccel_mag)
#                str_inclvec   = '[%.1f, %.1f], %.1f'%(self.ds.inclination_x,self.ds.inclination_y, -1)

                self.updatestatebox('orientation_gravity',            str_gravvec,   warn__nothres)
                self.updatestatebox('orientation_acceleration',       str_aclvec,    warn__nothres)
                self.updatestatebox('orientation_magnetometer',       str_magvec,    warn__nothres)
#                self.updatestatebox('orientation_gyroscope',          str_spnvec,    warn__nothres)
#                self.updatestatebox('orientation_linearacceleration', str_linaclvec, warn__nothres)
#                self.updatestatebox('orientation_inclinometer',       str_inclvec,   warn__nothres)

                self.dial_roll.setValue(int(self.ds.roll))
                self.dial_roll_alt.setValue(int(self.ds.roll_alt))

        """
        SYSTEM STATUS
        """
        
        if self.Nt % 4 == 0: # infrequent check is sufficient
            self.status_drill.setText('Online' if self.ds.islive else 'Offline')
            self.status_drill.setStyleSheet(self.style_onoffline[int(self.ds.islive)])
            self.status_loadcell.setText('Online' if self.ss.islive_loadcell else 'Offline')
            self.status_loadcell.setStyleSheet(self.style_onoffline[int(self.ss.islive_loadcell)])
            self.status_depthcounter.setText('Online' if self.ss.islive_depthcounter else 'Offline')
            self.status_depthcounter.setStyleSheet(self.style_onoffline[int(self.ss.islive_depthcounter)])

            if not ALWAYS_SHOW_DRILL_FIELDS:
                # Disable widgets if drill is offline
                self.gb_orientation.setEnabled(self.ds.islive)
                self.gb_pressure.setEnabled(self.ds.islive)
                self.gb_temperature.setEnabled(self.ds.islive)
                self.gb_surface_downholevoltage.setEnabled(self.ds.islive)

            self.gb_motor.setEnabled(self.ds.islive)
            self.gb_expert.setEnabled(True)
           
        """
        AUX
        """
                    
        self.Nt += 1
        
        
    def timestamp(self, turnaround):
        total_seconds = int(turnaround.total_seconds())
        hours, remainder = divmod(total_seconds,60*60)
        minutes, seconds = divmod(remainder,60)
        return "%02i:%02i:%02i"%(hours,minutes,seconds)
        
        
    def htmlfont(self, text,fsize, color='#000000'): return '<font size="%i" color="%s">%s</font>'%(fsize,color,text)
        

class DepthProgressBar(QWidget):

    def __init__(self, H_borehole=1e3):
        super().__init__()

        self.minval = 0 # min depth
        self.maxval = H_borehole # max depth (current ice drilling depth)
        self.curval = self.maxval * 0.5 # current drill depth (position)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding
        )

    def sizeHint(self):
        return QtCore.QSize(35,250)
        
    def setValue(self, currentDepth, iceDepth):
        self.curval = currentDepth
        self.maxval = np.amax([iceDepth,0.1])
        self.repaint()

    def paintEvent(self, e):

        self.painter = QtGui.QPainter(self)
        self.H, self.W = self.painter.device().height(), self.painter.device().width()

        ### Background (fluid)
        brush = QtGui.QBrush()
        c_fluid = 'white' #COLOR_GRAYBG 
        brush.setColor(QtGui.QColor(c_fluid))
        brush.setStyle(Qt.SolidPattern)
        rect = QtCore.QRect(0, 0, self.W, self.H)
        self.painter.fillRect(rect, brush)
        
        cgreen = "#a1d99b"
        cred   = "#fc9272"
        
        ### Zoom in for drilling mode
        Htol = 1 # meter above bottom before change to zoom-in 
        if self.curval<self.maxval - Htol:
            Hrel_ice = 0.05
            self.draw_ice(Hrel_ice)
            Hrel_drill = self.curval/self.maxval * (1-Hrel_ice)
            tol = 25 # metre
            c_drill = cgreen if self.curval < self.maxval - tol else cred
            self.draw_drill(Hrel_drill, c_drill)
            
        ### Zoom out for traveling mode
        else:
            # ice mass
            Hice = 2 # ice core max length
            if self.curval-self.maxval > 2: Hice = 4
            if self.curval-self.maxval > 4: Hice = 5 
            Htot = Htol+Hice
            self.draw_ice(Hice/Htot)

            # drill depth
            Hrel_drill = (self.curval-self.maxval+1)/Htot
            self.draw_drill(Hrel_drill, cgreen)

            # hatched delta L
            if self.curval > self.maxval:
                brush = QtGui.QBrush()
                brush.setColor(QtGui.QColor("#abd9e9"))
                brush.setStyle(Qt.BDiagPattern)
                rect = QtCore.QRect(0, int(Htol/Htot*self.H), self.W, int((Hrel_drill-Htol/Htot)*self.H))
                self.painter.fillRect(rect, brush)

            # horiz lines
            self.painter.setPen(QtGui.QPen(Qt.black, 3.5, Qt.SolidLine))
            H0 = int(1/Htot * self.H)
            self.painter.drawLine(0,H0,self.W,H0)        

            self.painter.setPen(QtGui.QPen(Qt.black, 3, Qt.DashLine))
            for dl in np.arange(Htol+1, Hice+1e-1, 1):
                H0 = int(dl/Htot * self.H)
                self.painter.drawLine(0,H0,self.W,H0)        
                
        ### Walls
        self.painter.setBrush(Qt.black)
        self.painter.setPen(QtGui.QPen(Qt.black, 4, Qt.SolidLine))
        self.painter.drawLine(0,0,0,self.H)
        self.painter.drawLine(self.W,0,self.W,self.H)
        self.painter.drawLine(0,self.H,self.W,self.H)
        self.painter.drawLine(0,0,self.W,0)
        
        self.painter.end()
        
    def draw_drill(self, Hrel, color):
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor(color))
        brush.setStyle(Qt.SolidPattern)
        H = int(Hrel*self.H) # in px
        rect = QtCore.QRect(0, 0, self.W, H)
        self.painter.fillRect(rect, brush)

    def draw_ice(self, Hrel, color="#deebf7"):
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor(color))
        brush.setStyle(Qt.SolidPattern)
        H0 = int((1-Hrel)*self.H) - 1
        rect = QtCore.QRect(0, H0, self.W, self.H)
        self.painter.fillRect(rect, brush)

    def _trigger_refresh(self):
        self.update()
        

class QHSeparationLine(QtWidgets.QFrame):

  def __init__(self):
    super().__init__()
    self.setMinimumWidth(1)
    self.setFixedHeight(30)
    self.setFrameShape(QtWidgets.QFrame.HLine)
    self.setFrameShadow(QtWidgets.QFrame.Sunken)
    self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
    return
    
        
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

