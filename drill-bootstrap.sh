#!/bin/bash
echo "*** Drill bootstrap ***";

echo "> Setting STATIC IP address";
sudo dhcpcd -S ip_address=10.2.3.10/16 -S routers=10.2.1.1 -S domain_name_servers=10.2.1.1 eth0
sleep 4;

echo "> Synchronizing clock"
sudo systemctl restart systemd-timesyncd.service
sudo timedatectl set-ntp true &
sudo ntpdate 0.arch.pool.ntp.org
sleep 3

echo -n "> Checking USB stick ... "
sudo mount /dev/sda1 /mnt/logs/ -o umask=000


if [ $? -eq 0 ]
then
   echo "OK"
else
   echo "NOT OK, no logfiles will be taken!"
fi

echo "> Launching drill control GUI";
sleep 1;
#python /home/drill/drill-surface/legacy/drill-surface/drill_surface.py &
python3 /home/drill/surface-unit/drill-control/drill-control.py &

#echo "> Drill position GUI";
#sleep 1;
#python /home/drill/surface-unit/drill-control/drill-position.py run &

echo "> Winch encoder (codex560)"
sleep 1;
#python3 /home/drill/surface-unit/drill-displays/codex560.py /dev/ttyUSB1 &
python3 /home/drill/surface-unit/drill-displays/codex560.py &

echo "> Load cell (pmdstrain)"
sleep 1;
#python3 /home/drill/surface-unit/drill-displays/pmdstrain.py /dev/ttyUSB0 &
python3 /home/drill/surface-unit/drill-displays/pmdstrain.py &

echo "> Launching drill comms (dispatch)";
sleep 1;
python /home/drill/surface-unit/drill-dispatch/dispatch.py --debug --port=/dev/ttyAMA0;

