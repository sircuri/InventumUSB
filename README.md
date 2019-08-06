# InventumUSB
Effort to control Inventum Ecolution Solo device from Python

Special thanks to [Stefan1975](https://tweakers.net/gallery/227200) for doing the heavy lifting on cracking the "login" procedure.

## Device information

**Device**: Ecolution Virtual COM port
 
**USB Vendor**: 0d59

**USB Product**: 0007

## Required Python version

I'm currently using **Python 2.7.13** on a Raspberry Pi for this project.
Python 2.7 is already installed (at least on my Raspberry Zero W)

```bash
sudo apt-get update
sudo apt-get install -y python-pip
```

## Required python modules

* pySerial
* enum
* configparser
* paho-mqtt

```bash
sudo python -m pip install pySerial enum configparser paho-mqtt
```

## Config

Create file _/etc/inventumusb.conf_:

```
[inventum]
#loglevel = INFO
#logfile = /var/log/inventum.log
#device = /dev/ttyACM0
#reset = 20

[mqtt]
#server = localhost
#port = 1883
#topic = ventilation/inventum/commands
#clientid = inventum-usb
#username = 
#password = mypassword
```
Almost all configuration parameters have sensible defaults and are commented out. The values shown are the defaults. If 
you need to change a setting remove the # in front of the parameter name. Only when username and the optional password 
are set, they will be used. Setting the username will trigger authentication for the MQTT server. 

Password can optionally be set.

## Usage

The application needs to be run as **root** in the current setup. It tries to write a pid-file in _/var/run_ and the 
high level logs for the daemon are written to _/var/log/inventum.log_

To start the daemon application:

```bash
$ sudo ./Program.py start
```
The program can also be started in the foreground with all logging to stdout. Start the program as follows:

```bash
$ sudo ./Program.py foreground
```

## Inventum information

The application will start to deliver information packets on the configured MQTT channel.
The channel is composed as:
* '**ventilation** / **inventum** / **data**' for the data logger information as JSON.

It also respond to commands send on MQTT channel:

* '**ventilation** / **inventum** / **commands**'

Supported commands are:
* **FAN=1**: Change the ventilation to mode MAX
* **FAN=0**: Revert the ventilation to the AUTO mode
* **DATA=1** (default): Start the Data Logger function of the Inventum device. This is the default command that gets executed
upon application start
* **DATA=0**: Stops the Data Logger function (does not do much, as the application reverts to the default command)
* **QUIT**: Stops the application

## Systemd

Systemd will collect all logging information in it's journal. 
The service unit allows one to run as a system user.

Create the user as follows:

```bash
useradd --system inventum
```

The following inventum.service file shall be placed in _/etc/systemd/system/inventum.service_.

```bash
[Unit]
Description=Inventum USB Controller
After=basic.target

[Service]
Type=simple
User=inventum
Group=inventum
ExecStart=/opt/inventumusb/Program.py foreground
Restart=always
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

To allow the system user to interact with the ttyACM0 device, add the following to a file _/etc/udev/rules.d/inventum.rules_

```bash
KERNEL=="ttyACM[0-9]*",ATTRS{idVendor}=="0d59",ATTRS{idProduct}=="0007",MODE="0660",GROUP="inventum",SYMLINK+="inventum"
```
Where idVendor and idProduct correspond to the above mentioned values of the Inventum Ecolution device. Restart the Raspberry or reload the udev config manually.

The program can now as usual be started by:
 
```bash
 systemctl start inventum.service
```

Systemd will run the program as the user _inventum_ and take care of restarting it when necessary. All logging 
information will be shown in the systemd logs.
