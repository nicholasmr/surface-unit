# N. Rathmann <rathmann@nbi.dk>, 2019-2024

import sys, os, signal, datetime
import numpy as np
from functools import partial

from settings import *
from state_drill import *
from state_surface import *

from PyQt5.QtCore import * 
from PyQt5.QtWidgets import * 
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

#import qwt # https://pypi.org/project/PythonQwt/
import pyqtgraph as pg

#-------------------
# Settings
#-------------------

DT           = 1/8 # update rate in seconds for GUI/surface state
DTFRAC_DRILL = 4 # update the drill state every DTFRAC_DRILL times the GUI/surface state is updated (was 7 previously)

tavg = 3 # time-averging length in seconds for velocity estimate

ALWAYS_SHOW_DRILL_FIELDS = True # ignore if drill is offline and show last recorded redis fields for drill

FS = 13
FS_GRAPH_TITLE = 5 # font size for graph titles
PATH_SCREENSHOT = "/mnt/logs/screenshots"
os.system('mkdir -p %s'%(PATH_SCREENSHOT))

# Print settings
print('%s: running with DT=%.3fs, DT_DRILL=%.3fs'%(sys.argv[0],DT,DT*DTFRAC_DRILL))

# GUI colors
COLOR_GRAYBG = '#f0f0f0'
COLOR_GREEN = '#66bd63'
COLOR_RED   = '#f46d43'
COLOR_DARKRED   = '#b2182b'
COLOR_DARKGREEN = '#1a9850'

COLOR_SLOT0  = '#3182bd'
COLOR_SLOT1 = "#969696"

COLOR_DIAL1  = '#01665e'
COLOR_DIAL1l = '#c7eae5'
COLOR_DIAL2  = '#8c510a'
COLOR_DIAL2l = '#dfc27d'

#-------------------
# Program start
#-------------------

class MainWidget(QWidget):

    runtime0 = None
    Nt = 0 # number of time steps taken

    loadmeasures      = {'hist_load':'Load', 'hist_loadnet':'Load - cable', 'hist_loadtare':'Tare load'}
    loadmeasure_inuse = 'hist_load'

    xlen            = [int(0.5*60), int(2*60), int(10*60), int(45*60)] 
    xlen_names      = ["1/2m", "2m", "10m", "45m"]
    xlen_samplerate = [1,1,1,1]  
    xlen_selector   = {'speed':0, 'load':0, 'current':0, 'incl':2} # default selection
    
    minYRange_load = 20 # kg
    minYRange_speed = 10.5 # cm/s
    maxYRange_speed = 150 # cm/s
    
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

        #self.hist_depth     = np.full(len(self.hist_time_drill), 0.0)
        #self.hist_incl_sfus = np.full(len(self.hist_time_drill), 0.0)
        #self.hist_incl_ahrs = np.full(len(self.hist_time_drill), 0.0)
        
        self.hist_depth     = np.linspace(0,-2900,len(self.hist_time_drill)) 
        self.hist_incl_sfus = np.linspace(0,8,len(self.hist_time_drill)) 
        self.hist_incl_ahrs = np.linspace(0,5,len(self.hist_time_drill)) 

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
    
        self.plot_incl = pg.PlotWidget();  
        self.plot_incl.setXRange(0, 8, padding=0)
        self.plot_incl.setYRange(-2.9*1e3, 0, padding=0)
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

        # init curves
        lw = 3
        plotpen_black = pg.mkPen(color='k', width=lw)
        self.curve_load    = self.plot_load.plot(    x=self.hist_time,y=self.hist_time*0-1e4, pen=plotpen_black)
        self.curve_speed   = self.plot_speed.plot(   x=self.hist_time,y=self.hist_time*0-1e4, pen=plotpen_black)
        self.curve_current = self.plot_current.plot( x=self.hist_time_drill,y=self.hist_time_drill*0-1e4, pen=plotpen_black)


        ###########

        # EGRIP
