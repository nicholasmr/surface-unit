#!/usr/bin/python
# N. Rathmann, 2017-2022

import sys, time, code # code.interact(local=locals())
import numpy as np

from settings import *
from state_drill import *
from state_surface import *

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import QtWidgets, QtGui, QtCore

### Run mode

if len(sys.argv) < 2: sys.exit('usage: %s [run|info|debug]'%(sys.argv[0]))

if len(sys.argv)==2: mode = str(sys.argv[1])
else:                mode = 'run';

RUNMODE  = mode=='run'   # View mode
INFOMODE = mode=='info'  # Info-screen mode (slightly reduced infomation)
DEBUG    = mode=='debug' # Debug without redis

NOREDIS          = DEBUG
SET_VALS_TO_WARN = DEBUG

#-----------------------
# Init
#-----------------------

### Time stepping

dt = 0 # time step size
t  = 0 # total time
tn = 0 # time steps

# Update frequency
dt = 0.5
if INFOMODE: dt = 1.0;
dti = 0.1 # dti" is interface update-rate in *seconds* (interpolating depth values between polling), whereas "dt" is REDIS polling rate in *seconds*.

pollrate = int(dt/dti) # poll/update rate in *time steps* of dti; that is, REDIS polling occours every "pollrate" times dti.
dt = pollrate*dti
print('%s: Time stepping: dt=%.2f, dti=%.2f, pollrate=%i'%(sys.argv[0],dt,dti,pollrate));

### Velocity history

if dt==0:  vdrill_hist = np.full(120,1e-10)
else:      vdrill_hist = np.full(50,1e-10)

### State objects 

ds = DrillState(  redis_host=DRILL_HOST if INFOMODE else REDIS_HOST)   
ss = SurfaceState(1.5, dt, redis_host=DRILL_HOST if INFOMODE else REDIS_HOST)

### Globals 

global l,lliq,ldrill, load,hammer,sliprate, motorRPM,motorI,motorU,motorflash, tempmotor,tempelect, incl,azi,  vdrill, ETA, alertloggers

l      = 900     # current bottom 
ldrill = 900+0.5 # drill position
lliq   = 77      # liquid level

load, hammer = 0,0
sliprate  = 0

motorRPM, motorI, motorU = 0,0,0 
tempmotor, tempelect = 0,0
incl, azi = 0,0

vdrill       = 0
ETA          = np.inf
alertloggers = 0

###

ldrillintp = np.zeros(pollrate) + ldrill
ldrillprev = ldrill


#--------------------------
# Fonts
#--------------------------

COLOR_WARN_RGB = [240,59,32]
COLOR_WARN_HEX = '#F03B20'
COLOR_OBS_RGB  = [255,237,160]
COLOR_OBS_HEX  = '#FFEDA0'
COLOR_BLUE_RGB = [158,202,225] 
COLOR_BLUE_HEX = '#9ECAE1'
COLOR_OK_RGB   = [26,152,80]   
COLOR_OK_HEX   = '#1A9850'

FontSize0 = 14
dFont = 4

fontname = 'Helvetica'
font = QFont(fontname); 
#font.setBold(True)
font.setPointSizeF(FontSize0+dFont);

fontb = QFont(fontname); 
fontb.setBold(True)
fontb.setPointSizeF(FontSize0+dFont);

fontsmaller = QFont(fontname); 
fontsmaller.setPointSizeF(FontSize0+dFont-3)

fonttitle = QFont(fontname); 
fonttitle.setBold(True)
fonttitle.setPointSizeF(FontSize0+8); 

#--------------------------
# Functions
#--------------------------

def htmlfont(text,fsize, color='#000000'): return '<font size="%i" color="%s">%s</font>'%(fsize,color,text)

def getMaxGeom():
#        geom_screen = QDesktopWidget().screenGeometry()
        geom_avail  = QDesktopWidget().availableGeometry() # ex [0, 28, 1920, 1028], "28" ypixels reserved for top/bottom window manager bars
#        code.interact(local=locals())
#        geom_xy     = [geom_avail.width()-geom_avail.x(), geom_avail.height()-geom_avail.y()]
        geom_xy     = [geom_avail.width(), geom_avail.height()]
        return geom_xy

