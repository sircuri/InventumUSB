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
from logging.handlers import TimedRotatingFileHandler


class InventumProcessor(object):
    def __init__(self):
        self.mainlogger = None
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

    def logging_setup(self, level, log_file):
        formatter = logging.Formatter('%(asctime)-15s %(funcName)s(%(lineno)d) - %(levelname)s: %(message)s')

        filehandler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        filehandler.setFormatter(formatter)

        stdouthandler = logging.StreamHandler(sys.stdout)
        stdouthandler.setFormatter(formatter)

        self.mainlogger = logging.getLogger('main')
        self.mainlogger.namer = InventumProcessor.logging_namer
        self.mainlogger.rotator = InventumProcessor.logging_rotator
        self.mainlogger.addHandler(filehandler)
        self.mainlogger.addHandler(stdouthandler)
        self.mainlogger.setLevel(level)

    def on_message(self, client, userdata, message):
        payload = str(message.payload.decode("utf-8"))
        self.mainlogger.info('Received command: %s', payload)

        if payload == 'FAN_HIGH':
            self.inventum.set_command_fan_high()
        elif payload == 'FAN_AUTO':
            self.inventum.set_command_fan_auto()
        elif payload == 'DATA_START':
            self.inventum.set_command_data_start()
        elif payload == 'DATA_STOP':
            self.inventum.set_command_data_stop()
        elif payload == 'KILL':
            self.inventum.interrupt()
        else:
            self.mainlogger.error('Unknown command received: %s', payload)

    def on_data(self, data):
        json_data = json.dumps(data)
        self.mainlogger.debug('DATA[%s]', json_data)
        combinedtopic = self.mqtttopic + '/data'
        self.client.publish(combinedtopic, json_data)

    def run_process(self):
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

        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)

        self.logging_setup(numeric_level, logfile)

        try:
            self.client = mqtt.Client(mqttclientid)
            if mqttusername != "":
                self.client.username_pw_set(mqttusername, mqttpasswd);
                self.mainlogger.debug("Set username -%s-, password -%s-", mqttusername, mqttpasswd)
            self.client.connect(mqttserver, port=mqttport)
            self.client.on_message = self.on_message
            self.client.subscribe(self.mqtttopic + '/commands')
            self.client.loop_start()
        except Exception as e:
            self.mainlogger.error("%s:%s: %s", mqttserver, mqttport, e)
            return 3

        self.mainlogger.info('Connected to MQTT %s:%s', mqttserver, mqttport)

        self.inventum = Inventum.Inventum(self.mainlogger)
        self.inventum.on_data = self.on_data
        self.inventum.start()

        self.client.loop_stop()
        return 0


class MyDaemon(Daemon):
    def run(self):
        _processor = InventumProcessor()
        _processor.run_process()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: %s start|stop|restart|foreground" % sys.argv[0])
        sys.exit(2)

    if 'foreground' == sys.argv[1]:
        processor = InventumProcessor()
        ret_val = processor.run_process()
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
