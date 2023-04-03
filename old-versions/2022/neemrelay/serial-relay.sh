#!/bin/bash
socat tcp-l:9998,reuseaddr,fork,cr file:/dev/ttyAMA0,echo=0,b600,raw,cr,icanon=1