#----------------------
# QT functions
#----------------------

### QT pens, brushes, colors, etc.

qstr_deg = "C"

penCase   = QPen(Qt.black, 9, Qt.SolidLine)
penHole   = QPen(Qt.black, 3, Qt.SolidLine)
penThn    = QPen(Qt.black, 3, Qt.SolidLine)

COLOR_WARN     = QColor(COLOR_WARN_RGB[0],COLOR_WARN_RGB[1],COLOR_WARN_RGB[2])
COLOR_BLUE_RGB = QColor(COLOR_BLUE_RGB[0],COLOR_BLUE_RGB[1],COLOR_BLUE_RGB[2])
COLOR_OK       = QColor(COLOR_OK_RGB[0],COLOR_OK_RGB[1],COLOR_OK_RGB[2])

penWarn   = QPen(Qt.white, 12, Qt.SolidLine)
penWarnred= QPen(COLOR_WARN, 12, Qt.SolidLine)
penReg    = QPen(Qt.black,3, Qt.SolidLine)
penThick  = QPen(Qt.black,6, Qt.SolidLine)
penThickCable = QPen(QColor(191,129,45),6, Qt.SolidLine)

penReg.setMiterLimit(100)
penReg.setJoinStyle(Qt.BevelJoin)

brush_liq             = QBrush(QColor(217,217,217),Qt.SolidPattern)
brush_undrilled       = QBrush(QColor(255,255,255),Qt.SolidPattern)
brush_drillbody       = QBrush(QColor(115,115,115),Qt.SolidPattern);
brush_drillbarreldiag = QBrush(QColor(0,0,0),Qt.BDiagPattern);  
brush_alertloggers    = QBrush(QColor(102,189,99),Qt.SolidPattern);

BRUSH_WARN     = QBrush(COLOR_WARN,Qt.SolidPattern);

COLOR_RPM_LVLS = [0.01]
COLOR_RPM      = [[189,189,189],COLOR_OBS_RGB]
BRUSH_RPM      = [QBrush(QColor(c[0],c[1],c[2]),Qt.SolidPattern) for c in COLOR_RPM]

COLOR_HAMMER_LVLS = [warn__hammer[1]/2, warn__hammer[1]]
COLOR_HAMMER      = [[189,189,189], COLOR_OBS_RGB, COLOR_WARN_RGB]
BRUSH_HAMMER      = [QBrush(QColor(c[0],c[1],c[2]),Qt.SolidPattern) for c in COLOR_HAMMER]
BRUSH_HAMMER_PAT  = QBrush(QColor(0,0,0),Qt.HorPattern)

def getColorGivenValue(val, lvls, colors):
    for ii in np.flipud(np.arange(len(lvls))):
        if val > lvls[ii]: return colors[ii+1]
    return colors[0] 

### Dimensions of drill sections

drilllen    = 10.2 + 0.0 # 0.5 is the length of dead weight
cbarrellen  = 3.5 # core barrel length
delta       = (drilllen-cbarrellen)*0.3
hammerlen   = delta
motorseclen = delta

### Borehole dimensions:

L      = 2.7 * 1e3 # hole depth
depths = np.multiply([0,      59,   62,   66,   98, L], 1) # depths with varying widths (due to casing)
f      = 0.7 # artificially reduce width by this factor
widths = np.multiply([2.55*f, 2.22*f, 1.85*f, 1.29, 1.29], 1) # borehole widths for given "depths" (due to casing)

### GUI-scaled drill/borehole length measures

dmul = 63 # depth multiplier
#dmul = 30 # debug
wmul = int(30*3.9) # width multiplier

# drill
mydrilllen    = int(dmul*drilllen)
mycbarrellen  = int(dmul*cbarrellen) # length of drilllen which is the core barrel
myhammerlen   = int(dmul*hammerlen)
mymotorseclen = int(dmul*motorseclen)

# borehole
mywidths      = np.multiply(widths, wmul)
mydepths      = np.multiply([0, 59, 62, 66, 98, L], dmul)
mytowerlen    = int(dmul*80)

### Drawing functions

x0 = 300-180 # newest, smaller-width GUI version

def LRwall(x0,w): return (int(x0-w/2),int(x0+w/2))