#        logger_depth = np.array([67,67,67,67,67,67,67,67,67,67,67,67,67,67,67,67,67,67,69,70,70,70,70,70,70,70,66,66,66,68,72,77,80,80,80,80,85,90,96,99,100,100,100,101,105,109,113,117,119,120,120,120,123,129,134,138,140,140,140,140,145,150,154,159,160,160,160,160,160,160,165,169,174,179,180,180,180,180,180,180,180,180,182,187,191,196,199,200,200,200,200,200,204,209,219,219,219,219,222,227,232,237,240,240,240,244,248,253,258,259,260,260,260,265,270,275,279,280,280,280,281,286,291,296,299,300,300,300,300,300,303,308,313,319,324,325,325,325,325,327,332,337,342,347,350,350,350,351,355,360,364,369,373,375,375,375,375,379,384,389,394,399,400,400,400,406,411,416,422,425,425,425,425,425,425,427,432,437,443,448,450,450,450,450,453,458,464,469,474,475,475,475,475,477,482,487,493,498,500,500,500,500,500,503,509,514,520,525,531,537,542,548,549,550,550,550,550,550,550,552,557,563,569,575,581,586,592,598,600,600,600,600,600,600,603,609,615,621,626,632,638,650,650,650,650,656,661,666,700,700,700,700,700,700,700,700,700,700,704,709,715,720,725,730,736,741,746,750,750,750,750,750,750,750,753,759,764,770,775,781,786,792,797,800,800,800,801,806,811,816,821,826,831,836,841,846,849,850,850,850,850,850,850,852,856,861,865,870,874,878,883,887,892,896,900,900,900,900,901,907,913,918,924,930,936,941,947,950,950,950,950,950,956,962,967,973,979,984,990,996,999,1000,1000,1000,1004,1011,1017,1023,1030,1036,1043,1048,1050,1050,1050,1050,1050,1050,1050,1050,1050,1050,1052,1058,1065,1071,1078,1084,1090,1097,1100,1100,1100,1100,1107,1113,1120,1126,1133,1139,1146,1150,1150,1150,1150,1150,1155,1161,1168,1175,1182,1189,1195,1200,1200,1200,1200,1206,1212,1219,1225,1232,1239,1245,1249,1250,1250,1250,1250,1250,1255,1261,1267,1273,1279,1285,1292,1297,1300,1300,1300,1300,1300,1304,1310,1315,1321,1327,1332,1338,1343,1349,1350,1350,1350,1350,1350,1350,1354,1359,1364,1369,1374,1379,1384,1389,1394,1399,1400,1400,1400,1400,1400,1400,1400,1400,1400,1400,1400,1400,1400,1400,1400,1400,1405,1411,1417,1422,1428,1433,1439,1445,1449,1450,1450,1450,1450,1450,1450,1453,1459,1465,1470,1476,1482,1487,1493,1499,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1500,1502,1507,1512,1517,1522,1528,1533,1538,1543,1548,1550,1550,1550,1550,1550,1550,1550,1555,1560,1565,1570,1575,1581,1586,1591,1596,1599,1600,1600,1600,1600,1600,1600,1600,1600,1600,1600,1600,1605,1610,1615,1620,1624,1629,1634,1639,1644,1649,1649,1650,1650,1650,1650,1650,1654,1658,1663,1667,1671,1676,1680,1685,1689,1693,1698,1700,1700,1700,1700,1700,1700,1703,1707,1712,1716,1721,1725,1730,1734,1738,1743,1747,1749,1750,1750,1750,1750,1750,1750,1755,1760,1764,1769,1774,1778,1783,1788,1792,1797,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1800,1805,1809,1814,1818,1823,1825,1825,1825,1825,1825,1825,1825,1825,1825,1826,1830,1835,1840,1845,1849,1850,1850,1850,1850,1850,1850,1850,1850,1850,1850,1850,1850,1850,1850,1853,1858,1862,1866,1870,1874,1875,1875,1875,1875,1875,1875,1875,1875,1879,1884,1889,1894,1899,1900,1900,1900,1900,1900,1900,1900,1900,1903,1907,1911,1915,1919,1923,1925,1925,1925,1925,1925,1925,1930,1934,1938,1943,1947,1949,1950,1950,1950,1950,1952,1956,1960,1965,1969,1973,1975,1975,1975,1975,1975,1975,1975,1975,1979,1983,1987,1992,1996,1999,2000,2000,2000,2000,2001,2005,2009,2013,2018,2022,2025,2025,2025,2025,2025,2025,2026,2030,2035,2040,2044,2049,2050,2050,2050,2050,2051,2056,2060,2064,2068,2072,2074,2075,2075,2075,2075,2076,2080,2084,2089,2093,2098,2100,2100,2100,2100,2100,2100,2100,2102,2107,2111,2116,2121,2124,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2125,2129,2134,2139,2143,2148,2150,2150,2150,2150,2150,2150,2150,2150,2150,2150,2150,2150,2150,2150,2154,2159,2163,2167,2171,2174,2175,2175,2175,2175,2175,2175,2175,2175,2175,2175,2175,2175,2176,2181,2185,2189,2194,2198,2199,2200,2200,2200,2200,2200,2200,2200,2200,2200,2200,2200,2201,2206,2210,2220,2220,2220,2220,2220,2220,2220,2223,2227,2232,2236,2239,2240,2240,2240,2240,2240,2240,2240,2241,2245,2249,2253,2256,2259,2260,2260,2260,2260,2264,2268,2273,2277,2280,2280,2280,2280,2280,2282,2287,2291,2296,2299,2300,2300,2300,2305,2309,2310,2310,2310,2311,2315,2317,2319,2320,2320,2320,2321,2323,2325,2327,2329,2330,2330,2330,2330,2330,2332,2334,2335,2337,2339,2340,2340,2340,2340,2340,2340,2340,2342,2344,2346,2348,2350,2350,2350,2350,2351,2353,2355,2357,2359,2360,2360,2360,2360,2360,2360,2360,2361,2363,2365,2367,2369,2370,2370,2370,2370,2370,2370,2370,2370,2372,2374,2377,2379,2380,2380,2380,2380,2380,2380,2380,2382,2384,2385,2387,2389,2390,2390,2390,2390,2390,2390,2390,2390,2390,2390,2392,2394,2396,2397,2399,2400,2400,2400,2400,2400,2400,2400,2400,2402,2404,2406,2407,2409,2409,2410,2410,2410,2410,2410,2410,2410,2410,2411,2412,2412,2412,2412,2412,2412,2411,2410,2411,2412,2412])
#        logger_incl = np.array([2.74,2.74,2.74,2.75,2.76,2.74,2.74,2.74,2.75,2.74,2.75,2.75,2.74,2.73,2.74,2.76,2.75,2.77,2.43,2.45,2.44,2.47,2.44,2.46,2.46,3.45,2.19,2.18,2.17,2.90,3.10,3.36,2.62,2.63,2.65,2.98,3.82,4.30,3.02,2.81,3.23,3.20,3.18,4.37,4.05,2.03,2.75,3.33,3.08,3.11,3.13,3.09,3.53,3.78,2.38,3.03,3.17,3.18,3.17,2.87,3.17,2.69,3.02,3.52,3.29,3.26,3.27,3.27,3.26,2.97,3.10,4.17,3.48,2.65,3.33,3.36,3.35,3.32,3.34,3.34,3.34,3.36,3.65,3.77,3.11,4.09,3.32,3.43,3.42,3.41,3.41,3.39,3.71,3.03,3.56,3.42,3.39,3.41,3.46,2.75,4.17,3.44,3.43,3.40,3.41,3.21,3.67,3.13,3.72,3.38,3.46,3.41,3.60,3.73,3.61,3.66,3.52,3.49,3.48,3.48,4.08,3.44,3.91,3.92,3.72,3.49,3.49,3.50,3.52,3.52,4.28,3.10,3.82,3.35,3.55,3.70,3.67,3.70,3.67,4.08,3.88,4.15,3.83,4.01,3.99,3.97,3.98,4.03,4.33,4.23,4.25,4.15,4.01,4.25,4.29,4.25,4.25,4.44,4.26,4.12,4.36,4.32,4.48,4.47,4.09,4.47,4.75,4.34,4.30,4.64,4.66,4.67,4.67,4.69,4.69,4.59,4.90,4.65,4.28,4.74,4.80,4.78,4.77,4.78,4.55,4.77,5.04,4.88,4.91,4.83,4.82,4.83,4.82,5.02,4.78,5.09,4.93,4.68,4.92,4.93,4.94,4.92,4.92,4.93,4.85,5.31,5.39,5.38,5.52,5.00,5.11,5.32,5.38,5.39,5.36,5.37,5.37,5.36,5.37,5.54,5.05,5.27,5.27,5.43,5.45,5.45,5.31,5.18,5.10,5.09,5.11,5.09,5.07,5.09,5.26,4.89,4.64,4.11,4.03,4.04,4.08,3.68,3.67,3.70,3.78,3.53,3.73,3.57,2.94,2.96,2.94,2.94,2.94,2.95,2.94,2.95,2.93,2.95,2.93,3.19,2.54,2.61,2.43,2.19,2.59,2.32,2.51,2.73,2.71,2.72,2.76,2.72,2.73,2.76,3.00,3.10,3.25,3.90,3.67,3.54,4.16,4.18,4.38,4.56,4.56,4.55,4.94,4.80,5.00,4.57,4.50,4.47,4.82,4.60,4.46,4.28,4.32,4.36,4.38,4.36,4.36,4.36,4.36,4.60,4.71,4.25,4.08,4.18,3.76,3.43,3.18,2.87,2.76,2.46,2.34,2.34,2.36,2.36,2.57,2.60,2.31,2.39,2.46,2.67,2.66,2.51,2.32,2.48,2.49,2.49,2.49,2.56,2.31,2.64,2.40,2.37,2.07,2.28,2.33,2.16,2.44,2.28,2.29,2.27,2.24,2.77,1.72,1.99,2.92,2.29,1.92,2.12,2.29,2.29,2.29,2.28,2.29,2.29,2.29,2.29,2.29,2.31,1.96,2.52,2.69,2.60,1.94,2.11,2.40,2.24,2.28,2.26,2.24,1.93,2.55,2.31,2.74,2.56,2.50,2.79,2.09,2.70,2.72,2.71,2.72,2.72,3.59,2.52,3.13,2.98,2.85,3.15,2.69,3.13,3.12,3.13,3.15,3.05,2.55,3.24,3.27,3.27,3.06,2.99,3.24,3.16,3.18,3.16,3.17,3.16,3.31,3.37,3.02,3.31,3.41,3.22,3.52,3.44,3.48,3.47,3.48,3.49,3.49,3.45,3.55,3.67,3.57,3.56,3.68,3.40,3.16,3.65,3.42,3.41,3.42,3.42,3.43,3.43,3.38,3.31,3.30,3.39,3.54,3.48,3.67,3.59,3.40,3.55,3.42,3.43,3.44,3.42,3.43,3.44,3.46,3.43,3.45,3.46,3.45,3.44,3.43,3.43,3.45,3.44,3.38,3.47,3.27,3.21,3.41,3.39,3.73,2.78,3.41,3.22,3.22,3.22,3.23,3.23,3.23,3.04,3.28,3.39,2.99,3.24,3.44,3.02,3.66,3.91,3.36,3.35,3.34,3.33,3.37,3.39,3.36,3.34,3.34,3.34,3.36,3.36,2.98,3.48,3.56,3.53,3.72,3.26,3.55,3.77,3.46,3.88,3.63,3.60,3.61,3.60,3.61,3.60,3.60,3.60,3.85,3.59,3.48,3.97,4.22,3.83,3.59,3.61,3.80,3.79,3.78,3.78,3.79,3.82,3.80,3.80,3.78,3.80,3.82,3.90,3.77,3.75,3.61,3.68,3.56,3.45,3.10,3.70,3.66,3.63,3.65,3.66,3.66,3.65,3.64,3.65,3.48,4.07,3.58,3.10,3.68,3.48,3.43,3.54,3.40,3.67,3.42,3.37,3.35,3.36,3.35,3.34,3.35,3.26,3.12,3.39,3.69,3.38,3.46,3.80,3.47,3.57,3.67,3.57,3.57,3.59,3.58,3.57,3.61,3.57,3.85,3.62,3.91,3.58,3.42,3.32,3.90,3.73,2.84,3.83,3.21,3.49,3.50,3.51,3.50,3.50,3.50,3.51,3.50,3.50,3.50,3.50,3.50,3.52,3.50,3.51,3.50,3.50,3.51,3.50,3.49,3.51,3.50,3.46,3.17,3.33,3.34,3.71,3.20,3.49,3.48,3.48,3.50,3.50,3.50,3.48,3.49,3.48,3.40,4.28,2.96,3.49,2.48,2.12,3.42,3.43,3.44,3.37,3.42,3.41,3.42,3.42,3.41,3.43,3.42,3.43,3.41,3.40,4.02,3.19,3.32,3.18,3.45,4.06,3.38,3.35,3.41,3.40,3.38,3.36,3.36,3.38,3.54,3.68,3.21,3.21,3.92,3.40,3.44,3.44,3.39,3.41,3.39,3.41,3.42,3.23,2.76,3.98,3.26,3.34,2.91,3.47,3.48,3.48,3.47,3.48,3.84,3.38,3.43,3.24,2.22,3.93,3.52,3.45,3.45,3.47,3.48,4.57,3.61,3.30,3.26,2.25,2.99,3.38,3.41,3.37,3.38,3.39,3.39,3.38,3.37,4.96,2.86,2.28,3.10,4.25,3.08,3.21,3.22,3.24,3.24,2.76,2.11,2.65,2.76,2.63,1.37,3.15,3.15,3.18,3.17,3.16,3.17,2.27,3.14,5.01,2.32,3.25,2.20,3.07,3.08,3.07,3.07,3.51,2.50,4.48,4.07,2.72,2.77,2.91,3.12,3.10,3.10,3.12,3.12,3.96,3.59,2.35,2.65,4.24,2.96,2.91,2.91,2.93,2.91,2.91,2.91,2.39,3.30,3.24,3.55,3.03,2.82,2.83,2.79,2.86,2.81,2.82,2.82,2.82,2.81,2.81,2.83,2.81,2.85,2.85,2.83,2.81,2.83,2.82,2.83,2.82,2.82,2.84,2.81,2.82,2.83,2.82,2.82,2.82,2.82,2.89,3.75,3.45,3.62,2.90,2.79,2.81,2.81,2.81,2.80,2.80,2.83,2.79,2.81,2.77,2.81,2.79,2.81,2.78,3.01,2.98,3.04,3.04,3.45,2.63,2.76,2.75,2.76,2.75,2.73,2.73,2.75,2.75,2.73,2.77,2.73,2.77,2.38,3.39,2.87,2.41,3.09,2.48,2.70,2.70,2.69,2.71,2.70,2.71,2.71,2.70,2.73,2.69,2.73,2.72,2.92,1.31,2.14,2.74,2.76,2.76,2.73,2.76,2.75,2.77,1.84,3.20,2.45,3.89,3.10,2.87,2.85,2.86,2.86,2.87,2.88,2.86,4.06,2.78,2.65,2.82,4.23,3.01,2.94,2.96,2.96,2.97,3.00,3.02,2.69,3.40,3.68,3.14,3.14,3.15,3.15,3.64,3.16,3.07,2.89,3.46,3.24,3.23,2.60,2.80,3.41,3.33,3.31,3.31,2.75,3.21,2.61,3.18,3.37,3.38,3.40,3.37,3.14,2.91,3.60,3.26,3.41,3.40,3.39,3.40,3.20,3.69,3.28,3.33,3.32,3.07,3.35,3.36,3.35,3.35,3.36,3.36,3.74,3.07,3.45,3.45,3.55,2.99,3.32,3.34,3.34,3.71,3.56,3.64,2.76,3.56,3.35,3.33,3.35,3.34,3.35,3.35,3.33,4.08,3.51,3.90,3.48,3.02,3.54,3.51,3.52,3.51,3.54,3.52,3.54,3.33,3.67,3.41,3.35,3.33,3.50,3.48,3.49,3.48,3.48,3.47,3.50,2.90,3.46,3.33,3.91,3.17,3.55,3.55,3.54,3.54,3.53,3.52,3.55,3.54,3.54,4.07,3.31,2.92,3.64,3.27,2.65,3.65,3.68,3.67,3.68,3.67,3.70,3.71,4.52,3.49,3.62,4.07,3.25,3.37,3.62,3.64,3.60,3.64,3.61,3.61,3.64,3.61,3.60,4.80,3.63,3.64,3.62,3.62,3.61,3.62,4.05,3.62,3.90,3.40,3.66])

        logger_depth = np.array([])
        logger_incl = np.array([])

        self.incl_scatter0 = pg.ScatterPlotItem(size=8, symbol='o', pen=None, brush=pg.mkBrush(100,100,100)) #brush=pg.mkBrush(30, 255, 35, 255))
        self.incl_scatter0.setData(logger_incl, -logger_depth)
        self.plot_incl.addItem(self.incl_scatter0)

        self.incl_scatter = pg.ScatterPlotItem(size=8, pen=None, brush=pg.mkBrush(239,59,44))
        self.incl_scatter.setData(self.hist_incl_sfus, self.hist_depth)
        self.plot_incl.addItem(self.incl_scatter)
