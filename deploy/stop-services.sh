#!/bin/bash

sudo systemctl is-active --quiet inventum.service
if [ $? -eq 0 ]
then
    sudo systemctl stop inventum.service
fi