def drawBoreHole(qp, OVERVIEW):

        global l,lliq,ldrill, load,hammer,sliprate, motorRPM,motorI,motorU,motorflash, tempmotor,tempelect, incl,azi,  vdrill, ETA, alertloggers
        global vdrill_hist

        flashon = True

        ### Measures        
        mylliq   = int(dmul*lliq)
        myl      = int(dmul*l)
        myldrill = int(dmul*ldrill)

        w        = int(mywidths[-2])
        extend   = int(1.3*drilllen) # extent to which we draw the portion of the QT image not seen (outside window). This should be adjusted according to the zoom-in scale "dmul"
        myextend = int(dmul*extend)
        # x0 = center (vertical) line through drill
        dxdrill = int(w/3)
        dwdrill = 2*dxdrill
        x0l = x0-dxdrill # left side of drill
        x0r = x0+dxdrill # right side of drill

        ### Vertical offsets
        if OVERVIEW: y0 = 80
        else:        y0 = -(myldrill-1.15*mydrilllen)
        Y0 = int(y0) 
        y0drill = Y0+myldrill

        #-------------------
        # The borehole and casing 
        #-------------------

        ### Depth ticks
        
        if OVERVIEW:  del_d = 200 # metres
        else:         del_d = 1
        dx = 20 # pixels
        tickslist = np.arange(np.max([0,np.round(ldrill-extend)]), np.min([L,np.round(ldrill+extend)]), del_d)
        for d in tickslist:
                dref, di =int(dmul*d), 0
                for di in np.arange(len(depths)-2):
                        if (d>=depths[di]) and (d<=depths[di+1]): break
                        else: di=di+1
                        
                wi = int(mywidths[di])
                recty,rectx = 40, 120
                wl,wr = LRwall(x0,wi)
                rect = QRect(wr+dx, Y0+dref-int(recty/2), rectx, recty)
                if np.mod(d,2*del_d)==0: qp.drawText(rect, Qt.AlignLeft, '%1.0fm'%(d))   
                qp.drawLine(wr+dx-6, Y0+dref, wr+6, Y0+dref)

        ### Level labels for l, lliq, delta l, etc.
        
        rectx, recty = 250, 80
        x0lbl = int(wl-dx-rectx*0.95)
        wl,wr = LRwall(x0,w)
        rect_lliq = QRect(x0lbl, int(Y0+mylliq-0.5*recty/2), rectx, recty)
        rect_l    = QRect(x0lbl, int(Y0+myl   -0.5*recty/2), rectx, recty)
        qp.drawLine(wl-6, Y0+myl, wl-dx+6, Y0+myl)
        qp.setBrush(brush_undrilled)      
        qp.drawRect(x0-int(w/2),Y0+myl, w,myextend)      

        ### Draw hole + casing
        
        mydepths[-1] = np.max([mydepths[-2],myldrill+myextend])
        N = len(mywidths)
        for ii in np.arange(N):
                if ii<N-1: qp.setPen(penCase)
                else:      qp.setPen(penHole)
                D, W = int(mydepths[ii+1]-mydepths[ii]), int(mywidths[ii])
                y0 = int(y0+D)
                wl,wr = LRwall(x0,W)
                qp.drawLine(wl, y0-D, wl, y0)    
                qp.drawLine(wr, y0-D, wr, y0) 
                if ii<len(mywidths)-1:
                        Wnext = int(mywidths[ii+1])
                        wlnext,wrnext = LRwall(x0,Wnext)
                        qp.drawLine(wl, y0, wlnext, y0)
                        qp.drawLine(wr, y0, wrnext, y0)

        #-------------------
        # The drill 
        #-------------------

        # -- body
        qp.setPen(penThick); 
        if load>warn__load[1] and flashon and not INFOMODE: qp.setPen(penWarnred); 
        qp.drawLine(x0, Y0-mytowerlen, x0, y0drill-mydrilllen)
        qp.setPen(penReg)

        qp.setBrush(brush_drillbody)
        qp.drawRect(x0l, y0drill, dwdrill, -mydrilllen)
        
        # -- skates
        qp.setBrush(BRUSH_HAMMER[0]) 
        if abs(sliprate)>warn__spin[1] and flashon and not INFOMODE:  qp.setBrush(BRUSH_WARN)
        qp.drawRect(x0l-int(w*0.12), y0drill-mydrilllen, dwdrill+int(2*w*0.12), +myhammerlen)

        # -- hammer
        qp.setBrush(BRUSH_HAMMER[0])
        if (hammer>warn__hammer[1]) and flashon and not INFOMODE: qp.setBrush(getColorGivenValue(hammer, COLOR_HAMMER_LVLS, BRUSH_HAMMER))  
        qp.drawRect(x0l, y0drill-mydrilllen, dwdrill, +myhammerlen)

        # -- motor section
        qp.setBrush(BRUSH_HAMMER[0])
        if (tempmotor>warn__temperature_motor[1] or tempelect>warn__temperature_electronics[1]) and flashon and not INFOMODE:  qp.setBrush(BRUSH_WARN)
        qp.drawRect(x0l, y0drill-mydrilllen+myhammerlen, dwdrill, +myhammerlen)

        qp.setBrush(BRUSH_RPM[0])
        if (motorRPM>0) and flashon: qp.setBrush(getColorGivenValue(motorRPM, COLOR_RPM_LVLS, BRUSH_RPM))

        if motorI>warn__motor_current[1] and flashon and not INFOMODE: qp.setBrush(BRUSH_WARN) # Override "on" blink if warning (red)
        if motorRPM==0 and alertloggers: qp.setBrush(brush_alertloggers)
        qp.drawRect(x0l, y0drill,  dwdrill, -mycbarrellen)
        qp.setBrush(brush_drillbarreldiag)
        qp.drawRect(x0l, y0drill,  dwdrill, -mycbarrellen)

        #----------------
        # Labels
        #----------------

        dx, dy = int(0.1*dxdrill), 40; # x padding of text box, height of text box
        x0txt = x0l+dx

        if SET_VALS_TO_WARN: ETA=-100
        isETA = (ETA is not np.inf) and abs(ETA)<60*10
        if isETA: 
                isOnWayDown = ETA<0
                if isOnWayDown: ETA = abs(ETA)
