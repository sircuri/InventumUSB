#!/bin/bash

targetpath=/opt/inventumusb

echo "Create installation folder $targetpath"
sudo mkdir -p "$targetpath"

echo "Purge installation folder $targetpath"
sudo rm -rf $targetpath/*

echo "Copy application to $targetpath"
sudo cp -r * $targetpath
echo "Add executable flag on $targetpath/Program.py"
sudo chmod +x $targetpath/Program.py

echo "Move ./etc/inventumusb.conf to /etc"
sudo cp -f inventumusb.conf.replaced /etc/inventumusb.conf
