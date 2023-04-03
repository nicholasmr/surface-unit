#!/bin/bash

export VERSIONPATH=/home/drill/surface-unit/old-versions/2022

echo "*** Drill bootstrap (version $VERSIONPATH) ***";

#if true 
if false 
then
    echo ">>> Setting STATIC IP address";
    sudo dhcpcd -S ip_address=10.2.3.10/16 -S routers=10.2.1.1 -S domain_name_servers=10.2.1.1 eth0
    sleep 2;

    echo ">>> Synchronizing clock"
    sudo systemctl restart systemd-timesyncd.service
    sudo timedatectl set-ntp true &
    sudo ntpdate 0.arch.pool.ntp.org
    sleep 2

    echo -n ">>> Checking USB stick ... "
    sudo mount /dev/sda1 /mnt/logs/ -o umask=000

    if [ $? -eq 0 ]
    then
       echo "OK"
    else
       echo "NOT OK, no logfiles will be taken!"
    fi
else
    echo ">>> ASSUMING NON-DEPLOYED STATE FOR DEBUGGING => NOT SETTING IP-ADDRESS OR MOUNTING USB STICK FOR LOG FILES."
fi

echo ">>> Launching drill control GUI";
sleep 1;
#python /home/drill/drill-surface/legacy/drill-surface/drill_surface.py &
python3 ${VERSIONPATH}/drill-control/drill-control.py &

echo ">>> Load cell (pmdstrain)"
sleep 1;
python3 /home/drill/surface-unit/drill-displays/CRLF_protocol_version/pmdstraincrlf.py /dev/ttyUSB0 &
#python2 /home/drill/surface-unit/drill-displays-py2/pmdstrain.py /dev/ttyUSB0 &
#python3 /home/drill/surface-unit/drill-displays/pmdstrain.py /dev/ttyUSB0 &

echo ">>> Winch encoder (codex560)"
sleep 2;
python2 /home/drill/surface-unit/drill-displays-py2/codex560.py /dev/ttyUSB1 &
#python3 /home/drill/surface-unit/drill-displays/codex560.py /dev/ttyUSB1 &

echo ">>> Launching drill comms (dispatch)";
sleep 1.5;
python ${VERSIONPATH}/drill-dispatch/dispatch.py --debug --port=/dev/ttyAMA0;