#                if isOnWayDown and INFOMODE: ETA = np.inf
                eta = ETA
                qp.setFont(fontb);
                y0ETA = y0drill+mycbarrellen*0.15
                w_ = int(dxdrill*2.4)
                xETA, yETA = int(x0txt-3*dx), int(y0drill+mycbarrellen*0.4);
                c = COLOR_BLUE_RGB
                qp.setBrush(c); qp.drawRect(QRect(xETA, yETA, w_,int(dy*1.8)))
                dw_ = int(0.04*w_)
                r = QRect(xETA+dw_, yETA,    w_,dy*2);  qp.drawText(r, Qt.AlignLeft, 'ETA\n%i min'%(eta))   
                qp.setFont(font);

        # velocity
        x0vel, y0vel = x0l, int(y0drill+mycbarrellen*0.05)
        if abs(vdrill)>warn__velocity[1] and flashon and not INFOMODE: qp.setPen(penWarnred); qp.setFont(fontb);
        else:                                                       qp.setPen(penReg); qp.setFont(fontb);
        v = '%.0f'%(vdrill)
        if abs(vdrill)<3.0: v = '%.1f'%(vdrill)
        r = QRect(x0-int(w/2*0.8),y0vel, w,dy); qp.drawText(r, Qt.AlignLeft, '%s cm/s'%(v))   
        qp.setFont(font); 

        # delta L (use same y ref as vel above)
        if ldrill>l:
                qp.setPen(penReg); qp.setFont(fontb); 
                r = QRect(x0-int(w/2*0.8),y0vel+int(dy*0.7), w,dy); qp.drawText(r, Qt.AlignLeft, 'L=%.2fm'%((ldrill-l)))   
                qp.setFont(font); 

        # orientation
        qp.setPen(penReg); 
        qp.setFont(fontb);
        qstr_theta, qstr_phi = "\u03B8", "\u03C6"
        if incl>-10 and not INFOMODE: # debug, don't show if get() function not implemented
                r = QRect(x0txt-dx, y0drill-int(mydrilllen/1.8), dwdrill,dy*3); 
                qp.drawText(r, Qt.AlignCenter, "Incl.\n%.1f\ndeg."%(incl))   

        ### If driller's mode --> how all info/labels
        
        if not INFOMODE:

                # cabel load
                ymidload = int(y0drill-mydrilllen*1.12)
                if load>warn__load[1] and flashon: qp.setPen(penWarnred); qp.setFont(fontb);
                else:                          qp.setPen(penReg); qp.setFont(fontb);
                r = QRect(x0-int(w/2*1.08), ymidload,             int(w/2),dy);  qp.drawText(r, Qt.AlignRight, '%.0f'%(load))   
                r = QRect(x0-int(w/2*1.08), ymidload+int(dy*0.6), int(w/2),dy);  qp.drawText(r, Qt.AlignRight, 'kg')   
                qp.setFont(font)

                # hammer
                ymidhammer = int(y0drill-mydrilllen - 0.02*myhammerlen)
                hammerflash = hammer>warn__hammer[1]/2 and flashon
                if hammerflash: 
                        if hammer>warn__hammer[1]: qp.setPen(penWarn); 
                        else:                  qp.setPen(penReg);  
                        qp.setFont(fontb);
                        r = QRect(x0txt-int(dx/2), ymidhammer,             dwdrill,dy); qp.drawText(r, Qt.AlignCenter, 'Ham.')        
                        r = QRect(x0txt-int(dx/2), ymidhammer+int(dy*0.6), dwdrill,dy); qp.drawText(r, Qt.AlignCenter, '%i%%'%(hammer))        
                qp.setFont(font)

                # skates
                ymidskates = int(y0drill-mydrilllen + 0.45*myhammerlen)
                if abs(sliprate)>warn__spin[1] and flashon:
                        if hammerflash: qp.setPen(penWarn); 
                        else:           qp.setPen(penWarnred); 
                        qp.setFont(fontb);
                        r = QRect(x0txt-dx, ymidskates, dwdrill,dy); qp.drawText(r, Qt.AlignCenter, 'Slip')      
                        r = QRect(x0txt-dx, ymidskates+int(0.65*dy), dwdrill,dy); qp.drawText(r, Qt.AlignCenter, '%iRPM'%(sliprate))      
                qp.setFont(font)

                # motor section
                if motorRPM > COLOR_RPM_LVLS[0]:
                        ymidmotorsec = int(y0drill-mydrilllen+myhammerlen + mymotorseclen/2)
                        dy_ = int(0.8*dy)

                        qp.setPen(penReg); qp.setFont(fontb);
                        if tempelect>warn__temperature_electronics[1] and flashon: qp.setPen(penWarn); qp.setFont(fontb); 
                        if tempelect is not np.nan:
                                r = QRect(x0txt-dx, ymidmotorsec-1*dy_, dwdrill,dy_*2); qp.drawText(r, Qt.AlignCenter, "Electr.\n%i%s"%(tempelect,qstr_deg))   
                        qp.setFont(font)

                # barrel/motor
                if motorRPM > COLOR_RPM_LVLS[0]:
                        ymidbarrel = int(y0drill-mycbarrellen/2)
                        dy_ = int(0.8*dy)

                        qp.setPen(penReg); qp.setFont(fontb);
                        r = QRect(x0txt, ymidbarrel-2*dy_, dwdrill,dy_); qp.drawText(r, Qt.AlignLeft, '%.0fRPM'%(motorRPM))   

                        qp.setPen(penReg); qp.setFont(fontb);
                        if motorI>warn__motor_current[1] and flashon: qp.setPen(penWarn); qp.setFont(fontb); 
                        r = QRect(x0txt, ymidbarrel-1*dy_, dwdrill,dy_); qp.drawText(r, Qt.AlignLeft, '%.1fA'%(motorI))   
                        qp.setFont(font)

                        qp.setPen(penReg); qp.setFont(fontb);
                        r = QRect(x0txt, ymidbarrel-0*dy_, dwdrill,dy_); qp.drawText(r, Qt.AlignLeft, '%.0fV'%(motorU)) 

                        qp.setPen(penReg); qp.setFont(fontb);
                        if tempmotor>warn__temperature_motor[1] and flashon: qp.setPen(penWarn); qp.setFont(fontb); 
                        r = QRect(x0txt, ymidbarrel+1*dy_, dwdrill,dy_); qp.drawText(r, Qt.AlignLeft, '%i%s'%(tempmotor,qstr_deg))   


