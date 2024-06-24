@ECHO OFF 

set COM_DEPTH=COM15
set  COM_LOAD=COM3
set COM_MODEM=COM8

echo.
echo =====================================
echo Bootstrapping intermediate drill box
echo =====================================

echo.
echo ---------------
echo COM ports used:
echo ---------------
echo %COM_DEPTH% for depth display (codix560)
echo %COM_LOAD%  for load display (cub5)
echo %COM_LOAD%  for load display (cub5)
echo ---------------
echo If needed, these can be adjust them in ~trio/surface-unit/drill-bootstrap-win.bat
echo ---------------
echo.

cd c:\Users\trio\surface-unit 

echo *** Launching codix560.py (depth display comms) ***
START B/ python surface-displays/codix560crlf.py %COM_DEPTH%

echo *** Launching dispatch.py (modem comms) ***
python drill-dispatch/dispatch.py --debug --port=%COM_MODEM%

echo *** Launching GUI drill-control.py [0m
python drill-control/drill-control.py

echo.
echo ============================
echo FINISHED
echo ============================
echo.

PAUSE
