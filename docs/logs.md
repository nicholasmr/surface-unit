# Drill logs

Drill logs are saved on the inserted USB pen in `/mnt/logs`.<br>

<p style="color:#cb181d;"><b>If a USB pen is NOT inserted, drill logs will NOT be saved!</b></p>

## Processing

The log files must be processed to get the equivelent comma-separated-value (.csv) file type.
This should be done externally and is not possible on the Surface Unit.

The following steps demonstrate how to do this:

* Power down the surface unit and remove the USB pen.
* Insert the USB pen into a Linux computer where the processing will take place.
* Download the surface unit software package [from here](https://github.com/nicholasmr/surface-unit/archive/refs/heads/main.zip) and extract the .zip file.
* Move the log files from the USB pen into the `logging/drill-logs` subdirectory.
* Process a given log file by entering the `logging/` subdirectory and running (where `8` and `24` are the hours during that day to consider, but can be replaced by other hours)

```
python3 plot-drill-log.py drill-logs/drill.log.YYYY-MM-DD 8 24 
```

* The processed .csv log file is dumped in `logging/drill-logs-processed` alongside a summary plot.

![](https://raw.githubusercontent.com/nicholasmr/surface-unit/main/docs/orientation/drill-log-2024-05-24--13-21.png#center){: style="width:700px"}

## Calculating orientation profile

Once the drill log has been processed, the drill orientation can be calculated using standard AHRS algorithms that rely on the measured vectors of acceleration, magnetic field, gyro, etc.

The surface unit software supports only the [SAAM algorithm](https://ahrs.readthedocs.io/en/latest/filters/saam.html) which gives results close to estimates based on the tilt of the acceleration vector, but is more accurate as it includes the magnetic field.
While these methods give the full orientation quarternion, only inclination and heading (azimuth) angles are outputted. 

To generate a .csv file of drill inclination and heading, run the following command for a given processed drill log file (note that `12` and `17` is the interval of hours during that day to consider, but can be replaced by other hours)

```
python3 plot-drill-orientation.py \
    drill-logs-processed/drill.log.processed.YYYY-DD-HH.csv 12 17
```

The processed .csv file is dumped in `logging/drill-logs-processed` alongside an orientation profile plot.

![](https://raw.githubusercontent.com/nicholasmr/surface-unit/main/docs/orientation/drill-orientation-2024-05-24.png#center){: style="width:530px"}

