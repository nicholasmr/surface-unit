# Software overview 

* The Surface Unit software is [available here](https://github.com/nicholasmr/surface-unit).
* On the Surface Unit, all the software is located at `/home/drill/surface-unit`.
* All manuals, datasheets, and other documentation are located at `/home/drill/surface-unit/documentation`.
* The software can be updated to the latest version by opening a terminal and running 

```
cd surface-unit
bash update.sh
```

## Installing

If wanting to install the software from scratch, note that:

* The software relies on both `python2` and `python3`, and

```
apt-get install dialog redis-server
```

* The following python packages are required by the Surface Unit software

```
pip2 install redis minimalmodbus docopt termcolor pyvesc pythoncrc
pip3 install redis minimalmodbus docopt termcolor pyvesc pythoncrc
pip3 install numpy scipy ahrs PyQt5 redis pyqtgraph 
```

* The following *additional* packages are required for processing logs etc.

```
pip3 install pandas 
```

