import Inventum as Inventum

import logging
import configparser
import os
import gzip
import sys
import json
import paho.mqtt.client as mqtt
from logging.handlers import TimedRotatingFileHandler


def logging_namer(name):
    return name + ".gz"


def logging_rotator(source, dest):
    with open(source, "rb") as sf:
        data = sf.read()
        with gzip.open(dest, "wb") as df:
            df.write(data)
    os.remove(source)


def logging_setup(level, log_file):
    formatter = logging.Formatter('%(asctime)-15s %(funcName)s(%(lineno)d) - %(levelname)s: %(message)s')

    filehandler = logging.handlers.RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    filehandler.setFormatter(formatter)

    stdouthandler = logging.StreamHandler(sys.stdout)
    stdouthandler.setFormatter(formatter)

    mainlogger = logging.getLogger('main')
    mainlogger.namer = logging_namer
    mainlogger.rotator = logging_rotator
    mainlogger.addHandler(filehandler)
    mainlogger.addHandler(stdouthandler)
    mainlogger.setLevel(level)


def on_message(client, userdata, message):
    payload = str(message.payload.decode("utf-8"))
    logger.info('Received command: %s', payload)

    if payload == 'FAN_HIGH':
        inventum.set_command_fan_high()
    elif payload == 'FAN_AUTO':
        inventum.set_command_fan_auto()
    elif payload == 'DATA_START':
        inventum.set_command_data_start()
    elif payload == 'DATA_STOP':
        inventum.set_command_data_stop()
    elif payload == 'KILL':
        inventum.interrupt()
    else:
        logger.error('Unknown command received: %s', payload)


def on_data(data):
    json_data = json.dumps(data)
    logger.debug('DATA[%s]', json_data)
    client.publish("ventilation/inventum/data", json_data)


config = configparser.RawConfigParser()
config.read('inventumusb.conf')

mqttserver = config.get("mqtt", "server", fallback="localhost")
mqttport = config.getint("mqtt", "port", fallback=1883)
mqtttopic = config.get("mqtt", "topic", fallback="ventilation/inventum/commands")
mqttclientid = config.get("mqtt", "clientid", fallback="inventum-usb")

loglevel = config.get("inventum", "loglevel", fallback="INFO")
logfile = config.get("inventum", "logfile", fallback="/var/log/inventum.log")

numeric_level = getattr(logging, loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging_setup(numeric_level, logfile)
logger = logging.getLogger('main')

try:
    client = mqtt.Client(mqttclientid)
    # if mqttusername != "":
    #     client.username_pw_set(mqttusername, mqttpasswd);
    #     logging.debug("Set username -%s-, password -%s-", mqttusername, mqttpasswd)
    client.connect(mqttserver, port=mqttport)
    client.on_message = on_message
    client.subscribe(mqtttopic)
    client.loop_start()
except Exception as e:
    logging.error("%s:%s: %s", mqttserver, mqttport, e)

inventum = Inventum.Inventum(logger)
inventum.on_data = on_data
inventum.start()
