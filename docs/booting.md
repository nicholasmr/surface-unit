# Booting the Surface Unit

<b>- When powered on, a bootstrapping script should run automatically</b> <br>
*If not*, open a terminal and type:
```
bash surface-unit/drill-bootstrap.sh
```

<b>- Select the appropriate deployment</b>

* "Deep drill" assumes a full deployment with internet access
* "Shallow drill" assumes a standalone deployment without internet access
* "Undeployed" is for debugging and should not be selected

![](https://raw.githubusercontent.com/nicholasmr/surface-unit/main/docs/bootstrap/menu1.png#center){: style="width:500px"}    
    
<b>- Select the communication protocol for load and depth displays</b><br>
This is written on labels above the displays (*CRLF* or *MODBUS*).

![](https://raw.githubusercontent.com/nicholasmr/surface-unit/main/docs/bootstrap/menu2.png#center){: style="width:500px"}
  
## The bootstrap script

The bootstrap script runs the following tasks:

<b>- Network configuration</b> 

If full (deep drill) deployment selected, the surface unit is assumed to be on camp network with a fixed IP address:

``` 
sudo dhcpcd -S ip_address=10.2.3.10/16 \
    -S routers=10.2.1.1 -S domain_name_servers=10.2.1.1 eth0
```

*but* if you wish to instead get an IP address from a local DHCP server, run in a terminal: 

``` 
sudo dhcpcd eth0
```

If unable to resolve hostnames, try moving "dns" forward (immediately after “myhostname”) in `/etc/nsswitch.conf`.

<b>- Clock synchronization</b>
``` 
sudo systemctl restart systemd-timesyncd.service
sudo timedatectl set-ntp true &
sudo ntpdate 0.arch.pool.ntp.org
```

*but* if you want to set the time manually, run e.g.:

``` 
sudo timedatectl set-time '2022-11-20 16:14:50'
```

<b>- Mount the USB pen for saving drill logs</b>

``` 
sudo mount /dev/sda1 /mnt/logs/ -o umask=000
```

<b>- Run the communication script for the depth display</b> 

```
python2 surface-displays/codix560.py
```

<b>- Run the communication script for the load display</b> 

```
python2 surface-displays/pmdstrain.py
```

<b>- Run the drill communication backend</b>

``` 
python3 drill-dispatch/dispatch.py --debug --port=/dev/ttyAMA0
```
 
<b>- Run the drill control GUI</b>

``` 
python3 drill-control/drill-control.py
```
