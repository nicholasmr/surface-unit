# Drill orientation

The BNO055 is a System in Package (SiP), integrating a triaxial 14-bit accelerometer, a triaxial 16-bit gyroscope with a range of ±2000 degrees per second, a triaxial geomagnetic sensor and a 32-bit cortex M0+ microcontroller running Bosch Sensortec sensor fusion software, in a single package.

![](https://raw.githubusercontent.com/nicholasmr/surface-unit/main/docs/orientation/BNO055.png#center){: style="width:400px"}

## Calibrating the BNO055

Though the sensor fusion software runs the calibration algorithm of all the three sensors (accelerometer, gyroscope and magnetometer) in the background to remove the offsets, some preliminary steps had to be ensured for this automatic calibration to take place.
The accelerometer and the gyroscope are relatively less susceptible to external disturbances, as a result of which the offset is negligible. Whereas the magnetometer is susceptible to external magnetic field and therefore to ensure proper heading accuracy, the calibration steps described below have to be taken.
Depending on the sensors been selected, the following simple steps had to be taken after every ‘Power on Reset’ for proper calibration of the device.

### Routine recommended in datasheet

* Place the device in 6 different stable positions for a period of few seconds to allow the accelerometer to calibrate.
    * Make sure that there is slow movement between 2 stable positions.
    * The 6 stable positions could be in any direction, but it is best if the device is lying at least once perpendicular to the x, y and z axis.
* Place the device in a single stable position for a period of few seconds to allow the gyroscope to calibrate.

### Routine for drill deployment

At EastGRIP, the following routine was found to be sufficient:

* Power on drill while laying horizontal tower and let it rest for 10 seconds.
* Rotate drill slowly around own axis at 90 deg. intervals and let it rest for a few seconds.
* Tilt tower to 45 deg. and repeat rotation.
* Tilt tower to 90 deg. and repeat rotation.
* If sensor quality values (`Sensor Q` in drill control GUI) are larger than 1 for most sensors, the calibration profile is useful (`Q>=1` is preferred).

![](https://raw.githubusercontent.com/nicholasmr/surface-unit/main/docs/orientation/Q.png){: style="width:300px"}

* <b>If calibration is poor, return tower to horizontal and try again.</b>
* Once satisfied, save the calibration profile in slot `1` or `2` so that it can be reloaded later in case the BNO055 automatically re-calibrates (happens once in a while):

![](https://raw.githubusercontent.com/nicholasmr/surface-unit/main/docs/orientation/saveload.png){: style="width:180px"}

* Descend the drill with power on throughout descent.

If you want consistent heading (azimuth) and roll information from the drill, e.g. when using the spring for directional drilling, an additional step is needed:

* Make sure the spring (or some other marker on the drill) is pointing away from the tower (i.e. pointing straight upwards when tower is horizontal) and bring the tower to 10 to 30 deg. from plumb and press `Zero ref.`. 
This will align the drill orientation with the tower/trench frame-of-reference (the azimuth and roll dials should then align with zero).


<!-- ![](https://raw.githubusercontent.com/nicholasmr/surface-unit/main/docs/orientation/values.png){: style="width:150px"} -->

