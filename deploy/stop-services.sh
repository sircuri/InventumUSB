#!/bin/bash

if ps aux | grep '[r]estartd'; then
    echo "Stop Restartd daemon"
    sudo service restartd stop
fi

pid=$(ps aux | grep '[P]rogram.py' | awk '{print $2}')
if [ -n "$pid" ]; then
	echo "Stop Inventum python application"
	sudo kill "$pid"
fi
