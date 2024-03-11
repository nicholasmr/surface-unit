#!/bin/bash
# N. M. Rathmann <rathmann@nbi.ku.dk>, 2019-2024

### Settings

VPATH_LATEST=/home/drill/surface-unit
VPATH_2022=/home/drill/surface-unit/old-versions/2022

DEV_PMDSTRAIN=/dev/ttyUSB0
DEV_CODIX=/dev/ttyUSB1

STATIC_IP=10.2.3.10

INFO='\033[1;32m'
ERROR='\033[1;31m'
NC='\033[0m' # No Color

HEIGHT=15
WIDTH=60
CHOICE_HEIGHT=4
BACKTITLE="SURFACE UNIT BOOTSTRAP"
MENU="Choose one of the following options:"

### Menu 1

OPTIONS=(1 "2024 version"
         2 "2024 version, NOT deployed to field"
         3 "2022 version (without drill BNO055 update)"
         4 "2016-2019 legacy (N/A)"
         )

CHOICE=$(dialog --clear --nocancel --backtitle "$BACKTITLE" --title "Drill GUI version" --menu "$MENU" $HEIGHT $WIDTH $CHOICE_HEIGHT "${OPTIONS[@]}" 2>&1 >/dev/tty)
clear

ISDRILLHOST=1 # assume this is drill host by default

case $CHOICE in
        1)  VPATH=$VPATH_LATEST; export GUI_SCRIPT=$VPATH/drill-control/drill-control.py ;;
        2)  VPATH=$VPATH_LATEST; export GUI_SCRIPT=$VPATH/drill-control/drill-control.py; ISDRILLHOST=0 ;;
        3)  VPATH=$VPATH_2022;   export GUI_SCRIPT=$VPATH/drill-control/drill-control.py ;;
        4)  VPATH=$VPATH_2022;   export GUI_SCRIPT=$VPATH/legacy/drill-surface/drill_surface.py ;;
esac

### Menu 2

OPTIONS=(1 "CRLF for PMD-strain, CRLF for CODIX560"
         2 "CRLF for PMD-strain, Modbus for CODIX560"
         )

CHOICE=$(dialog --clear --nocancel --backtitle "$BACKTITLE" --title "Communication protocols for depth and load displays" --menu "$MENU" $HEIGHT $WIDTH $CHOICE_HEIGHT "${OPTIONS[@]}" 2>&1 >/dev/tty)
clear
case $CHOICE in
        1) PMDSTRAIN_CRLF=1; CODIX_CRLF=1 ;;
        2) PMDSTRAIN_CRLF=1; CODIX_CRLF=0 ;;
esac


####################################


if  [ $ISDRILLHOST = 1 ]
then
    echo -e "${INFO}>>> Setting static IP address $STATIC_IP ${NC}";
    sudo dhcpcd -S ip_address=$STATIC_IP/16 -S routers=10.2.1.1 -S domain_name_servers=10.2.1.1 eth0
    sleep 2;

    echo -e "${INFO}>>> Synchronizing clock${NC}"
    sudo systemctl restart systemd-timesyncd.service
    sudo timedatectl set-ntp true &
    sudo ntpdate 0.arch.pool.ntp.org
    sleep 2

    echo -n -e "${INFO}>>> Checking USB stick ... ${NC}"
    sudo mount /dev/sda1 /mnt/logs/ -o umask=000

    if [ $? -eq 0 ]
    then
        echo -e "${INFO}OK${NC}"
    else
        echo -e "${ERROR} Not found! No log files will be recorded ${NC}"
    fi
else
    echo -e "${ERROR}>>> Non-deployed state for debugging: IP address sought by DHCP and USB pen not mounted for logging${NC}"
    sudo dhcpcd eth0
fi


####################################


echo -e "${INFO}>>> Launching drill control GUI ${GUI_SCRIPT} ${NC}";
python3 ${GUI_SCRIPT} &


sleep 1;
echo -e "${INFO}>>> Load cell (pmdstrain, CRLF=$PMDSTRAIN_CRLF) ${NC}"
if  [ $PMDSTRAIN_CRLF = 1 ]
then
    python3 $VPATH_LATEST/surface-displays/pmdstraincrlf.py $DEV_PMDSTRAIN & 
else
    python2 $VPATH_LATEST/surface-displays/pmdstrain.py $DEV_PMDSTRAIN &
fi


sleep 1;
echo -e "${INFO}>>> Winch encoder (codix560, CRLF=$CODIX_CRLF) ${NC}"
if  [ $CODIX_CRLF = 1 ]
then
    python3 $VPATH_LATEST/surface-displays/codix560crlf.py $DEV_CODIX & 
else
    python2 $VPATH_LATEST/surface-displays/codix560.py $DEV_CODIX &
fi


echo -e "${INFO}>>> Launching drill communications (dispatch) ${NC}";
python3 $VPATH/drill-dispatch/dispatch.py --debug --port=/dev/ttyAMA0;


### Added by Rikke
#sudo idle& /home/drill/surface-unit/drill-control/drill-control.py
#sudo idle& /home/drill/surface-unit/drill-dispatch/packets.py

