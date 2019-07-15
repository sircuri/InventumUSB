import Inventum as Inventum

import logging
import configparser
import os
import gzip
import sys
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


config = configparser.RawConfigParser()
config.read('inventumusb.conf')

mqttserver = config.get("mqtt", "server", fallback="localhost")
mqttport = config.getint("mqtt", "port", fallback=1883)
mqtttopic = config.get("mqtt", "topic", fallback="goodwe")
mqttclientid = config.get("mqtt", "clientid", fallback="inventum-usb")

loglevel = config.get("inventum", "loglevel", fallback="INFO")
logfile = config.get("inventum", "logfile", fallback="/var/log/inventum.log")

numeric_level = getattr(logging, loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging_setup(numeric_level, logfile)
logger = logging.getLogger('main')

inventum = Inventum.Inventum(logger)
inventum.start()
