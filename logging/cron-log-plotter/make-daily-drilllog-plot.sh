# Nicholas R., 2022-2023

# Get drill log of today and plot the history

### Vars
WORKDIR="/home/drill"
DRILL_HOST="10.2.3.10"
# check if command line argument is empty or not present
if [ -z $1 ]; then
        LOGFILEREMOTE="drill.log"
        LOGFILE="drill.log.`date '+%Y-%m-%d'`"
else
        LOGFILEREMOTE=$1
        LOGFILE=$1
fi

### Get the log file
echo "scp drill@$DRILL_HOST:/mnt/logs/$LOGFILEREMOTE $WORKDIR/$LOGFILE"
sshpass -p 'raspberry' scp drill@$DRILL_HOST:/mnt/logs/$LOGFILEREMOTE $WORKDIR/$LOGFILE

### Plot time series
python3 $WORKDIR/surface-unit/logging/plot-drill-log.py         $WORKDIR/$LOGFILE 8 24 $WORKDIR
python3 $WORKDIR/surface-unit/logging/plot-drill-orientation.py $WORKDIR/$LOGFILE      $WORKDIR

### Move plots to public drive by saving on drill computer usb pen (from which drill computer crontab syncs with public drive)
sshpass -p "raspberry" scp $WORKDIR/*.png                  drill@$DRILL_HOST:/mnt/logs/plots/
sshpass -p "raspberry" scp $WORKDIR/drill-logs-processed/* drill@$DRILL_HOST:/mnt/logs/drill-logs-processed/

### Clean up
rm $WORKDIR/$LOGFILE
rm $WORKDIR/drill-logs-processed/*
rm *.png

