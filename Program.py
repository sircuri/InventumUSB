#!/usr/bin/python -tt
from daemonpy.daemon import Daemon

import Inventum as Inventum
import logging
import configparser
import os
import gzip
import sys
import json
import paho.mqtt.client as mqtt


class InventumProcessor(object):
    def __init__(self):
        self.client = None
        self.inventum = None
        self.mqtttopic = ''

    @staticmethod
    def logging_namer(name):
        return name + ".gz"

    @staticmethod
    def logging_rotator(source, dest):
        with open(source, "rb") as sf:
            data = sf.read()
            with gzip.open(dest, "wb") as df:
                df.write(data)
        os.remove(source)

    def logging_setup(self, level, log_file, foreground):

        # If we are running in the foreground we use stderr for logging, if running as forking daemon we use the logfile
        if foreground:
            logging.basicConfig(format='%(asctime)-15s %(funcName)s(%(lineno)d) - %(levelname)s: %(message)s',
                                stream=sys.stderr, level=level)
        else:
            logging.basicConfig(format='%(asctime)-15s %(funcName)s(%(lineno)d) - %(levelname)s: %(message)s',
                                filename=log_file, level=level)

    def on_message(self, client, userdata, message):
        payload = str(message.payload.decode("utf-8"))
        logging.info('Received command: %s', payload)

        if payload == 'FAN=1':
            self.inventum.set_command_fan_high()
        elif payload == 'FAN=0':
            self.inventum.set_command_fan_auto()
        elif payload == 'DATA=1':
            self.inventum.set_command_data_start()
        elif payload == 'DATA=0':
            self.inventum.set_command_data_stop()
        elif payload == 'QUIT':
            self.inventum.interrupt()
        else:
            logging.error('Unknown command received: %s', payload)

    def on_data(self, data):
        json_data = json.dumps(data)
        combinedtopic = self.mqtttopic + '/data'
        logging.debug('Publishing data to MQTT on channel %s', combinedtopic)
        self.client.publish(combinedtopic, json_data)

    def run_process(self, foreground):
        config = configparser.RawConfigParser()
        config.read('/etc/inventumusb.conf')

        mqttserver = config.get("mqtt", "server", fallback="localhost")
        mqttport = config.getint("mqtt", "port", fallback=1883)
        self.mqtttopic = config.get("mqtt", "topic", fallback="ventilation/inventum")
        mqttclientid = config.get("mqtt", "clientid", fallback="inventum-usb")
        mqttusername = config.get("mqtt", "username", fallback="")
        mqttpasswd = config.get("mqtt", "password", fallback=None)

        loglevel = config.get("inventum", "loglevel", fallback="INFO")
        logfile = config.get("inventum", "logfile", fallback="/var/log/inventum.log")
        device = config.get("inventum", "device", fallback="/dev/ttyACM0")

        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)

        self.logging_setup(numeric_level, logfile, foreground)

        try:
            self.client = mqtt.Client(mqttclientid)
            if mqttusername != "":
                self.client.username_pw_set(mqttusername, mqttpasswd);
                logging.debug("Set username -%s-, password -%s-", mqttusername, mqttpasswd)
            self.client.connect(mqttserver, port=mqttport)
            logging.info('Connected to MQTT %s:%s', mqttserver, mqttport)
            self.client.on_message = self.on_message
            logging.info('Waiting for commands on MQTT channel %s/commands', self.mqtttopic)
            self.client.subscribe(self.mqtttopic + '/commands')
            self.client.loop_start()
        except Exception as e:
            logging.error("%s:%s: %s", mqttserver, mqttport, e)
            return 3

        self.inventum = Inventum.Inventum(logging, device)
        self.inventum.on_data = self.on_data
        self.inventum.start()

        self.client.loop_stop()
        return 0


class MyDaemon(Daemon):
    def run(self):
        _processor = InventumProcessor()
        _processor.run_process(foreground=False)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: %s start|stop|restart|foreground" % sys.argv[0])
        sys.exit(2)

    if 'foreground' == sys.argv[1]:
        processor = InventumProcessor()
        ret_val = processor.run_process(foreground=True)
        sys.exit(ret_val)

    daemon = MyDaemon('/var/run/inventum.pid', '/dev/null', '/dev/null', '/dev/null')

    if 'start' == sys.argv[1]:
        daemon.start()
    elif 'stop' == sys.argv[1]:
        daemon.stop()
    elif 'restart' == sys.argv[1]:
        daemon.restart()
    else:
        print("Unknown command")
        sys.exit(2)
    sys.exit(0)