#        self.curve_incl = self.plot_current.plot( x=self.hist_depth,y=self.hist_incl_sfus, pen=plotpen_black)

        ### State fields

        self.create_gb_surface()
        self.create_gb_orientation()
        self.create_gb_temperature()
        self.create_gb_pressure()
        self.create_gb_other()
        self.create_gb_motor()
        self.create_gb_run()
        self.create_gb_status()
        self.create_gb_bno055calib()
        self.create_gb_expert()

        ### QT Layout

        # Graphs (top)

        #w_btn = 100
        w_btn = 60
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
                
        plotLayout4 = QVBoxLayout() 
        plotLayout4.addWidget(self.plot_incl)
        plotLayout4btn = QHBoxLayout()
        plotLayout4btn.setSpacing(s_btn)
        plotLayout4btn.addStretch(1)
        incl_xlen_btn1 = QPushButton(self.xlen_names[0]); incl_xlen_btn1.clicked.connect(lambda: self.changed_xaxislen_incl(0)); incl_xlen_btn1.setMaximumWidth(w_btn); plotLayout4btn.addWidget(incl_xlen_btn1)
        incl_xlen_btn2 = QPushButton(self.xlen_names[1]); incl_xlen_btn2.clicked.connect(lambda: self.changed_xaxislen_incl(1)); incl_xlen_btn2.setMaximumWidth(w_btn); plotLayout4btn.addWidget(incl_xlen_btn2)
        incl_xlen_btn3 = QPushButton(self.xlen_names[2]); incl_xlen_btn3.clicked.connect(lambda: self.changed_xaxislen_incl(2)); incl_xlen_btn3.setMaximumWidth(w_btn); plotLayout4btn.addWidget(incl_xlen_btn3)
        incl_xlen_btn4 = QPushButton(self.xlen_names[3]); incl_xlen_btn4.clicked.connect(lambda: self.changed_xaxislen_incl(3)); incl_xlen_btn4.setMaximumWidth(w_btn); plotLayout4btn.addWidget(incl_xlen_btn4)
        plotLayout4btn.addStretch(2)
        plotLayout4.addLayout(plotLayout4btn)

        topLayout.addLayout(plotLayout1,1)
        topLayout.addLayout(plotLayout2,3)
        topLayout.addLayout(plotLayout3,1)
        topLayout.addLayout(plotLayout4,1)

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
#        botLayoutSub1.addWidget(QLabel('')) # spacer
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
#        self.gb_run_peakload            = self.MakeStateBox('run_peakload',   'Peak load, %is (kg)'%(self.xlen[0]), initstr)
        self.gb_run_peakload            = self.MakeStateBox('run_peakload',   'Peak load (kg)', initstr)
        layout.addWidget(self.gb_surface_depth)
        layout.addWidget(self.gb_surface_speed)
        layout.addWidget(self.gb_surface_load)
        layout.addWidget(self.gb_surface_loadcable)
        layout.addWidget(self.gb_run_deltaload)
        layout.addWidget(self.gb_run_peakload)
        layout.addStretch(1)
        self.gb_surface.setLayout(layout)

    def create_gb_orientation(self, initstr='N/A'):
        self.gb_orientation = QGroupBox("Orientation (deg)")
