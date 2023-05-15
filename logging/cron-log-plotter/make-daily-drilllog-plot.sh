# Nicholas R., 2022

# Get drill log of today and plot the history

### Vars
WORKDIR="/home/drill"
PLTSCRIPT="$WORKDIR/surface-unit/logging/plot-drill-log.py"
LOGFILEREMOTE="drill.log"
LOGFILE="drill.log.`date '+%Y-%m-%d'`"
DRILL_HOST="10.2.3.10"

### Get the log file
echo "scp drill@$DRILL_HOST:/mnt/logs/$LOGFILEREMOTE $WORKDIR/$LOGFILE"
sshpass -p 'raspberry' scp drill@$DRILL_HOST:/mnt/logs/$LOGFILEREMOTE $WORKDIR/$LOGFILE

### Plot time series
python3 $PLTSCRIPT $WORKDIR/$LOGFILE  8 13 $WORKDIR
python3 $PLTSCRIPT $WORKDIR/$LOGFILE 13 19 $WORKDIR
python3 $PLTSCRIPT $WORKDIR/$LOGFILE 19 24 $WORKDIR
python3 $PLTSCRIPT $WORKDIR/$LOGFILE  8 24 $WORKDIR

python3 $WORKDIR/surface-unit/logging/plot-drill-orientation.py $WORKDIR/$LOGFILE  $WORKDIR

### Move plots to public drive
sshpass -p "raspberry" scp $WORKDIR/* drill@$DRILL_HOST:/mnt/logs/plots/

### Clean up
rm $WORKDIR/$LOGFILE
rm *.png
