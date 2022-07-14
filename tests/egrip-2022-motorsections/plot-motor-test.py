import numpy as np
import matplotlib.pyplot as plt

def loadfile(fname):

    with open(fname) as f:
        lines = f.readlines()[1:]
        time       = [float(line.split(',')[0]) for line in lines]
        temp_gear  = [float(line.split(',')[1]) for line in lines]
        temp_motor = [float(line.split(',')[2]) for line in lines]
        current    = [float(line.split(',')[3]) for line in lines]
        rpm        = [float(line.split(',')[4]) for line in lines]
        
    return (time, temp_gear, temp_motor, current, rpm)
    

time1, temp_gear1, temp_motor1, current1, rpm1 = loadfile('log1')
time2, temp_gear2, temp_motor2, current2, rpm2 = loadfile('log2')
time3, temp_gear3, temp_motor3, current3, rpm3 = loadfile('log3')

print(time2,time3)

scale=1.5
fig = plt.figure(figsize=(5*scale,7*scale))
ax1 = fig.add_subplot(411)
ax2 = fig.add_subplot(412)
ax3 = fig.add_subplot(413)
ax4 = fig.add_subplot(414)

ax1.plot(time1, temp_gear1, c='tab:green', ls='-',  label='Tube 1')
ax1.plot(time2, temp_gear2, c='tab:red',   ls='-',  label='Tube 2')
ax1.plot(time3, temp_gear3, c='tab:blue',  ls='--', label='Tube 3')
ax1.set_xlabel('time (min.)'); ax1.set_ylabel('Temp. gear (deg. C)'); leg1 = ax1.legend(); ax1.grid()

ax2.plot(time1, temp_motor1, c='tab:green', ls='-',  label='Tube 1')
ax2.plot(time2, temp_motor2, c='tab:red',   ls='-',  label='Tube 2')
ax2.plot(time3, temp_motor3, c='tab:blue',  ls='--', label='Tube 3')
ax2.set_xlabel('time (min.)'); ax2.set_ylabel('Temp. motor (deg. C)');  leg2 = ax2.legend(); ax2.grid()

ax3.plot(time1, current1, c='tab:green', ls='-',  label='Tube 1')
ax3.plot(time2, current2, c='tab:red',   ls='-',  label='Tube 2')
ax3.plot(time3, current3, c='tab:blue',  ls='--', label='Tube 3')
ax3.set_xlabel('time (min.)'); ax3.set_ylabel('Current (A)');  leg3 = ax3.legend(); ax3.grid()

ax4.plot(time1, rpm1, c='tab:green', ls='-',  label='Tube 1')
ax4.plot(time2, rpm2, c='tab:red',   ls='-',  label='Tube 2')
ax4.plot(time3, rpm3, c='tab:blue',  ls='--', label='Tube 3')
ax4.set_xlabel('time (min.)'); ax4.set_ylabel('Speed (RPM)');  leg4 = ax4.legend(); ax4.grid()

ax1.set_title('Bench test of EGRIP motor sections (no load) at 100% throttle, 2022')

fig.tight_layout()
plt.savefig('motor-test-timeseries.png',dpi=200)

####


scale=1.05
fig = plt.figure(figsize=(6*scale,5*scale))
ax1 = fig.add_subplot(111)

ax1.plot(temp_gear1, current1, c='tab:green', ls='-',  label='Tube 1')
ax1.plot(temp_gear2, current2, c='tab:red',   ls='-',  label='Tube 2')
ax1.plot(temp_gear3, current3, c='tab:blue',  ls='--', label='Tube 3')
ax1.set_ylabel('Idle current (A)'); ax1.set_xlabel('Gear temperature (deg. C)'); leg1 = ax1.legend(); ax1.grid()

ax1.set_title('Bench test of EGRIP motor sections (no load) at 100% throttle, 2022')

fig.tight_layout()
plt.savefig('motor-test.png',dpi=200)