#        self.gb_orientation.setMinimumWidth(330)
        layout = QVBoxLayout()

        layout.addWidget(self.MakeStateBox('orientation_inclination',  'Inclination,  Azimuth,  Spring roll',  initstr))

        dlayout = QGridLayout()
        cdial = dict(dial_azim=COLOR_DIAL1, dial_roll=COLOR_DIAL2)
        for tt in ['dial_azim', 'dial_roll']:
            d = QDial()
            d.setNotchesVisible(True)
            d.setMinimum(-180)
            d.setMaximum(+180)
            d.setWrapping(True)
            d.setMinimumHeight(100)
#            d.setMaximumHeight(85)
#            if tt in ['dial_azim_sfus', 'dial_azim_ahrs']:
            d.setInvertedAppearance(True)
            d.setInvertedControls(True)
            d.setStyleSheet("background-color: %s; border : 2px solid black;"%(cdial[tt]));
            setattr(self, tt, d)
        dlayout.addWidget(self.dial_azim, 0,0)
        dlayout.addWidget(self.dial_roll, 0,1)
        btn_offset = QPushButton('Zero ref.') 
        btn_offset.clicked.connect(lambda: [None,self.ds.save_offset('sfus'),self.ds.save_offset('ahrs')][0]) 
        dlayout.addWidget(btn_offset, 1,0)
        btn_offset = QPushButton('Clear') 
        btn_offset.clicked.connect(lambda: [None,self.ds.save_offset('sfus',reset=True),self.ds.save_offset('ahrs',reset=True)][0]) 
        dlayout.addWidget(btn_offset, 1,1)
        layout.addLayout(dlayout)

        layout.addWidget(self.MakeStateBox('orientation_offsets', 'Offsets (incl, azim, roll)', initstr))
        layout.addWidget(self.MakeStateBox('orientation_quality', 'Sensor Q (sys, gyr, acc, mag)', initstr))

        #layout.addWidget(QLabel(' '))
        dlayout = QGridLayout()        
        lbl_method = QLabel('Method:')
        dlayout.addWidget(lbl_method, 0,0)
        self.cb_orimethod = QComboBox()
        self.cb_orimethod.addItems(["Sensor fusion", "AHRS"])
        self.cb_orimethod.currentIndexChanged.connect(self.changed_orimethod)
        self.orimethod = 'sfus'
        dlayout.addWidget(self.cb_orimethod,0,1)
        dlayout.setColumnStretch(2,1)
        layout.addLayout(dlayout)

        self.gb_BNO055 = QGroupBox("BNO055 triaxial values") # create already here because self.cb_show_bno055.setChecked() below requires it be defined
        layout_BNO055 = QVBoxLayout()
        layout_BNO055.addWidget(self.MakeStateBox('orientation_acceleration', 'Acceleration (m/s^2)', initstr))
        layout_BNO055.addWidget(self.MakeStateBox('orientation_magnetometer', 'Magnetometer (mT)',    initstr))   
        layout_BNO055.addWidget(self.MakeStateBox('orientation_gyroscope',    'Gyroscope (deg/s)',    initstr))
