#!/bin/bash
echo "*** Drill bootstrap ***";

echo "*** Setting IP-address ***";
sudo dhcpcd -S ip_address=10.2.3.10/16 -S routers=10.2.1.1 -S domain_name_servers=10.2.1.1 eth0
sleep 6;

echo "> Synchronizing clock"
sudo timedatectl set-ntp true &

echo -n "> Checking USB stick ... "
sudo mount /dev/sda1 /mnt/logs/ -o umask=000


if [ $? -eq 0 ]
then
   echo "OK"

   echo "> Notes"
   sleep 1;
   gedit /mnt/logs/notes.txt &
else
   echo "NOT OK, no logfiles will be taken!"
fi

echo "> Launching GUI";
sleep 1;
#python /home/drill/drill-surface/legacy/drill_surface.py &
python3 /home/drill/surface-unit/drill-control.py &

#echo "> Drill position GUI";
#sleep 1;
#python /home/drill/surface-unit/drill-position.py run &

echo "> Winch encoder"
sleep 1;
python2 /home/drill/drill-displays/codex560.py /dev/ttyUSB1 &

echo "> Load cell"
sleep 1;
python2 /home/drill/drill-displays/pmdstrain.py /dev/ttyUSB0 &

echo "> Launching The Matrix";
sleep 1;
python /home/drill/drill-dispatch/dispatch.py --debug --port=/dev/ttyAMA0;

