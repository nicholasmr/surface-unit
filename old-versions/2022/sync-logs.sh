#!/bin/bash
rsync -HPSavx /mnt/logs/ admin@10.2.3.1:/share/Public/drill-logs/