#        layout_BNO055.addWidget(self.MakeStateBox('orientation_linearacceleration', 'Linearacceleration (m/s^2)',    initstr))
#        layout_BNO055.addWidget(self.MakeStateBox('orientation_gravity',            'Gravity (m/s^2)',    initstr))
        layout_BNO055.addWidget(self.MakeStateBox('orientation_quaternion_sfus',    'Quaternion, SFUS (x,y,z,w)',    initstr))
        layout_BNO055.addWidget(self.MakeStateBox('orientation_quaternion_ahrs',    'Quaternion, AHRS (x,y,z,w)',    initstr))
        self.gb_BNO055.setLayout(layout_BNO055)
        self.cb_show_bno055 = QCheckBox("Show BNO055 details?")
        self.cb_show_bno055.toggled.connect(self.clicked_showhide_bno055)     
        self.cb_show_bno055.setChecked(self.SHOW_BNO055_DETAILED)
        self.clicked_showhide_bno055()
        layout.addWidget(self.cb_show_bno055)
        layout.addWidget(self.gb_BNO055)
                
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
        layout.addWidget(self.MakeStateBox('orientation_spin', 'Drill spin (RPM)',   initstr))
        self.gb_surface_downholevoltage = self.MakeStateBox('surface_downholevoltage', 'Downh. volt. (V)',   initstr)
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
        layout.addWidget(self.MakeStateBox('temperature_motorctrl',      'Motor ctr. (VESC)', initstr))
        layout.addStretch(1)
        self.gb_temperature.setLayout(layout)
        

    def create_gb_motor(self, initstr='N/A', btn_width=150):
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
#        layout.addWidget(QLabel('Press start to express'), row+3,1, 1,2)
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
#        self.dial_inching = QDial()
#        self.dial_inching.setNotchesVisible(True)
#        self.dial_inching.setMinimum(-180)
#        self.dial_inching.setMaximum(+180)
#        self.dial_inching.setWrapping(True)
#        self.dial_inching.setMaximumHeight(75)
#        layout.addWidget(self.dial_inching, row+1,2, 3,1)
#        layout.addWidget(QLabel('Press start to express'), row+3,1, 1,2)
        self.btn_inchingstart = QPushButton("Start")
        self.btn_inchingstart.setStyleSheet("background-color : %s"%(COLOR_GREEN))
        self.btn_inchingstart.clicked.connect(self.clicked_inchingstart)
        self.btn_inchingstart.setMinimumWidth(btn_width); self.btn_inchingstart.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_inchingstart, row+4,1)
