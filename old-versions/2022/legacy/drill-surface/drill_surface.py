#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, time
import datetime
import redis
from redis import ConnectionError
import tkinter as tk
from tkinter import font
from tkinter import ttk
from tkinter import *
from tkinter.ttk import *
from functools import partial

import math
import settings
import os
import threading

from drill_math import *
from state import DrillState, SurfaceState

#----------------------
# Config
#----------------------

config = []

#----------------------
# Globals
#----------------------

### NOTE FROM JC:
# Feel free to hack around to your heart's content! However, keep the fucking global
# namespace clear of all these state variables! This is a GUI, it is not meant to hold
# state in any significant amount. Do your calculations in the DrillState and SurfaceState
# objects in state.py. They contain all the sensor data you need. Do your thing in there
# and expose your genius calculations through methods on those classes :)
#
# Meanwhile, I'm trying to get rid of all these variables...
#
# And use the Git server on Bob: http://bob.egrip.camp:8888/
# Make a user there and clone what you need. Maybe make your own branch to work in?
#
# If you have any problems I can help! Just drop me a mail at hillerup@nbi.ku.dk

HAMMER_ALERT_UPPER_BOUND__LOW  = 6.0
HAMMER_ALERT_UPPER_BOUND__HIGH = 10.0

depth = 0
velocity = 0
load = 0
velocity_arr = [0 for i in range(200)]
load_plot = [0 for i in range(480)]
depth_plot = [] #[0 for i in range(4)]
depth_plot_mask = [0 for i in range(480)]
meanVelocity = 0
tare = 0
accelerometer = [0,0,0,0]
accelerometer_raw = [0,0,0,0]
orientation = [0,0,0,0]
accel_calib = [0,0,0]
m_current = 0
m_rpm = 0
m_voltage = 0
m_direction = ''
bh_maxDepth = 0
bh_startDepth = 0
bh_stopDepth = 0
bh_lastStartDepth = 0
bh_lastStopDepth = 0
bh_startTime = time.time()
bh_stopTime = time.time()
bh_deltaDepth = 0
bh_lastDeltaDepth = 0
bh_lastRunTime = 0
bh_LLevel = 0
state_running = False
state_run_id = -1
state_drilling = False
ll_detected = False
sound_bool = False
gyrosliptimeout = 0

NewGyroAlarm_state = False

left_box_color1 = '#969696'
left_box_color2 = '#bdbdbd'

COLOR_BG       = [255, 255, 255]
COLOR_WARN_RGB = [240, 59, 32]
COLOR_WARN_HEX = '#F03B20'
COLOR_OBS_RGB  = [255, 237, 160]
COLOR_OBS_HEX  = '#FFEDA0'
COLOR_BLUE_RGB = [158, 202, 225]
COLOR_BLUE_HEX = '#9ECAE1'
COLOR_OK_RGB   = [26, 152, 80]
COLOR_OK_HEX   = '#1A9850'

deltaDepthwidget_width = 200

PLOT_H = 590

logcounter = 0


drill_z = [9.789, -0.101, -0.1214]

loadWarning = False
loadAlert = False
pressureAlert = False
currentAlert = False

#----------------------
# REDIS FUNCTIONS
#----------------------
def redisConnect():
    tstep = 30
    host= settings.DRILL_HOST

    noconnect = True
    while noconnect:
        rs = redis.Redis(host=host)
        noconnect = False
        try:
            rs.ping()
        except ConnectionError:
            print("*** Redis connection failed to %s. Re-attempting in %i secs"%(host, tstep))
            noconnect = True
            time.sleep(tstep);
    return rs

redis_conn = redisConnect()
drill_state = DrillState(redis_conn)
surface_state = SurfaceState(redis_conn)




try:
    bh_maxDepth = float(redis_conn.get('dmsg-l'))
except:
    bh_maxDepth = -1

bh_lastStopDepth = bh_maxDepth


def getTare():
    try:
        return float(redis_conn.get('dmsg-tareref'))
    except:
        return 0

def setTare(tareval):
    redis_conn.set('dmsg-tareref', tareval)

def getAccelerometer():
    x = drill_state.get('accelerometer_x')
    y = drill_state.get('accelerometer_y')
    z = drill_state.get('accelerometer_z')

    try:
        total = math.sqrt(x*x + y*y + z*z)
    except:
        total = None

    return [x, y, z, total]


def getOrientation():
    global accel_calib, drill_z, accelerometer_raw

    try:
        accelerometer = accel_calib
        azimuth = math.atan2(accel_calib[1], -accel_calib[2])
        azid= azimuth * 180. / math.pi

        inclination = math.atan(math.sqrt(accel_calib[2]*accel_calib[2]+accel_calib[1]*accel_calib[1]) / accel_calib[0])
        incd = inclination * 180. / math.pi

    except:
        azimuth = None
        azid = None
        inclination = None
        incd = None

    try:
        inclination_marius = vector_angle(accelerometer_raw,drill_z)
        incd_marius = inclination_marius * 180. / math.pi

    except:
        inclination_marius = None
        incd_marius = None

    x_vector = [0,1,0]
    drill_x = vector_difference(x_vector,vector_projection(x_vector,drill_z))
    y_vector = [0,0,1]
    drill_y = vector_difference(vector_difference(y_vector, vector_projection(y_vector, drill_z)), vector_projection(y_vector,drill_x))


    try:
        acc_proj_drill_xy = vector_difference(accelerometer_raw,vector_projection(accelerometer_raw,drill_z))
        phi_x = vector_angle(drill_x, acc_proj_drill_xy)
        phi_y = vector_angle(drill_y, acc_proj_drill_xy)
    except:
        phi_x = 0
        phi_y = 0

    phi_xd = rad2deg(phi_x)
    phi_yd = rad2deg(phi_y)
    if phi_yd < 90:
        azid_marius = phi_xd
    else:
        azid_marius = -phi_xd
    azid_marius += 90

    if azid_marius > 180:
        azid_marius -= 360

    return [incd, azid, inclination, azimuth, incd_marius, inclination_marius, azid_marius]


def getCalibratedAccelerometer():
    ax = drill_state.get('accelerometer_x')
    ay = drill_state.get('accelerometer_y')
    az = drill_state.get('accelerometer_z')

    c = settings.accCalibration

    try:
        calX = c[0][0] * ax + c[0][1] * ay + c[0][2] * az
        calY = c[1][0] * ax + c[1][1] * ay + c[1][2] * az
        calZ = c[2][0] * ax + c[2][1] * ay + c[2][2] * az
    except:
        calX = None
        calY = None
        calZ = None

    return [calX, calY, calZ]

#----------------------
# OTHER FUNCTIONS
#----------------------


def createPlotArray(data, width, height, origin, load_alert, totalweight):
    n = len(data)
    dt = float(width-origin) / float(n)
    y_min = 1500
    y_max = 0
    outArray = []

    for i in data:
        if i > y_max:
            y_max = i
        if i < y_min:
            y_min = i

    y_max += 0.3
    y_min -= 0.3

    y_scale = (y_max - y_min) / float(height-30)

    scale = []
    y_sep = float(height-30) / 5.

    for i in range(6):
        coord = (15 + y_sep*i)
        scale.append([height-coord, coord*y_scale+y_min])

    if load_alert < y_min:
        alert_mark = height - 15
    elif load_alert > y_max:
        alert_mark = 15
    else:
        alert_mark = height - (float(load_alert)-y_min) / y_scale

    if totalweight < y_min:
        total_mark = height - 15
    elif totalweight > y_max:
        total_mark = 15
    else:
        total_mark = height - (float(totalweight)-y_min) / y_scale

    for i in range(n):
        outArray.append(origin + i* dt)
        outArray.append(height - (data[i] - y_min) / y_scale)

    return [outArray, scale, width-origin, [alert_mark, total_mark]]

def LOADALERT(minLoad, cableweight, maxLoad):
    global load, loadWarning, loadAlert


    if load < minLoad:
        loadWarning = True
        if load < cableweight:
            loadAlert = True
            return 1
        else:
            loadAlert = False
            return 0
    elif load > maxLoad:
        loadAlert = True
        return 1
    else:
        loadWarning = False
        loadAlert = False
        return 0

def PRESSUREALERT(maxPressure):

    err = 0

    return err

def CURRENTALERT(maxCurrent):
    global m_current, currentAlert

    return False

