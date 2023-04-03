# neemrelay
This program makes the NEEM drill work with the EastGRIP surface unit. By running the `neemrelay.py` script the serial connection from the hole is bound to a TCP port.

## How to do it
*Note:* Since NEEM uses the downhole frequencies for the uphole and vice versa you need to flip the little red switch on the modem in the surface unit for this to work.

On the NEEM drill laptop open COM2TCP and connect to `10.2.3.10` port `5556`. Then use that COM port in the drill software to communicate. Note that the laptop should be on the EastGRIP network.