#        layout.addWidget(QLabel(''), row,1)

        dlayout = QGridLayout()
        self.btn_inch5 = QPushButton("+5 deg")
        self.btn_inch5.setMaximumWidth(90)
        self.btn_inch5.clicked.connect(self.clicked_inching_5)
        dlayout.addWidget(self.btn_inch5, 0,1)
              
        self.btn_inch10 = QPushButton("+10 deg")
        self.btn_inch10.setMaximumWidth(90)
        self.btn_inch10.clicked.connect(self.clicked_inching_10)
        dlayout.addWidget(self.btn_inch10, 0,2)
              
        self.btn_inch120 = QPushButton("+120 deg")
        self.btn_inch120.setMaximumWidth(90)
        self.btn_inch120.clicked.connect(self.clicked_inching_120)
        dlayout.addWidget(self.btn_inch120, 0,3)
              
        layout.addLayout(dlayout,row+5, 1, 1, 2)
              
        ###              
        
        layout.setRowStretch(row+5, 1)
        self.gb_motor.setLayout(layout)
        
    def create_gb_run(self, initstr='N/A', btn_width=150):
        self.gb_run = QGroupBox("Current run")
        layout = QVBoxLayout()
        
        self.btn_startrun = QPushButton("Start")
        self.btn_startrun.setCheckable(True)
        self.btn_startrun.clicked.connect(self.clicked_startstop_run)
        self.btn_startrun.setStyleSheet("background-color : %s"%(COLOR_GREEN))
        #self.btn_startrun.setMinimumWidth(btn_width); self.btn_startrun.setMaximumWidth(btn_width)
        layout.addWidget(self.btn_startrun)

        self.cbox_settareload = QPushButton("Reset tare load")
        self.cbox_settareload.clicked.connect(self.clicked_resettareload)
        #self.cbox_settareload.setMinimumWidth(btn_width); self.cbox_settareload.setMaximumWidth(btn_width)
        layout.addWidget(self.cbox_settareload)
        
        self.btn_screenshot = QPushButton("Screenshot")
        self.btn_screenshot.clicked.connect(self.take_screenshot)
        #self.btn_screenshot.setMinimumWidth(btn_width); self.btn_screenshot.setMaximumWidth(btn_width)
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
        layout = QGridLayout()

#        layout.addWidget(QLabel(''))
        self.cbox_unlockexpert = QCheckBox("Unlock")
        self.cbox_unlockexpert.toggled.connect(self.clicked_unlockexpert)     
        layout.addWidget(self.cbox_unlockexpert)

#        layout.addWidget(QLabel(''))        
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
        
#        layout.addWidget(QLabel(''))
        self.cb_motorconfig_label = QLabel('Motor config:')
        self.cb_motorconfig_label.setEnabled(False)
        layout.addWidget(self.cb_motorconfig_label)
        self.cb_motorconfig = QComboBox()
        self.cb_motorconfig.addItems(["parvalux", "skateboard", "hacker", "plettenberg"])
        self.cb_motorconfig.currentIndexChanged.connect(self.changed_motorconfig)
        self.cb_motorconfig.setEnabled(False)
        layout.addWidget(self.cb_motorconfig)

#        layout.addStretch(3)
        layout.rowStretch(1)
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

    def create_gb_bno055calib(self, initstr='N/A'):
    
        self.gb_bno005calib = QGroupBox("BNO055 calibration")
        layout = QGridLayout()

        #btn_width = 33
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
            