def BOTTOMALERT(distFromBottom):
        global depth, bh_maxDepth, meanVelocity, meanVelocity
#       bottomAlert = (bh_maxDepth-distFromBottom < depth) and meanVelocity > 0.3
        bottomAlert = (bh_maxDepth-distFromBottom < depth) and (depth<bh_maxDepth+0.5)
        return bottomAlert


def takeScreenshot(suffix):
    filename = "%s--%s.png" % (datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S"), suffix)

    folder = settings.screenshot_directory
    command = "scrot -ub \"%s/%s\" &" % (folder, filename)

    os.system(command)

    print(filename)

def NewGyroAlarm():
    global NewGyroAlarm_state

    if NewGyroAlarm_state:
        NewGyroAlarm_state = False

    else:
        NewGyroAlarm_state = True

    
    

def toggleRunLog():
    global state_drilling, bh_startDepth, bh_stopDepth, depth, bh_startTime, bh_stopTime, bh_deltaDepth
    global bh_lastStartDepth, bh_lastStopDepth, bh_lastRunTime, bh_lastDeltaDepth

    updateRunStatusFromRedis()

    if state_drilling:
        redis_conn.publish('surface', 'stop-run')
        state_drilling = False

        bh_stopDepth = depth
        bh_lastDeltaDepth = bh_stopDepth - bh_startDepth
        bh_lastStartDepth = bh_startDepth
        bh_lastStopDepth = bh_stopDepth

        bh_stopTime = time.time()
        bh_lastRunTime = bh_stopTime - bh_startTime

        takeScreenshot('run-end')

    else:
        redis_conn.publish('surface', 'start-run')
        state_drilling = True
        bh_startDepth = depth
        bh_startTime = time.time()

    updateRunStatusFromRedis()

    redis_conn.set('dmsg-l',depth)

def toggleTare(): # Changed name of button to Offset Load
    global load_plot
    tare = getTare()
    if tare>0:
        setTare(0)
        load_plot = [x+tare for x in load_plot]
    else:
        load0 = surface_state.get('load')
        setTare(load)
        load_plot = [x-load0 for x in load_plot]


def updateRunStatusFromRedis():
    global state_running, runStatus, state_run_id

    # Get the ground truth once
    is_running = redis_conn.get("is-running") == "True"

    # Update the local state
    state_running = is_running
    try:
        state_run_id = int(redis_conn.get('current-run'))
    except:
        state_run_id = -1

def detectLLevel(loaddrop):
    global depth, meanVelocity, bh_LLevel, load_plot, ll_detected

    if meanVelocity > 0.4 and depth < 180 and depth > 50 and not ll_detected:
        if load_plot[-1]+load_plot[-2]+load_plot[-3]+load_plot[-4]+loaddrop*4 < load_plot[-10]+load_plot[-11]+load_plot[-12]+load_plot[-13]:
            bh_LLevel = depth


#----------------------
# Interface
#----------------------
class App():

    def __init__(self):
        global load_plot, depth_plot_mask, depth_plot

        global NewGyroAlarm_state
        
        self.updatecounter = 0
        self._job = None
        # create window and main frame
        #-----------------------------

        self.root = tk.Tk(className = "Drill Control" )
        self.root.title("Drill Control")

        self.frame = tk.Frame(self.root)
        self.frame.grid(row=0, column=0)

        global left_box_color1, left_box_color2, COLOR_BG
        COLOR_BG = self.root["background"]

        # create gui variables
        #---------------------

        self.rFrameName = tk.StringVar()
        self.rButtonText = tk.StringVar()

        self.aziVar = tk.StringVar()
        self.incVar = tk.StringVar()

        self.m_currentVar = tk.StringVar()
        self.m_rpmVar = tk.StringVar()
        self.m_voltageVar = tk.StringVar()
        self.m_dutyCycleVar = tk.StringVar()

        self.w_loadVar = tk.StringVar()
        self.w_depthVar = tk.StringVar()
        self.w_depth_maxDepthVar = tk.StringVar()
        self.w_velocityVar = tk.StringVar()
        self.w_meanVelVar = tk.StringVar()

        self.w_sorensenVVar = tk.StringVar()
        self.w_sorensenAVar = tk.StringVar()

        self.hammerVar = tk.StringVar()
        self.downholeVoltageVar = tk.StringVar()
        self.spinVar = tk.StringVar()
        self.gyroVar = tk.StringVar()

        self.p_sens1Var = tk.StringVar()
        self.p_sens2Var = tk.StringVar()
        self.p_sens3Var = tk.StringVar()
        self.p_sens4Var = tk.StringVar()

        self.t_sens1Var = tk.StringVar()
        self.t_sens2Var = tk.StringVar()
        self.t_sens3Var = tk.StringVar()
        self.t_sens4Var = tk.StringVar()
        self.t_motorVar = tk.StringVar()

        self.n_gyroalarmVar = tk.StringVar()
        self.inclination_xVar = tk.StringVar()
        self.inclination_yVar = tk.StringVar()
        self.resetNewGyroalarmTextVar = tk.StringVar()
        self.magnetometer_xVar = tk.StringVar()
        self.magnetometer_yVar = tk.StringVar()
        self.magnetometer_zVar = tk.StringVar()

        self.bh_maxDepthVar = tk.StringVar()
        self.bh_deltaDepthVar = tk.StringVar()

        self.bh_lastStartDepthVar = tk.StringVar()
        self.bh_lastStopDepthVar = tk.StringVar()
        self.bh_lastDeltaDepthVar = tk.StringVar()
        self.bh_lastRunTimeVar = tk.StringVar()
        self.bh_lastBreakVar = tk.StringVar()

        self.runStatusButtontextVar = tk.StringVar()
        self.resetRunButtontextVar = tk.StringVar()
        self.bh_startDepthVar = tk.StringVar()
        self.bh_stopDepthVar = tk.StringVar()
        self.bh_currentRunTimeVar = tk.StringVar()
        self.bh_LLevelVar = tk.StringVar()

        self.netLoadStringVar = tk.StringVar()
        self.cutterLoadStringVar = tk.StringVar()

        self.runStatus = tk.StringVar()

        self.n_tachoVar = tk.StringVar()

        self.pwmVar = tk.IntVar()
        self.pwmVar.set(0)

        self.rotateVar = tk.IntVar()
        self.rotateVar.set(0)

        self.rpmVar = tk.IntVar()
        self.rpmVar.set(0)


        # Make sure we know about run data
        updateRunStatusFromRedis()


        # create main gui structure
        #--------------------------

        fontsmall  = font.Font(family="Helvetica", size=12, weight='normal')
        fontnormal = font.Font(family="Helvetica", size=15, weight='normal')
        fontlarge  = font.Font(family="Helvetica", size=17, weight='normal')
        fontalert  = font.Font(family="Helvetica", size=16, weight='bold')

        kwargs1      = {"padx":5, "pady":1}
        kwargs2      = {'bd':0, 'width':9, 'height':1, 'font':fontsmall, 'justify':'left'}
        pressure_settings = {'bd':0, 'width':9, 'height':2, 'font':fontsmall, 'justify':'left'}
        kwargs2norm  = {'bd':0, 'width':9, 'height':1, 'font':fontnormal, 'justify':'right'}
        kwargs2large = {'bd':0, 'height':1, 'font':fontlarge, 'justify':'right'}
        kwargs_lblframe = {'padx':8, 'pady':5}
        framexpad = 8

        #--------------------
        # Main Frames
        #--------------------
        pady=5


        self.clock_label = tk.Label(self.frame, width=7, font=fontalert)
        self.clock_label.grid(row=0, column=0)

        self.headerFrame = tk.Frame(self.frame)
        self.headerFrame.grid(row=0, column=1, pady=pady)

        self.alertFrame = tk.LabelFrame(self.frame, text='Alerts')
        self.alertFrame.grid(row=1, column=0, pady=pady, padx=10,sticky='n')

        self.centerFrame = tk.Frame(self.frame)
        self.centerFrame.grid(row=1, column=1, pady=pady)

        self.lowerFrame = tk.Frame(self.frame)
        self.lowerFrame.grid(row=2, column=0, columnspan=2, pady=pady)

        #--------------------
        # Header frame
        #--------------------

        c=0;r=0;
        kwargs = {'padx':2, 'pady':0}

        self.loadDisplayframe = tk.LabelFrame(self.headerFrame, text = 'Gross load', **kwargs)
        self.loadDisplayframe.grid(row=r, column=c, sticky='news'); c+=1
        self.loadDisplay = tk.Label(self.loadDisplayframe, textvariable = self.w_loadVar, width=8, **kwargs2large)
        self.loadDisplay.grid(row=0, column=0)
        
        self.netLoadDisplayframe = tk.LabelFrame(self.headerFrame, text = 'Net load', **kwargs)
        self.netLoadDisplayframe.grid(row=r, column=c, sticky='news'); c+=1
        self.netLoadDisplay = tk.Label(self.netLoadDisplayframe, textvariable = self.netLoadStringVar, width=8, **kwargs2large)
        self.netLoadDisplay.grid(row=0, column=0)

        self.depthDisplayframe = tk.LabelFrame(self.headerFrame, text = 'Current depth', **kwargs)
        self.depthDisplayframe.grid(row=r, column=c, sticky='news'); c+=1
        self.depthDisplay = tk.Label(self.depthDisplayframe, textvariable = self.w_depthVar, width=8,**kwargs2large)
        self.depthDisplay.grid(row=0, column=0)

        self.maxdepthDisplayframe = tk.LabelFrame(self.headerFrame, text = 'Total depth', **kwargs)
        self.maxdepthDisplayframe.grid(row=r, column=c, sticky='news'); c+=1
        self.maxdepthDisplay = tk.Label(self.maxdepthDisplayframe,
                                        textvariable = self.bh_maxDepthVar, width=8,**kwargs2large)
        self.maxdepthDisplay.grid(row=0, column=0)


        self.velocityDisplayframe = tk.LabelFrame(self.headerFrame, text = 'Winch speed', **kwargs)
        self.velocityDisplayframe.grid(row=r, column=c, sticky='news'); c+=1
        self.velocityDisplay = tk.Label(self.velocityDisplayframe, textvariable = self.w_velocityVar, width=12,**kwargs2large)
        self.velocityDisplay.grid(row=0, column=0)

        self.meanvelocityDisplayframe = tk.LabelFrame(self.headerFrame, text = 'Average speed', **kwargs)
        self.meanvelocityDisplayframe.grid(row=r, column=c, sticky='news'); c+=1
        self.meanvelocityDisplay = tk.Label(self.meanvelocityDisplayframe, textvariable = self.w_meanVelVar, width=12,**kwargs2large)
        self.meanvelocityDisplay.grid(row=0, column=0)

        self.tachoDisplayframe = tk.LabelFrame(self.headerFrame, text = 'Tachometer', **kwargs)
        self.tachoDisplayframe.grid(row=r, column=c, sticky='news'); c+=1
        self.tachoDisplay = tk.Label(self.tachoDisplayframe, textvariable = self.n_tachoVar, width=12,**kwargs2large)
        self.tachoDisplay.grid(row=0, column=0)

        #--------------------
        # Alert frame
        #--------------------

        kwargs = {'width':12, 'height':2, 'font':fontalert, 'justify':'center', 'padx':15}
        c = 0;r = 0

        self.loadAlert          = tk.Label(self.alertFrame, text = "Load", **kwargs)
        self.loadAlert.grid(row=r, column=c)
        r+=1

        self.currentAlert       = tk.Label(self.alertFrame, text = "Current", **kwargs)
        self.currentAlert.grid(row=r, column=c)
        r+=1

        self.pressureAlert      = tk.Label(self.alertFrame, text = "Leak", **kwargs)
        self.pressureAlert.grid(row=r, column=c)
        r+=1

        self.gyroAlert          = tk.Label(self.alertFrame, text = "Gyro Alert", **kwargs)
        self.gyroAlert.grid(row=r, column=c)
        r+= 1
        '''
        self.aziDisplayframe = tk.LabelFrame(self.alertFrame, text = 'Azimuth', **kwargs1)
        self.aziDisplayframe.grid(row=r, column=0, sticky='news', pady=5)
        tk.Label(self.aziDisplayframe, textvariable = self.aziVar, **kwargs2).grid(row=0, column=0)

        self.azimuthwidget = tk.Canvas(self.aziDisplayframe, height=100, width=100)
        self.azimuthwidget.grid(row=1, column=0, pady=20, sticky='news')

        self.azimuthwidget.create_oval(10,10,90,90, outline='black', fill='white')
        self.azimuthwidget.create_polygon(50,10,45,0,55,0, fill="black")
        '''
        #--------------
        # Lower frames
        #--------------
        collowerframe = 0
        rowslowerframe = 2

        self.inclinometerframe = tk.LabelFrame(self.lowerFrame, text='Drill orientation', **kwargs_lblframe)
        self.inclinometerframe.grid(row=0, column=collowerframe, rowspan=rowslowerframe+1, sticky='news', padx=framexpad); collowerframe+=1


        self.inclinationDisplayframe = tk.LabelFrame(self.inclinometerframe, text = 'Inclination', **kwargs1)
        self.inclinationDisplayframe.grid(row=0, column=0, sticky='news',pady=5)
        tk.Label(self.inclinationDisplayframe, textvariable = self.incVar,  **kwargs2).grid(row=0, column=0)
        
        self.aziDisplayframe = tk.LabelFrame(self.inclinometerframe, text = 'Azimuth', **kwargs1)
        self.aziDisplayframe.grid(row=1, column=0, sticky='news', pady=5)
        tk.Label(self.aziDisplayframe, textvariable = self.aziVar, **kwargs2).grid(row=0, column=2)

        self.azimuthwidget = tk.Canvas(self.aziDisplayframe, height=90, width=100)
        self.azimuthwidget.grid(row=1, column=2, pady=4, sticky='news')

        self.azimuthwidget.create_oval(10,10,90,90, outline='black', fill='white')
        self.azimuthwidget.create_polygon(50,10,45,0,55,0, fill="black")
        
        #-----------

        self.sensorFrame = tk.LabelFrame(self.lowerFrame, text='Drill sensors', **kwargs_lblframe)
        self.sensorFrame.grid(row=0, column=collowerframe, rowspan=rowslowerframe, sticky='news', padx=framexpad)

        collowerframe+=1
        kwargs = {'sticky':'news', 'pady':2, 'padx':4}

        self.pres1Displayframe = tk.LabelFrame(self.sensorFrame, text = 'P Electronics', height=3)
        self.pres1Displayframe.grid(row=0, column=0, **kwargs)
        tk.Label(self.pres1Displayframe, textvariable = self.p_sens1Var, **pressure_settings).grid(row=0, column=0)

        self.pres2Displayframe = tk.LabelFrame(self.sensorFrame, text = 'P Topplug', height=3)
        self.pres2Displayframe.grid(row=0, column=1, **kwargs)
        tk.Label(self.pres2Displayframe, textvariable = self.p_sens2Var,  **pressure_settings).grid(row=0, column=0)

        self.pres3Displayframe = tk.LabelFrame(self.sensorFrame, text = 'P Gear 1')
        self.pres3Displayframe.grid(row=1, column=0, **kwargs)
        tk.Label(self.pres3Displayframe, textvariable = self.p_sens3Var, **pressure_settings).grid(row=0, column=0)

        self.pres4Displayframe = tk.LabelFrame(self.sensorFrame, text = 'P Gear 2')
        self.pres4Displayframe.grid(row=1, column=1, **kwargs)
        tk.Label(self.pres4Displayframe, textvariable = self.p_sens4Var, **pressure_settings).grid(row=0, column=0)

        self.temp1Displayframe = tk.LabelFrame(self.sensorFrame, text = 'T Baseplate', **kwargs1)
        self.temp1Displayframe.grid(row=2, column=0, **kwargs)
        self.temp1Display = tk.Label(self.temp1Displayframe, textvariable = self.t_sens1Var, **kwargs2)
        self.temp1Display.grid(row=0, column=0)

        self.temp2Displayframe = tk.LabelFrame(self.sensorFrame, text = 'T Motor sect.', **kwargs1)
        self.temp2Displayframe.grid(row=2, column=1, **kwargs)
        self.temp2Display = tk.Label(self.temp2Displayframe, textvariable = self.t_sens2Var, **kwargs2)
        self.temp2Display.grid(row=0, column=0)

        self.temp3Displayframe = tk.LabelFrame(self.sensorFrame, text = 'T VESC', **kwargs1)
        self.temp3Displayframe.grid(row=3, column=0, **kwargs)
        tk.Label(self.temp3Displayframe, textvariable = self.t_sens3Var, **kwargs2).grid(row=0, column=0)

        self.spinDisplayframe = tk.LabelFrame(self.sensorFrame, text = 'Spin', **kwargs1)
        self.spinDisplayframe.grid(row=3, column=1, **kwargs)
        self.spinLabel = tk.Label(self.spinDisplayframe, textvariable = self.spinVar, **kwargs2)
        self.spinLabel.grid(row=0, column=0)


        self.downholeVoltageDisplayframe = tk.LabelFrame(self.sensorFrame, text = 'Downhole V', **kwargs1)
        self.downholeVoltageDisplayframe.grid(row=4, column=0, **kwargs)
        self.downholeVoltageDisplay = tk.Label(self.downholeVoltageDisplayframe, textvariable = self.downholeVoltageVar, **kwargs2)
        self.downholeVoltageDisplay.grid(row=0, column=0)

        self.hammerDisplayframe = tk.LabelFrame(self.sensorFrame, text = 'Hammer', **kwargs1)
        self.hammerDisplayframe.grid(row=4, column=1, **kwargs)
        self.hammerDisplay = tk.Label(self.hammerDisplayframe, textvariable = self.hammerVar, **kwargs2)
        self.hammerDisplay.grid(row=0, column=0)

        self.gyroDisplayframe = tk.LabelFrame(self.sensorFrame, text = 'Gyro Alarm', **kwargs1)
        self.gyroDisplayframe.grid(row=5, column=1, **kwargs)
        self.gyroDisplay = tk.Label(self.gyroDisplayframe, textvariable = self.n_gyroalarmVar, **kwargs2)
        self.gyroDisplay.grid(row=0, column=0)

        self.NewGyroAlarmButt = tk.Button(self.sensorFrame, height=1, width=9, bg = 'green', textvariable = self.resetNewGyroalarmTextVar, command=NewGyroAlarm) #.grid(row=5 ,column=0)
        #self.NewGyroAlarmButt = tk.Button(self.sensorFrame, height=1, width=9, bg = 'green', textvariable = self.resetNewGyroalarmTextVar, command=partial(self.RotateMotor, 270, 10)) #.grid(row=5 ,column=0)
        self.NewGyroAlarmButt.grid(row=5 ,column=0)
        #tk.Button(self.sensorFrame, height=1, width=9, textvariable = self.resetNewGyroalarmTextVar, command=lambda: NewGyroAlarm_state= !(NewGyroAlarm_state)).grid(row=5 ,column=0)
        #tk.Button(self.currentrunFrame, height=1, width=9, text='Offset Load', command=toggleTare).grid(row=2, column=1) RotateMotor(self, 10, 10, 1)

#inclinometerframe
        
        self.inclinationXDisplayframe = tk.LabelFrame(self.inclinometerframe, text = 'Inclinnation X, Y', **kwargs1)
        self.inclinationXDisplayframe.grid(row=2, column=0, sticky='news',pady=5, padx=4) #, **kwargs)
        self.inclinationXDisplay = tk.Label(self.inclinationXDisplayframe, textvariable = self.inclination_xVar, **kwargs2)
        self.inclinationXDisplay.grid(row=0, column=0)

        #self.inclinationYDisplayframe = tk.LabelFrame(self.inclinometerframe, text = 'Inclination Y', **kwargs1)
        #self.inclinationYDisplayframe.grid(row=2, column=1, sticky='news',pady=5, padx=4) #, **kwargs)
        self.inclinationYDisplay = tk.Label(self.inclinationXDisplayframe, textvariable = self.inclination_yVar, **kwargs2)
        self.inclinationYDisplay.grid(row=0, column=1)

#'magnetometer_x'

        self.magnetometerDisplayframe = tk.LabelFrame(self.inclinometerframe, text = 'Magnetometer', **kwargs1)
        self.magnetometerDisplayframe.grid(row=3, column=0, sticky='news',pady=5, padx=4) #, **kwargs)
        self.magnetometer_xDisplay = tk.Label(self.magnetometerDisplayframe, textvariable = self.magnetometer_xVar, **kwargs2)
        self.magnetometer_xDisplay.grid(row=0, column=0)
        self.magnetometer_xDisplay = tk.Label(self.magnetometerDisplayframe, textvariable = self.magnetometer_yVar, **kwargs2)
        self.magnetometer_xDisplay.grid(row=0, column=1)
        self.magnetometer_xDisplay = tk.Label(self.magnetometerDisplayframe, textvariable = self.magnetometer_zVar, **kwargs2)
        self.magnetometer_xDisplay.grid(row=0, column=2)

        #self.inclinationXDisplayframe = tk.LabelFrame(self.inclinometerframe, text = 'Inclin X', **kwargs1)
        #self.inclinationXDisplayframe.grid(row=0, column=0, sticky='news',pady=5)
        #tk.Label(self.inclinationDisplayframe, textvariable = self.incVar,  **kwargs2).grid(row=0, column=0)


        self.motorcontrolframe = tk.LabelFrame(self.lowerFrame, text='Motor control', **kwargs_lblframe)
        self.motorcontrolframe.grid(row=0, column=collowerframe, rowspan=rowslowerframe, sticky='news', padx=framexpad)
        collowerframe+=1
        row=0

        self.currentDisplayframe = tk.LabelFrame(self.motorcontrolframe, text = 'Current', **kwargs1)
        self.currentDisplayframe.grid(row=row, column=0, columnspan=2)
        self.currentDisplay = tk.Label(self.currentDisplayframe, textvariable = self.m_currentVar, **kwargs2norm)
        self.currentDisplay.grid(row=0, column=0)

        self.rpmDisplayframe = tk.LabelFrame(self.motorcontrolframe, text = 'Speed', **kwargs1)
        self.rpmDisplayframe.grid(row=row, column=2, columnspan=2)
        tk.Label(self.rpmDisplayframe, textvariable = self.m_rpmVar, **kwargs2norm).grid(row=0, column=0)

        self.voltageDisplayframe = tk.LabelFrame(self.motorcontrolframe, text = 'Voltage', **kwargs1)
        self.voltageDisplayframe.grid(row=row+1, column=0, columnspan=2, pady=10, padx=7)
        tk.Label(self.voltageDisplayframe, textvariable = self.m_voltageVar, **kwargs2norm).grid(row=0, column=0)
        '''
        self.voltageDisplayframe = tk.LabelFrame(self.motorcontrolframe, text = 'Throttle', **kwargs1)
        self.voltageDisplayframe.grid(row=row+1, column=2, columnspan=2, pady=10, padx=7)
        tk.Label(self.voltageDisplayframe, textvariable = self.m_dutyCycleVar, **kwargs2norm).grid(row=0, column=0)
        '''
        self.throttleDisplayframe = tk.LabelFrame(self.motorcontrolframe, text = 'Throttle', **kwargs1)
        self.throttleDisplayframe.grid(row=row+1, column=2, columnspan=2, pady=10, padx=7)
        tk.Label(self.throttleDisplayframe, textvariable = self.m_dutyCycleVar, **kwargs2norm).grid(row=0, column=0)

        row = row+2
        self.motorcontrolbuttonframe = tk.Frame(self.motorcontrolframe, padx=0, pady=5)
        self.motorcontrolbuttonframe.grid(row=row, columnspan=4, column=0)

        controlNotebook = Notebook(self.motorcontrolbuttonframe)
        controlNotebook.grid(row=0, column=0)

        throttleControlTab = Frame()
        controlNotebook.add(throttleControlTab, text='Throttle control')
        tk.Label(throttleControlTab, text="Throttle").grid(row=0, column=0, columnspan=4)
        #tk.Scale(throttleControlTab, from_=-255, to=255, orient=tk.HORIZONTAL, length=220, variable=self.pwmVar).grid(row=1, column=0, columnspan=2, sticky='news')
        tk.Label(throttleControlTab, text="Jerky Throttle - Press Start to Express").grid(row=1, column=0, columnspan=4)
        tk.Scale(throttleControlTab, from_=-255, to=255, orient=tk.HORIZONTAL, length=512, variable=self.pwmVar).grid(row=2, column=0, columnspan=4, sticky='news')
        self.MyScale = tk.Scale(throttleControlTab, from_=-255, to=255, orient=tk.HORIZONTAL, length=512, resolution=5,  command=self.startMotorThrottle, variable=self.pwmVar)
        self.MyScale.grid(row=0, column=0, columnspan=4, sticky='news')

        kwargs_motorcontrol = {'width': 10, 'height': 2}
        tk.Button(throttleControlTab, text='Start', bg=COLOR_OK_HEX,   command=self.startMotorThrottle, **kwargs_motorcontrol).grid(row=3, column=1, pady=15)
        tk.Button(throttleControlTab, text='Stop',  bg=COLOR_WARN_HEX, command=self.stopMotor,  **kwargs_motorcontrol).grid(row=3, column=2, pady=15)
        '''
        tk.Button(throttleControlTab, text='Parvalux',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 0),  **kwargs_motorcontrol).grid(row=3, column=0, pady=4)
        tk.Button(throttleControlTab, text='Skateboard',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 1),  **kwargs_motorcontrol).grid(row=3, column=1, pady=4)
        tk.Button(throttleControlTab, text='Hacker',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 2),  **kwargs_motorcontrol).grid(row=3, column=2, pady=4)
        tk.Button(throttleControlTab, text='Plettenberg',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 3),  **kwargs_motorcontrol).grid(row=3, column=3, pady=4)
        '''

#        rpmControlTab = Frame()
#        controlNotebook.add(rpmControlTab, text='RPM control')
#        tk.Label(rpmControlTab, text="RPM").grid(row=0, column=0, columnspan=2)
#        tk.Scale(rpmControlTab, from_=-120, to=120, orient=tk.HORIZONTAL, length=220, variable=self.rpmVar).grid(row=1, column=0, columnspan=2, sticky='news')

#        tk.Button(rpmControlTab, text='Start', bg=COLOR_OK_HEX,   command=self.startMotorRPM, **kwargs_motorcontrol).grid(row=2, column=0, pady=15)
#        tk.Button(rpmControlTab, text='Stop',  bg=COLOR_WARN_HEX, command=self.stopMotor,  **kwargs_motorcontrol).grid(row=2, column=1, pady=15)

        goodiesControlTab = Frame()
        controlNotebook.add(goodiesControlTab, text='Fine control')
#        tk.Button(goodiesControlTab, text='Small rotation\nBackward', command=lambda: self.smallRotation(settings.inching_pwm * -1, settings.inching_time), **kwargs_motorcontrol).grid(row=0, column=0, pady=5, padx=5)
#        tk.Button(goodiesControlTab, text='Small rotation\nForward',  command=lambda: self.smallRotation(settings.inching_pwm, settings.inching_time),  **kwargs_motorcontrol).grid(row=0, column=1)
        #
        tk.Button(goodiesControlTab, text='Close filter',  command=lambda: self.smallRotation(settings.inching_pwm__FLT,    settings.inching_time),  **kwargs_motorcontrol).grid(row=1, column=0,pady=15)
        tk.Button(goodiesControlTab, text='Open filter',   command=lambda: self.smallRotation(settings.inching_pwm__FLT*-1, settings.inching_time),  **kwargs_motorcontrol).grid(row=1, column=1)
        #
        tk.Button(goodiesControlTab, text='S.B. release',  command=lambda: self.smallRotation(settings.inching_pwm__SB* -1, settings.inching_time),  **kwargs_motorcontrol).grid(row=2, column=0)
        tk.Button(goodiesControlTab, text='S.B. lock',     command=lambda: self.smallRotation(settings.inching_pwm__SB,     settings.inching_time),  **kwargs_motorcontrol).grid(row=2, column=1)
 
        expertControlTab = Frame()
        controlNotebook.add(expertControlTab, text='Expert settings')
        tk.Button(expertControlTab, text='Parvalux',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 0),  **kwargs_motorcontrol).grid(row=3, column=0, pady=10, padx=10)
        tk.Button(expertControlTab, text='Skateboard',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 1),  **kwargs_motorcontrol).grid(row=3, column=1, pady=10, padx=10)
        tk.Button(expertControlTab, text='Hacker',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 2),  **kwargs_motorcontrol).grid(row=3, column=2, pady=10, padx=10)
        tk.Button(expertControlTab, text='Plettenberg',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 3),  **kwargs_motorcontrol).grid(row=3, column=3, pady=10, padx=10)
        
        rotateControlTab = Frame()
        controlNotebook.add(rotateControlTab, text='Rotate drill')
        '''
        self.rotateDisplayframe = tk.LabelFrame(rotateControlTab, text = 'Rotation', **kwargs1)
        self.rotateDisplayframe.grid(row=1, column=0, sticky='news', pady=5)
        tk.Label(self.aziDisplayframe, textvariable = self.aziVar, **kwargs2).grid(row=0, column=2)
        '''
        #self.rotationwidget = tk.Canvas(self.rotateDisplayframe, height=90, width=100)
        self.rotationwidget = tk.Canvas(rotateControlTab, height=100, width=100)
        self.rotationwidget.grid(row=1, column=0, pady=4, sticky='news')

        self.rotationwidget.create_oval(10,10,90,90, outline='black', fill='white')
        self.rotationwidget.create_polygon(50,10,45,0,55,0, fill="black")
        #self.rotationwidget.create_polygon(50,90,45,100,55,100, fill="black")
        #self.rotationwidget.create_polygon(math.cos(-30)*45+45+10, -1*math.sin(-30)*45+45+10,math.cos(-28)*50+45+10, -1*math.sin(-28)*50+45+10,math.cos(-32)*50+45+10, -1*math.sin(-32)*50+45+10, fill="black")
        RotaDeg = 30.0
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*40.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*40.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*50.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*50.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*50.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*50.0+40+10,
                                            fill="black")
        
        RotaDeg = 150.0
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*40.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*40.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*50.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*50.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*50.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*50.0+40+10,
                                            fill="black")
        # Drill arrows

        RotaDeg = 150.0
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*40.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*40.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*30.0+40+10,
                                            tag="rotate_arrow_2", fill="black")
        
        RotaDeg = 270.0
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*40.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*40.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*30.0+40+10,
                                            tag="rotate_arrow_3", fill="black")
        
        RotaDeg = 30.0
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*40.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*40.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*30.0+40+10,
                                            tag="rotate_arrow_1", fill="black")
        
        
        tk.Button(rotateControlTab, text='Rotate\n to new pos',  bg='green', font="Courier 10", command=partial(self.RotateMotor, 270, 10),  **kwargs_motorcontrol).grid(row=1, column=1, pady=10, padx=10)
        tk.Button(rotateControlTab, text='Reset tacho',  bg=COLOR_WARN_HEX, command=partial(self.SetTacho, 0),  **kwargs_motorcontrol).grid(row=1, column=3, pady=10, padx=10)
        #tk.Button(rotateControlTab, text='C',  bg=COLOR_WARN_HEX, command=partial(self.setMotor, 2),  **kwargs_motorcontrol).grid(row=3, column=2, pady=10, padx=10)
        tk.Label(rotateControlTab, text="Drill rotation").grid(row=0, column=0, columnspan=4)
        #tk.Scale(rotateControlTab, from_=-255, to=255, orient=tk.HORIZONTAL, length=512, variable=self.pwmVar).grid(row=2, column=0, columnspan=4, sticky='news')
        #self.MyRotScale = tk.Scale(rotateControlTab, from_=-360, to=360, orient=tk.HORIZONTAL, length=720, resolution=1,  command=partial(self.RotateMotor, 270, 10), variable=self.rotateVar)
        self.MyRotScale = tk.Scale(rotateControlTab, from_=-360, to=360, orient=tk.HORIZONTAL, length=720, resolution=1,  variable=self.rotateVar)
        self.MyRotScale.grid(row=0, column=0, columnspan=4, sticky='news')
        
        #-----------

        self.currentrunFrame = tk.LabelFrame(self.lowerFrame, text="Current run", **kwargs_lblframe)
        self.currentrunFrame.grid(row=0, column=collowerframe, sticky='news', padx=framexpad)
        collowerframe+=1


        self.currentStartDisplayframe = tk.LabelFrame(self.currentrunFrame, text = 'Start depth', **kwargs1)
        self.currentStartDisplayframe.grid(row=0, column=0, padx=5)
        tk.Label(self.currentStartDisplayframe,textvariable = self.bh_startDepthVar, **kwargs2).grid(row=0, column=0)

        self.timeDisplayFrame = tk.LabelFrame(self.currentrunFrame, text = 'Run time', **kwargs1)
        self.timeDisplayFrame.grid(row=0, column=1, padx=5)
        tk.Label(self.timeDisplayFrame, textvariable = self.bh_currentRunTimeVar, **kwargs2).grid(row=0, column=0)

        self.deltaDepthwidgetframe = tk.LabelFrame(self.currentrunFrame, text=u'\u0394 length', **kwargs1)
        self.deltaDepthwidgetframe.grid(row=1, columnspan=2, column=0, pady=10)
        self.deltaDepthwidget = tk.Canvas(self.deltaDepthwidgetframe, bg="white", height=30, width=deltaDepthwidget_width)
        self.deltaDepthwidget.grid(row=0, column=0,pady=3)

        self.deltaDepthwidget.create_text(deltaDepthwidget_width*1/2, 15, fill='black', tag='deltatext',anchor=tk.CENTER, text='0cm', font=fontnormal)

        tk.Button(self.currentrunFrame, height=1, width=9, textvariable = self.resetRunButtontextVar, command=toggleRunLog).grid(row=2 ,column=0)
        tk.Button(self.currentrunFrame, height=1, width=9, text='Offset Load', command=toggleTare).grid(row=2, column=1)


        self.cutterLoadLabelFrame = tk.LabelFrame(self.currentrunFrame, text=u'Cutter load')
        self.cutterLoadLabelFrame.grid(row=4, column=1)
        tk.Label(self.cutterLoadLabelFrame, textvariable = self.cutterLoadStringVar, **kwargs2).grid(row=0, column=0)

        tk.Button(self.currentrunFrame, height=1, width=9, text='Screenshot', command=lambda: takeScreenshot('driller')).grid(row=4, column=0)


        # --------------------------------
        self.prevrunFrame = tk.LabelFrame(self.lowerFrame, text = 'Previous Run', **kwargs_lblframe)
        self.prevrunFrame.grid(row=0, column=collowerframe, rowspan=rowslowerframe, sticky='news', padx=framexpad); collowerframe+=1
        kwargs = {'sticky':'news', 'pady':3,'padx':4}

        self.l_startDisplayframe = tk.LabelFrame(self.prevrunFrame, text = 'Start', **kwargs1)
        self.l_startDisplayframe.grid(row=0, column=0, **kwargs)
        tk.Label(self.l_startDisplayframe, textvariable = self.bh_lastStartDepthVar, **kwargs2).grid(row=0, column=0)

        self.lLDisplayframe = tk.LabelFrame(self.prevrunFrame, text = 'Liquid level', **kwargs1)
        self.lLDisplayframe.grid(row=5, column=0, **kwargs)
        tk.Label(self.lLDisplayframe, textvariable = self.bh_LLevelVar, **kwargs2).grid(row=0, column=0)

        self.l_stopDisplayframe = tk.LabelFrame(self.prevrunFrame, text = 'Stop', **kwargs1)
        self.l_stopDisplayframe.grid(row=2, column=0, **kwargs)
        tk.Label(self.l_stopDisplayframe, textvariable = self.bh_lastStopDepthVar, **kwargs2).grid(row=0, column=0)

        self.l_dDepthDisplayframe = tk.LabelFrame(self.prevrunFrame, text = u'\u0394 length', **kwargs1)
        self.l_dDepthDisplayframe.grid(row=3, column=0, **kwargs)
        tk.Label(self.l_dDepthDisplayframe, textvariable = self.bh_lastDeltaDepthVar, **kwargs2).grid(row=0, column=0)

        self.l_timeDisplayframe = tk.LabelFrame(self.prevrunFrame, text = 'Run time', **kwargs1)
        self.l_timeDisplayframe.grid(row=4, column=0, **kwargs)
        tk.Label(self.l_timeDisplayframe, textvariable = self.bh_lastRunTimeVar, **kwargs2).grid(row=0, column=0)

        #--------------
        # Plot
        #--------------
        self.loadplotframe = tk.LabelFrame(self.centerFrame, padx=0, pady=0)
        self.loadplotframe.grid(row=0, column=0, sticky='news')

