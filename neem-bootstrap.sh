#!/bin/bash
echo ":: NEEM relay bootstrap";

echo "> Winch encoder"
sleep 1;
python2 /home/drill/drill-displays/codex560.py /dev/ttyUSB1 &

echo "> Load cell"
sleep 1;
python2 /home/drill/drill-displays/pmdstrain.py /dev/ttyUSB0 &

echo "> Launching NEEM relay";
sleep 1;
python /home/drill/neemrelay/neemrelay.py;
