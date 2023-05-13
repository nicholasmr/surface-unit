#!/bin/bash
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2023

VPATH_LATEST=/home/drill-aux/surface-unit
STATIC_IP=10.2.3.15

INFO='\033[1;32m'
ERROR='\033[1;31m'
NC='\033[0m' # No Color

#echo -e "${INFO}>>> Setting static IP address $STATIC_IP ${NC}";
#sudo dhcpcd -S ip_address=$STATIC_IP/16 -S routers=10.2.1.1 -S domain_name_servers=10.2.1.1 eth0
#sleep 1;

#echo -e "${INFO}>>> Synchronizing clock${NC}"
#sudo systemctl restart systemd-timesyncd.service
#sudo timedatectl set-ntp true &
#sudo ntpdate 0.arch.pool.ntp.org
#sleep 2

echo -e "${INFO}>>> Launching drill aux GUI ${NC}";
python3 $VPATH_LATEST/drill-control/drill-orientation.py &