#       self.loadplotframe = tk.Canvas(self.loadplotframe, bg="white", height=620, width=900)

        self.loadplotframe = tk.Canvas(self.loadplotframe, bg="white", height=PLOT_H+20, width=900)
        self.loadplotframe.grid(row=0, column=0)

        self.loadplotframe.create_line(60, 0, 60, 630, fill="black")
        self.loadplotframe.create_line(800, 0, 800, 630, fill="black")
        self.loadplotframe.create_line(60, 585, 800, 585, fill='black')

        [outArray, scale, array_width, load_mark] = createPlotArray(load_plot, 800, PLOT_H, 60, 4, 12)

        for i in scale:
            self.loadplotframe.create_line(52,i[0],60,i[0], fill="black", width=1, tag= "plotscale")
            self.loadplotframe.create_text(50,i[0], font=fontlarge, text='{:.1f}'.format(i[1]), anchor='e', tag= "plotscale")
            

        self.loadplotframe.create_line(outArray, fill="black", width=2, tag= "loadplot")

        #---------------
        # closing window
        #---------------

        def on_closing():
            self.root.quit()     # stops mainloop
            self.root.destroy()

        self.root.protocol("WM_DELETE_WINDOW", on_closing)


        def gotGyroSlip():
            global gyrosliptimeout
            
            gyrosliptimeout = datetime.datetime.now().timestamp() + 5
        
        
        # Start a Redis pubsub listener
        def redis_listener():
            ps = redis_conn.pubsub(ignore_subscribe_messages=True)
            ps.subscribe('uphole')
            for redis_msg in ps.listen():
                # TODO Catch the DrillState messages here, too and update the UI, instead of polling
                
                if redis_msg is not None and redis_msg["type"] == "message":
                    uphole_packet_type = redis_msg["data"].decode('ascii')

                    # print(uphole_packet_type)
                    
                    if uphole_packet_type == "GyroSlipAlarm":
                        gotGyroSlip()
                    # ... this should work, but I don't have time to properly test.
                    # elif uphole_packet_type == "DownholeState":
                    #     drill_state.update()

        redis_listener_thread = threading.Thread(target=redis_listener, daemon=True)
        redis_listener_thread.start()

        
        # Start update and main loop
        #---------------------------
        self.update()
        self.updateplot()
        self.root.mainloop()

    def update(self):
        global velocity_arr, depth, velocity, meanVelocity, load, tare, accelerometer, logcounter, plotupdatecounter, accel_calib,  accelerometer_raw
        global towerAlert, casingAlert, loadWarning, loadAlert, pressureAlert, hammerAlert, currentAlert, bottomAlert, temperatureAlert
        global m_current, m_rpm  , m_voltage
        global load_plot, depth_plot, depth_plot_mask, bh_maxDepth, bh_lastStartDepth, bh_lastStopDepth, bh_startDepth, bh_stopDepth, bh_deltaDepth, bh_lastDeltaDepth, bh_startTime, bh_stopTime, state_drilling, bh_lastRunTime, bh_LLevel, gyrosliptimeout
        global ll_detected
        global COLOR_BG
        global sound_bool
        global NewGyroAlarm_state

        self.updatecounter += 1

        now = time.strftime("%H:%M:%S")
        self.clock_label.configure(text=now)
        self.root.after(100, self.update)

        drill_state.update()
        surface_state.update()

        depth = surface_state.get('depth')
        velocity = surface_state.get('velocity')
        load = surface_state.get('load')
        tare = getTare()
        accelerometer_raw = getAccelerometer()
        accelerometer = getAccelerometer()
        accel_calib = getCalibratedAccelerometer()
        # orientation = getOrientation()

        updateRunStatusFromRedis()

        # get mean velocity
        velocity_arr.pop(0)
        velocity_arr.append(velocity)
        meanVelocity = mean(velocity_arr)

        #calculating cable weight
        cableWeight = settings.cable_weight(depth)

        load_ = load - tare*(tare>0)
        load_plot.pop(0)
        load_plot.append(load_)

        n=0
        m=int((len(depth_plot_mask)-1)/ 4)

        for i in range(m):
            n+=depth_plot_mask[i-m]

        depth_plot_mask.pop(0)
        if n > 0:
            depth_plot_mask.append(0)
        else:
            depth_plot_mask.append(1)
            if len(depth_plot) > 3:
                depth_plot.pop(0)
            depth_plot.append(depth)


        # set plot background
        hammer_pct = (100 * float(drill_state.get('hammer')) / settings.max_hammer)
        if hammer_pct > HAMMER_ALERT_UPPER_BOUND__HIGH:
            self.loadplotframe["bg"] = COLOR_WARN_HEX
        elif hammer_pct > HAMMER_ALERT_UPPER_BOUND__LOW:
            self.loadplotframe["bg"] = COLOR_OBS_HEX
        else:
            self.loadplotframe["bg"] = 'white'

        # Reset liquid level
        if ll_detected and depth < 50:
            ll_detected = False

        # print ll_detected

        detectLLevel(10)

        m_current = drill_state.get('motor_current')
        m_rpm = drill_state.get('motor_rpm')
        m_voltage = drill_state.get('motor_voltage')

        if depth > bh_maxDepth:
            bh_maxDepth = depth

        if state_running:
            self.runStatusButtontextVar.set('Stop run')
            self.runStatus.set("Current run: %d" % int(state_run_id))
        else:
            self.runStatusButtontextVar.set('Start run')
            self.runStatus.set("Not running")

        if state_drilling:
            self.resetRunButtontextVar.set('Stop log')
            bh_deltaDepth = depth - bh_startDepth