#        layout.rowStretch(1)
        self.gb_bno005calib.setLayout(layout)

    ### User actions 
    
    # Orientation
    
    def changed_orimethod(self):
        self.orimethod = None
        if self.cb_orimethod.currentIndex()==0: self.orimethod = 'sfus'
        if self.cb_orimethod.currentIndex()==1: self.orimethod = 'ahrs'
        print('orimethod is now ', self.orimethod)
    
    # Motor
    
    def changed_throttle(self):
        self.sl_throttle_label.setText('Throttle: %i%%'%(self.sl_throttle.value()))
        
    def changed_sl_inching(self):
        deg = self.sl_inching.value()
#        self.dial_inching.setValue(deg)
        self.sl_inching_label.setText('Inching: %+i deg'%(deg))
        
    def clicked_motorstart(self):
        throttle_pct = int(self.sl_throttle.value())
        self.ds.start_motor__throttle(throttle_pct)
        
    def clicked_inchingstart(self):
        deg = self.sl_inching.value()
        self.ds.start_motor__degrees(deg, throttle_pct=int(self.sl_inchingthrottle.value()))
        
    def clicked_inching_5(self):   self.ds.start_motor__degrees(  5, throttle_pct=int(self.sl_inchingthrottle.value()))
    def clicked_inching_10(self):  self.ds.start_motor__degrees( 10, throttle_pct=int(self.sl_inchingthrottle.value()))
    def clicked_inching_120(self): self.ds.start_motor__degrees(120, throttle_pct=int(self.sl_inchingthrottle.value()))
        
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
        print('changed_motorconfig')
        #ds.set_motorconfig(self, motorid)
        #print('Saving screenshot to %d'%(self.cb_motorconfig.currentIndex()))
        self.ds.set_motorconfig( self.cb_motorconfig.currentIndex())
        #self.setMotor(3)  # Hardwired Plettenberg
        #pass

    def setMotor(self, motor_id):
        print('Saving screenshot to %d'%(motor_id))
        '''
        if motor_id == 0:
            redis_conn.publish('downhole','motor-config:parvalux')
        elif motor_id == 1:
            redis_conn.publish('downhole','motor-config:skateboard')
        elif motor_id == 2:
            redis_conn.publish('downhole','motor-config:hacker')
        elif motor_id == 3:
            redis_conn.publish('downhole','motor-config:plettenberg')
        '''
        
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
            #test = index # int(self.sl_throttle.value())
            #print('drill-control: Saving calibration in slot %d'% i)
            self.ds.save_bno055_calibration(i)
        else:
#            print('save ignored...')           
            pass
        
    def clicked_loadcal(self, i):
        #test = index # int(self.sl_throttle.value())
        #print('drill-control: Loading calibration from slot %d'% i)
        self.ds.load_bno055_calibration(i)
        

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
        
    def changed_xaxislen_incl(self, idx):
        self.xlen_selector['incl'] = idx #self.cb_xaxislen_current.currentIndex()
#        self.plot_incl.setXRange(0, self.xlen[self.xlen_selector['incl']]/60*1.01, padding=0)
        
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
        self.plot_speed.setTitle(  self.htmlfont('<b>Speed = %.1f cm/s'%(self.hist_speed[-1]), FS_GRAPH_TITLE))        

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
            self.hist_current   = np.roll(self.hist_current,  -1);   self.hist_current[-1]   = self.ds.motor_current
            sel = self.xlen_selector['current']
            I0 = -int(self.xlen[sel]/(DT*DTFRAC_DRILL))
            x = self.hist_time_drill[I0:len(self.hist_time_drill):self.xlen_samplerate[sel]]
            y = self.hist_current[   I0:len(self.hist_time_drill):self.xlen_samplerate[sel]]
            self.curve_current.setData(x=x,y=y)
            self.plot_current.setTitle(self.htmlfont('<b>Current = %.1f A'%(self.ds.motor_current), FS_GRAPH_TITLE))

            self.hist_depth     = np.roll(self.hist_depth, -1); self.hist_depth[-1] = -np.abs(self.ss.depth)
            self.hist_incl_ahrs = np.roll(self.hist_incl_ahrs, -1); self.hist_incl_ahrs[-1] = self.ds.incl_ahrs
            self.hist_incl_sfus = np.roll(self.hist_incl_sfus, -1); self.hist_incl_sfus[-1] = self.ds.incl_sfus
            sel = self.xlen_selector['incl']
            I0 = -int(self.xlen[sel]/(DT*DTFRAC_DRILL))
            x = self.hist_depth[I0:len(self.hist_depth):self.xlen_samplerate[sel]]
            y0 = self.hist_incl_sfus if self.orimethod=='sfus' else self.hist_incl_ahrs 
            y = y0[I0:len(y0):self.xlen_samplerate[sel]]
#            print(x,y)
            self.incl_scatter.setData(x=y, y=x)
