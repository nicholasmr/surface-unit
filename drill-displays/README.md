# displays
This repository contains code to read the winch encoder and load cells. 

We should find a better way to figure out the device nodes of these two. Right now we just know that the load cell is on `/dev/ttyUSB0` and the winch encoder is on `/dev/ttyUSB1` -- but why? Maybe udev can help us?