#            self.depthDisplay["bg"] = left_box_color1
        else:
            self.resetRunButtontextVar.set('Start log')
            bh_deltaDepth = 0

        #----------------------------------
        # Check alert state
        # -> change alert parameters here
        #----------------------------------

        self.minload = 15 + cableWeight
        self.totalweight = 130 + cableWeight

        alertState = 0
        alertState += LOADALERT(self.minload, cableWeight, settings.warn_load)
        alertState += PRESSUREALERT(12)
        alertState += CURRENTALERT(settings.warn_motorI)

        #---------------------------------


        def updateAlert(alertLabel, position, alarm_condition, warn_condition=None, auxLabel=None):
            if position is None:
                alertLabel["bg"] = COLOR_BG
            elif position % 2 == 0:
                alertLabel["bg"] = left_box_color1
            else:
                alertLabel["bg"] = left_box_color2

            if auxLabel is not None:
                auxLabel["bg"] = COLOR_BG
                
            if warn_condition is not None and warn_condition():
                alertLabel["bg"] = COLOR_OBS_HEX

                if auxLabel is not None:
                    auxLabel["bg"] = COLOR_OBS_HEX
                
            if alarm_condition is not None and alarm_condition():
                alertLabel["bg"] = COLOR_WARN_HEX

                if auxLabel is not None:
                    auxLabel["bg"] = COLOR_WARN_HEX


        updateAlert(self.loadAlert,     0,    lambda: loadAlert,    lambda: loadWarning, self.loadDisplay)
        updateAlert(self.currentAlert,  1,    lambda: currentAlert, None,                self.currentDisplay)
        updateAlert(self.pressureAlert, 2,    lambda: False)
        updateAlert(self.gyroAlert,     3,    lambda: datetime.datetime.now().timestamp() <= gyrosliptimeout)
        
        updateAlert(self.spinLabel,     None, lambda: drill_state.get_spin() is not None and drill_state.get_spin() >= 3)
        
                    
        #----------------------------------
        # Update interface
        #----------------------------------
        def set_var(variable, format, value):
            try:
                variable.set(format % value)
            except Exception as e:
                # print("set_var exception: %s" % e)
                variable.set('N/A')

        set_var(self.aziVar,               '%.0f°',             drill_state.get_azimuth())
        set_var(self.incVar,               '%.1f°',             drill_state.get_inclination())
        set_var(self.m_currentVar,         '%.1f A',            drill_state.get('motor_current'))
        set_var(self.m_rpmVar,             '%.0f RPM',          drill_state.get('motor_rpm'))
        set_var(self.m_voltageVar,         '%.0f V',            drill_state.get('motor_voltage'))
        set_var(self.m_dutyCycleVar,       '%.1f %%',           100 * drill_state.get('motor_duty_cycle'))
        #print(self.m_voltageVar.get())
        set_var(self.w_loadVar,            '%.0f kg',           load)
        set_var(self.w_depthVar,           '%.2f',              depth)
        set_var(self.w_velocityVar,        '%.0f cm/s',         velocity*100)
        set_var(self.w_meanVelVar,         '%.2f cm/s',         meanVelocity*100)

        set_var(self.hammerVar,            '%d %%',             100 * float(drill_state.get('hammer'))/settings.max_hammer)
        set_var(self.downholeVoltageVar,   '%.1f V',            drill_state.get('downhole_voltage'))
        set_var(self.spinVar,              '%.1f rpm',          drill_state.get_spin())
        set_var(self.p_sens1Var,           '%.0f mbar\n%d °C', (drill_state.get('pressure_electronics'),
                                                                drill_state.get('aux_temperature_electronics')))
        set_var(self.p_sens2Var,           '%.0f mbar\n%d °C', (drill_state.get('pressure_topplug'),
                                                                drill_state.get('aux_temperature_topplug')))
        set_var(self.p_sens3Var,           '%.0f mbar\n%d °C', (drill_state.get('pressure_gear1'),
                                                                drill_state.get('aux_temperature_gear1')))
        set_var(self.p_sens4Var,           '%.0f mbar\n%d °C', (drill_state.get('pressure_gear2'),
                                                                drill_state.get('aux_temperature_gear2')))
        set_var(self.t_sens1Var,           '%.1f °C',           drill_state.get('temperature_electronics'))
        set_var(self.t_sens2Var,           '%.1f °C',           drill_state.get('temperature_motor'))
        set_var(self.t_sens3Var,           '%.1f °C',           drill_state.get('motor_controller_temp'))
        self.gyro_alarmVal = drill_state.get('gyro_alarm')
        set_var(self.n_gyroalarmVar,       '%u x 30°',          0x7F & self.gyro_alarmVal)

        #set_var(self.n_tachoVar,           '%1d',               drill_state.get('tachometer'))
        set_var(self.n_tachoVar,           '%.2f',               float(drill_state.get('tachometer'))/560.0)

        #NewGyroAlarm_state = NewGyroAlarm_state
        
        if (self.gyro_alarmVal & 0x80) != 0:
            NewGyroAlarm_state = True

        
         
        if NewGyroAlarm_state:
            set_var(self.resetNewGyroalarmTextVar, '%s', 'Alarm')
            self.NewGyroAlarmButt.configure( bg = COLOR_WARN_HEX)
            #bg=COLOR_WARN_HEX
        else:
            set_var(self.resetNewGyroalarmTextVar, '%s', "-----")
            self.NewGyroAlarmButt.configure( bg = COLOR_OK_HEX)
            #bg=COLOR_OK_HEX

        #set_var(self.inclination_xVar,    '%.1f °',          drill_state.get('inclination_x')/100.0)
        #set_var(self.inclination_yVar,    '%.1f °',          drill_state.get('inclination_y')/100.0)
        set_var(self.inclination_xVar,    '%.1f °',          drill_state.get('inclination_x'))
        set_var(self.inclination_yVar,    '%.1f °',          drill_state.get('inclination_y'))

        #'magnetometer_x'
        #set_var(self.magnetometer_xVar,    '%.1f °',          drill_state.get('magnetometer_x'))
        set_var(self.magnetometer_xVar,    '%.1f',              drill_state.get('magnetometer_x'))
        set_var(self.magnetometer_yVar,    '%.1f',              drill_state.get('magnetometer_y'))
        set_var(self.magnetometer_zVar,    '%.1f',              drill_state.get('magnetometer_z'))

        set_var(self.bh_maxDepthVar,       '%.2f',              bh_maxDepth)
        set_var(self.w_depth_maxDepthVar,  '%.2f / %.2f m',     (depth, bh_maxDepth))

        set_var(self.bh_lastStartDepthVar, '%.2f m',            bh_lastStartDepth)
        set_var(self.bh_lastStopDepthVar,  '%.2f m',            bh_lastStopDepth)
        set_var(self.bh_startDepthVar,     '%.2f m',            bh_startDepth)
        set_var(self.bh_stopDepthVar,      '%.2f m',            bh_stopDepth)

        set_var(self.bh_deltaDepthVar,     '%.2f m',            bh_deltaDepth)
        set_var(self.bh_lastDeltaDepthVar, '%.2f m',            bh_lastDeltaDepth)
        set_var(self.bh_LLevelVar,         '%.0f m',            bh_LLevel)

        set_var(self.netLoadStringVar,     '%d kg',             surface_state.get_net_load())

        if (getTare() > 0):
            set_var(self.cutterLoadStringVar,'%.02f kg',        getTare() - surface_state.load)
        else:
            self.cutterLoadStringVar.set("N/A")
    
        self.bh_lastRunTimeVar.set(sec2hms(bh_lastRunTime))

        if state_drilling:
            self.bh_currentRunTimeVar.set(sec2hms(time.time()-bh_startTime))
        else:
            self.bh_currentRunTimeVar.set('00:00')


        # update load plot
        #-----------------
        self.updateplot()

        # update azimuth widget
        #---------------------
        self.azimuthwidget.delete("azi_arrow")

        aziArrowCoord = []

        try:
            a = math.radians(drill_state.get_azimuth())

            aziArrowCoord.append(rotate((50,10), (50,50), a))
            aziArrowCoord.append(rotate((65,60), (50,50), a))
            aziArrowCoord.append(rotate((35,60), (50,50), a))
            self.azimuthwidget.create_polygon(aziArrowCoord, tag="azi_arrow", fill="black")
        except TypeError:
            # if we don't have orientation, why even draw the arrow?
            pass


        # update delta depth widget
        #--------------------------

        self.deltaDepthwidget.delete('deltaBar')
        self.deltaDepthwidget.create_rectangle(0,0, min([deltaDepthwidget_width, bh_deltaDepth/3.7 * deltaDepthwidget_width])  ,40,fill=COLOR_OK_HEX,tag='deltaBar')

        self.deltaDepthwidget.itemconfigure('deltatext', text='{:.2f}m'.format(bh_deltaDepth))
        self.deltaDepthwidget.tag_raise('deltatext', 'deltaBar')


        # update rotation widget
        #--------------------------

        self.rotationwidget.delete("rotate_arrow_1")
        self.rotationwidget.delete("rotate_arrow_2")
        self.rotationwidget.delete("rotate_arrow_3")
        
        i = drill_state.get('tachometer')*360/560
        RotaDeg = 150.0 + i
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*40.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*40.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*30.0+40+10,
                                            tag="rotate_arrow_2", fill="black")
        
        RotaDeg = 270.0 + i
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*40.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*40.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*30.0+40+10,
                                            tag="rotate_arrow_3", fill="green")
        
        RotaDeg = 30.0 + i
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*40.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*40.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*30.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*30.0+40+10,
                                            tag="rotate_arrow_1", fill="black")
        j = self.rotateVar.get()
        RotaDeg = 150.0 + i + j
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*30.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*20.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*20.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*20.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*20.0+40+10,
                                            tag="rotate_arrow_2", fill="black")
        
        RotaDeg = 270.0 + i + j
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*30.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*20.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*20.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*20.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*20.0+40+10,
                                            tag="rotate_arrow_3", fill="green")
        
        RotaDeg = 30.0 + i + j
        self.rotationwidget.create_polygon( math.cos(-RotaDeg*6.28/360.0)*30.0+40+10, -1*math.sin(-RotaDeg*6.28/360.0)*30.0+40+10,
                                            math.cos(-(RotaDeg+6)*6.28/360.0)*20.0+40+10, -1*math.sin(-(RotaDeg+6)*6.28/360.0)*20.0+40+10,
                                            math.cos(-(RotaDeg-6)*6.28/360.0)*20.0+40+10, -1*math.sin(-(RotaDeg-6)*6.28/360.0)*20.0+40+10,
                                            tag="rotate_arrow_1", fill="black")


    def updateplot(self):
        global load_plot, depth_plot, depth_plot_mask

        self.loadplotframe.delete("loadplot")
        [outArray, scale, array_width, yAmark] = createPlotArray(load_plot, 800, PLOT_H, 60, self.minload, self.totalweight)
