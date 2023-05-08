#!/bin/bash
# N. Rathmann, 2019-2023

### Settings

ISDRILLHOST=1 # assume this is drill host by default

RED='\033[1;31m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
NC='\033[0m' # No Color

HEIGHT=15
WIDTH=60
CHOICE_HEIGHT=4
BACKTITLE="SURFACE UNIT BOOTSTRAP"
MENU="Choose one of the following options:"

### MENU 1

OPTIONS=(1 "2023 version (default)"
         2 "2022 version, for drills without BNO055 update"
         3 "2023 version, non-drill computer (debug)"
         4 "2016-2019 legacy (unsupported)"
         )

CHOICE=$(dialog --clear --backtitle "$BACKTITLE" --title "Drill GUI version" --menu "$MENU" $HEIGHT $WIDTH $CHOICE_HEIGHT "${OPTIONS[@]}" 2>&1 >/dev/tty)
clear
case $CHOICE in
        1)  export VERSIONPATH=/home/drill/surface-unit/drill-control/drill-control.py ;;
        2)  export VERSIONPATH=/home/drill/surface-unit/old-versions/2022/drill-control/drill-control.pyc;;
        3)  export VERSIONPATH=/home/drill/surface-unit/drill-control/drill-control.py; ISDRILLHOST=0 ;;
        4)  export VERSIONPATH=/home/drill/drill-surface/legacy/drill-surface/drill_surface.py ;;
esac

### MENU 2

OPTIONS=(1 "CRLF for pmdstrain, MODBUS for codix560 (default)"
         2 "CRLF for pmdstrain, CRLF for codix560"
         )

CHOICE=$(dialog --clear --backtitle "$BACKTITLE" --title "Surface instrument communication protocols" --menu "$MENU" $HEIGHT $WIDTH $CHOICE_HEIGHT "${OPTIONS[@]}" 2>&1 >/dev/tty)
clear
case $CHOICE in
        1)  PMDSTRAIN_CRLF=1; CODIX_CRLF=0 ;;
        2)  PMDSTRAIN_CRLF=1; CODIX_CRLF=1 ;;
esac

### Run bootstrap

#echo -e "${BLUE}>>> Running drill bootstrap (2023)${NC}";

# If not deployed, then allow for IP address on local network (DHCP)
if  [ $ISDRILLHOST = 1 ]
then
    echo -e "${BLUE}>>> Setting static IP address = 10.2.3.10 ${NC}";
    sudo dhcpcd -S ip_address=10.2.3.10/16 -S routers=10.2.1.1 -S domain_name_servers=10.2.1.1 eth0
    sleep 2;

    echo -e "${BLUE}>>> Synchronizing clock${NC}"
    sudo systemctl restart systemd-timesyncd.service
    sudo timedatectl set-ntp true &
    sudo ntpdate 0.arch.pool.ntp.org
    sleep 2

    echo -n -e "${BLUE}>>> Checking USB stick ... ${NC}"
    sudo mount /dev/sda1 /mnt/logs/ -o umask=000

    if [ $? -eq 0 ]
    then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED} NOT FOUND! No log files will be recorded ${NC}"
    fi
else
    echo -e "${RED}>>> NON-DEPLOYED state for debugging => IP not set and USB pen not mounted for logging${NC}"
fi


echo -e "${BLUE}>>> Launching drill control GUI ${VERSIONPATH} ${NC}";
sleep 1;
python3 ${VERSIONPATH} &

echo -e "${BLUE}>>> Load cell (pmdstrain, CRLF=$PMDSTRAIN_CRLF) ${NC}"
sleep 1;
if  [ $PMDSTRAIN_CRLF = 1 ]
then
    python3 /home/drill/surface-unit/drill-displays/CRLF_protocol_version/pmdstraincrlf.py /dev/ttyUSB0 & 
else
    python2 /home/drill/surface-unit/drill-displays-py2/pmdstrain.py /dev/ttyUSB0 &
    #python3 /home/drill/surface-unit/drill-displays/pmdstrain.py /dev/ttyUSB0 &
fi


echo -e "${BLUE}>>> Winch encoder (codix560, CRLF=$CODIX_CRLF) ${NC}"
sleep 1;
if  [ $CODIX_CRLF = 1 ]
then
    python3 /home/drill/surface-unit/drill-displays/CRLF_protocol_version/codex560crlf.py /dev/ttyUSB1 & 
else
    python2 /home/drill/surface-unit/drill-displays-py2/codex560.py /dev/ttyUSB1 &
    #python3 /home/drill/surface-unit/drill-displays/codex560.py /dev/ttyUSB1 & 
fi

echo -e "${BLUE}>>> Launching drill comms (dispatch)${NC}";
sleep 1.5;
python /home/drill/surface-unit/drill-dispatch/dispatch.py --debug --port=/dev/ttyAMA0;

# Added by Rikke for 2023 changes
sudo idle& /home/drill/surface-unit/drill-control/drill-control.py
sudo idle& /home/drill/surface-unit/drill-dispatch/packets.py