class drillLocation(QWidget):

        def __init__(self, parent = None):
                QWidget.__init__(self, parent)

        def paintEvent(self, event):
                qp = QPainter()
                qp.begin(self)
                qp.setFont(font)        
                drawBoreHole(qp,0)
                self.qp = qp
                qp.end()

        def sizeHint(self): return QSize(400, 1200)

#----------------------
#----------------------
#----------------------

def eventListener():

        global t,tn
        global r, l,lliq,ldrill,ldrillprev,ldrillintp,load,hammer,sliprate,motorRPM,motorI,motorU,motorflash, tempmotor,tempelect, incl,azi, vdrill_hist,vdrill,ETA, alertloggers

        substep = tn % pollrate;
        if substep==0 and (not DEBUG):
        
            ldrillprev = ldrill

            # Pull from redis 
            ss.update()
            ldrill, velinst, l, load = ss.depth, ss.speed, ss.depthtare, ss.load
            alertloggers = ss.alertloggers
            
            ds.update()
            motorRPM, motorI, motorU = ds.motor_rpm, ds.motor_current, ds.motor_voltage
            tempelect, tempmotor     = ds.temperature_electronics, ds.temperature_motor
            hammer, sliprate         = ds.hammer, ds.spin
            incl, azi                = ds.inclination, ds.azimuth
            ##
            vdrill_inst = velinst #* 1e2