#        print outArray
        self.loadplotframe.create_line(outArray, fill='black', width=3, smooth=1, tag= "loadplot")

        self.loadplotframe.delete("plotscale")
        for i in scale:
            self.loadplotframe.create_line(52,i[0],60,i[0], fill="black", width=1, tag= "plotscale")
            self.loadplotframe.create_line(800,i[0],808,i[0], fill="black", width=1, tag= "plotscale")
            self.loadplotframe.create_text(50,i[0], text='{:.1f}'.format(i[1]), anchor='e',  tag= "plotscale")
            self.loadplotframe.create_text(812,i[0], text='{:.1f}'.format(i[1]), anchor='w',  tag= "plotscale")

        self.loadplotframe.delete('plotAlertMarker')


        if yAmark[1] == 15:
            self.loadplotframe.create_polygon(790,yAmark[1],810,yAmark[1],800,yAmark[1]-15 , tag="plotAlertMarker", fill=COLOR_OK_HEX)
        elif yAmark[1] == 585:
            self.loadplotframe.create_polygon(790,yAmark[1],810,yAmark[1],800,yAmark[1]+15 , tag="plotAlertMarker", fill=COLOR_OK_HEX)
        else:
            self.loadplotframe.create_polygon(795,yAmark[1],815,yAmark[1]+10,815,yAmark[1]-10 , tag="plotAlertMarker", fill=COLOR_OK_HEX)

        if yAmark[0] == 15:
            self.loadplotframe.create_polygon(790,yAmark[0],810,yAmark[0],800,yAmark[0]-15 , tag="plotAlertMarker", fill=COLOR_WARN_HEX)
        elif yAmark[0] == 585:
            self.loadplotframe.create_polygon(790,yAmark[0],810,yAmark[0],800,yAmark[0]+15 , tag="plotAlertMarker", fill=COLOR_WARN_HEX)
        else:
            self.loadplotframe.create_polygon(795,yAmark[0],815,yAmark[0]+10,815,yAmark[0]-10 , tag="plotAlertMarker", fill=COLOR_WARN_HEX)


        self.loadplotframe.delete('plotdepthscale')

        j = 0
        for i in range(len(depth_plot_mask)):
            if depth_plot_mask[i] == 1:
                k = float(i) * array_width / len(depth_plot_mask) +60
                self.loadplotframe.create_line(k,0,k,590, fill=COLOR_BLUE_HEX, width=1.5, tag= "plotdepthscale")
                self.loadplotframe.create_text(k,605, text='{:.2f}'.format(depth_plot[j]), anchor='s',  tag= "plotdepthscale")
                j +=1



    
    #def startMotorThrottle(self):
    def startMotorThrottle(self, pos=0):
        pwm = int(self.pwmVar.get())

        if pwm >= -255 and pwm <= 255:
            redis_conn.publish('downhole','motor-pwm:%d' % pwm)
            #print("Hello...")
        else:
            print("PWM out of range")


    def startMotorRPM(self):
        rpm = int(self.rpmVar.get())

        if rpm >= -120 and rpm <= 120:
            redis_conn.publish('downhole','motor-rpm:%d' % rpm)
        else:
            print("RPM out of range")

    def smallRotation(self, pwm, sleeptime):
        def worker():
            redis_conn.publish('downhole', 'motor-pwm:%d' % pwm)
            time.sleep(sleeptime)
            redis_conn.publish('downhole', 'motor-stop')

        t = threading.Thread(target=worker)
        t.start()
        
    def stopMotor(self):
        redis_conn.publish('downhole','motor-stop')
        self.MyScale.set(0)

    def setMotor(self, motor_id):
        if motor_id == 0:
            redis_conn.publish('downhole','motor-config:parvalux')
        elif motor_id == 1:
            redis_conn.publish('downhole','motor-config:skateboard')
        elif motor_id == 2:
            redis_conn.publish('downhole','motor-config:hacker')
        elif motor_id == 3:
            redis_conn.publish('downhole','motor-config:plettenberg')

    def RotateMotor(self, degrees = 0, pwm = 10, pos = '0'):

        print("What: %d" % int(pos))
        
        #degrees = int(self.rotateVar.get())
        degrees = self.rotateVar.get()
        self.rotateVar.set(0)
        
        redis_conn.publish('downhole', 'motor-rotate-by: %d, %d,' % (degrees, pwm))

    def SetTacho(self, tacho_index):

        print("Tacho index: %d" % int(tacho_index))
        
        #degrees = self.rotateVar.get()
        
        redis_conn.publish('downhole', 'motor-set-tachometer: %d' % tacho_index)



app=App()
