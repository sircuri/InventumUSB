#!/bin/bash

targetpath=/opt/inventumusb

sudo ln -f -s ${targetpath}/systemd/system/inventum.service "/etc/systemd/system/inventum.service"

echo "Start Inventum Service"
sudo systemctl start inventum.service

sleep 15

sudo systemctl is-active --quiet inventum.service
if [ $? -eq 0 ]
then
    echo "Inventum Service started"
    exit 0
else
    echo "Service not started"
    exit 1
fi