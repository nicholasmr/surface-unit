import os, glob

for f in glob.glob('drill-logs/drill.log.2022*'):
    os.system('python3 plot-drill-log.py         %s 6 24 ./plots-2022'%(f))
    os.system('python3 plot-drill-orientation.py %s      ./plots-2022'%(f))