#            vdrill_hist = np.hstack([vdrill_hist[1::],vdrill_inst]) 
#            vdrill      = np.nanmean(vdrill_hist)
            vdrill = vdrill_inst
            # /end

            dl = (ldrill-ldrillprev)/(pollrate)
            ldrillintp = [ldrillprev+(ii+1)*dl for ii in range(pollrate)]
            
        if (not INFOMODE) and (not DEBUG): ldrill = ss.depth
        else:                              ldrill = ldrillintp[substep]
	
        if   vdrill<-10 and ldrill<(l-30): ETA =      (ldrill/(-vdrill*1e-2)) /60 
        elif vdrill>+10 and ldrill>(30):   ETA = -((l-ldrill)/(-vdrill*1e-2)) /60
        else:                              ETA = np.inf  

        # Debug state
        if SET_VALS_TO_WARN:
                f = 1.01
                hammer    = f*warn__hammer[1]
                sliprate  = f*warn__spin[1]
                motorRPM  = f*1
                motorI    = f*warn__motor_current[1]
                tempmotor = f*warn__temperature_motor[1]
                tempelect = f*warn__temperature_electronics[1]
                load      = f*warn__load[1]
                vdrill    = f*warn__velocity[1]*100

        motoron = (motorRPM > 1.0) 

        # Update
        progress.repaint()        
        t  = t + dti
        tn = tn + 1
       
#----------------------
# QT main
#----------------------

app = QApplication([])
w = QWidget() ## Define a top-level widget to hold everything
geom_xy = getMaxGeom()
f = 1./6
w.resize(int(geom_xy[0]*f), int(geom_xy[1]*0.97))
w.move(int(geom_xy[0]*(1-f)),0)
w.setWindowTitle('Drill position')

#----------------------
# Add widgets to the layout in their proper positions
#----------------------

layout = QGridLayout()
layout.setSpacing(10)
w.setLayout(layout)
progress = drillLocation()
layout.addWidget(progress, 0, 0, 4, 1)  # plot goes on right side, spanning 3 rows

if not INFOMODE:
    button = QPushButton('Alert loggers',w)
    button.setCheckable(True)
    button.clicked.connect(lambda: ss.toggle_alertloggers())
    button.resize(120,30)
    button.move(int(geom_xy[0]*f/2*1.1),20)

w.show()

# Run (main) window "updater" ever dti seconds (not dt, which is the polling rate!)
timer1 = QTimer()
timer1.timeout.connect(eventListener)
timer1.start(int(dti*1000)) 
app.exec_() # Start the Qt event loop