#            self.incl_scatter.setData(x = self.hist_incl_sfus[::dn] if self.orimethod=='sfus' else self.hist_incl_ahrs[::dn], y=self.hist_depth[::dn])
            self.plot_incl.setTitle(self.htmlfont('<b>Incl. = %.1f deg'%(self.ds.incl_sfus), FS_GRAPH_TITLE))

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
                (incl, azim, roll) = [ getattr(self.ds, '%s_%s'%(tt,self.orimethod)) for tt in ['incl','azim','roll']]
                self.updateStateBox('orientation_inclination',  '%.1f,&nbsp; <font color="%s">%.0f</font>,&nbsp; <font color="%s">%.0f</font>'%(incl, COLOR_DIAL1, azim, COLOR_DIAL2, roll), warn__nothres)
                self.updateStateBox('orientation_spin',         "%.2f"%(self.ds.spin),        warn__nothres)
                
                qsys = '<font color="%s">%i</font>'%(COLOR_DARKGREEN if self.ds.quality_sys>=2   else COLOR_DARKRED, self.ds.quality_sys)
                qgyr = '<font color="%s">%i</font>'%(COLOR_DARKGREEN if self.ds.quality_gyro>=2  else COLOR_DARKRED, self.ds.quality_gyro)
                qacc = '<font color="%s">%i</font>'%(COLOR_DARKGREEN if self.ds.quality_accel>=2 else COLOR_DARKRED, self.ds.quality_accel)
                qmag = '<font color="%s">%i</font>'%(COLOR_DARKGREEN if self.ds.quality_magn>=2  else COLOR_DARKRED, self.ds.quality_magn)
                self.updateStateBox('orientation_quality', '%s, %s, %s, %s'%(qsys,qgyr,qacc,qmag), warn__nothres)
                
                offsets = getattr(self.ds, 'offset_%s'%(self.orimethod))
                self.updateStateBox('orientation_offsets', "%.1f, %i, %i"%(offsets[0], offsets[1], offsets[2]),  warn__nothres)

                if self.SHOW_BNO055_DETAILED:
                    str_aclvec    = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.accelerometer_x,self.ds.accelerometer_y,self.ds.accelerometer_z, self.ds.accelerometer_mag)
                    str_magvec    = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.magnetometer_x,self.ds.magnetometer_y,self.ds.magnetometer_z, self.ds.magnetometer_mag)
                    str_linaclvec = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.linearaccel_x,self.ds.linearaccel_y,self.ds.linearaccel_z, self.ds.linearaccel_mag)
                    str_gravvec   = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.gravity_x,self.ds.gravity_y,self.ds.gravity_z, self.ds.gravity_mag)
                    str_spnvec    = '[%.1f, %.1f, %.1f], %.1f'%(self.ds.gyroscope_x,self.ds.gyroscope_y,self.ds.gyroscope_z, self.ds.gyroscope_mag)
                    str_quatvec_sfus = '[%.2f, %.2f, %.2f, %.2f] %.1f'%(self.ds.quat_sfus[0],self.ds.quat_sfus[1],self.ds.quat_sfus[2],self.ds.quat_sfus[3], np.linalg.norm(self.ds.quat_sfus))
                    str_quatvec_ahrs = '[%.2f, %.2f, %.2f, %.2f] %.1f'%(self.ds.quat_ahrs[0],self.ds.quat_ahrs[1],self.ds.quat_ahrs[2],self.ds.quat_ahrs[3], np.linalg.norm(self.ds.quat_ahrs))
                    self.updateStateBox('orientation_acceleration', str_aclvec, warn__nothres)
                    self.updateStateBox('orientation_magnetometer', str_magvec, warn__nothres)
#                    self.updateStateBox('orientation_linearacceleration', str_linaclvec, warn__nothres)
#                    self.updateStateBox('orientation_gravity', str_gravvec, warn__nothres)
                    self.updateStateBox('orientation_gyroscope',    str_spnvec, warn__nothres)
                    self.updateStateBox('orientation_quaternion_sfus',    str_quatvec_sfus, warn__nothres)
                    self.updateStateBox('orientation_quaternion_ahrs',    str_quatvec_ahrs, warn__nothres)
                else:
                    self.dial_azim.setValue(int(azim))
                    self.dial_roll.setValue(int(roll))

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
                self.updateStateBox('motor_throttle',   int(self.ds.motor_throttle), warn__nothres)
                self.updateStateBox('motor_tachometer', round(self.ds.tachometer*TACHO_PRE_REV,2), warn__nothres)
        
        ### Disabled widgets if drill state is dead
        
        if not ALWAYS_SHOW_DRILL_FIELDS:
            self.gb_orientation.setEnabled(self.ds.islive)
            self.gb_pressure.setEnabled(self.ds.islive)
            self.gb_temperature.setEnabled(self.ds.islive)
            self.gb_surface_downholevoltage.setEnabled(self.ds.islive)

        self.gb_motor.setEnabled(self.ds.islive)
        #self.gb_expert.setEnabled(self.ds.islive)
        self.gb_expert.setEnabled(True)

        ### Disabled widgets if winch encoder is dead

#        for f in ['gb_surface_depth','gb_surface_speed']:
#            lbl = getattr(self, f)
#            lbl.setEnabled(self.ss.islive_loadcell)
                        
        ### Disabled widgets if load cell is dead
                        
#        for f in ['gb_surface_load','gb_surface_loadcable','gb_run_peakload']:
#            lbl = getattr(self, f)
#            lbl.setEnabled(self.ss.islive_depthcounter)
            
        
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
        return QtCore.QSize(50,300)
        
    def setValue(self, currentDepth, iceDepth):
        self.curval = currentDepth
#        self.curval = iceDepth - 20 # debug colors
        self.iceval = iceDepth
        self.repaint()

    def paintEvent(self, e):

        painter = QtGui.QPainter(self)
        H, W = painter.device().height(), painter.device().width()
#        H = int(0.6*H) # debug
        tol = 20 # metre
        
        c_ice      = '#969696' 
        c_icehatch = '#252525'
        c_fluid    = 'white' #COLOR_GRAYBG 
        c_drill    = COLOR_DARKGREEN if self.curval < self.iceval - tol else COLOR_DARKRED

        ### backgorund (fluid)
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor(c_fluid))
        brush.setStyle(Qt.SolidPattern)
        rect = QtCore.QRect(0, 0, W, H)
        painter.fillRect(rect, brush)
        
        ### undrilled ice
        ystart_ice = self.maxval
        yend_ice   = int(self.iceval/self.maxval * H) # in px
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
        y_drill = int(self.curval/self.maxval * H) # in px
        brush = QtGui.QBrush()
        brush.setColor(QtGui.QColor(c_drill))
        brush.setStyle(Qt.SolidPattern)
        rect = QtCore.QRect(0, 0, W, y_drill)
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
