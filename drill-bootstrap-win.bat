@ECHO OFF 

set COM_DEPTH = COM7
set COM_LOAD  = COM8
set COM_MODEM = COM4

ECHO =====================================
ECHO Bootstrapping intermediate drill box
ECHO =====================================

echo ^<ESC^>[93m [93m
echo ---------------
echo COM ports used:
echo ---------------
echo %COM_DEPTH% for depth display (codix560)
echo %COM_LOAD%  for load display (cub5)
echo %COM_LOAD%  for load display (cub5)
echo ---------------
echo If needed, these can be adjust them in ~trio/surface-unit/drill-bootstrap-win.bat
echo ---------------[0m

cd c:\Users\trio\surface-unit 

ECHO [101;93m Launching codix560.py (depth display comms) [0m
python surface-displays/codix560crlf.py %COM_DEPTH%

ECHO [101;93m Launching dispatch.py (modem comms) [0m
python drill-dispatch/dispatch.py --debug --port=%COM_MODEM%

ECHO [101;93m Launching GUI drill-control.py [0m
python drill-control/drill-control.py

ECHO ============================
ECHO FINISHED
ECHO ============================

PAUSE
