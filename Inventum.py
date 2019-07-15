from __future__ import print_function
import time

import TermSerial as Serial


class Inventum:

    STATE_IDLE = 0
    STATE_LOGIN = 1
    STATE_CHALLENGE = 2
    STATE_EXTRA_MENU = 3
    STATE_IO_STATUS = 4
    STATE_DATALOGGER = 5

    CMD_NONE = 1

    MODE_TERM = 1
    MODE_BULK = 2

    MENU_PARAMETERS = '6'
    MENU_IO_FAN = 17
    CMD_IO_HIGH_FAN = 61
    CMD_IO_AUTO_FAN = 62

    MENU_DATALOGGER = '9'
    CMD_DATA_START = 91
    CMD_DATA_STOP = 92

    DEFAULT_CMD = CMD_DATA_START

    LOGIN_CODE = '3845'  # Seems to be working for most Inventum Ecolution devices
    PIN_CODE = '19'

    def __init__(self, logger):
        self.log = logger
        self.termser = Serial.TermSerial('/dev/ttyACM0')
        self.last_menu_selected = 0
        self.menu_timeout = 0
        self.last_selected_menu_item = ''
        self.state = self.STATE_IDLE
        self.mode = self.MODE_TERM
        self.active_command = self.DEFAULT_CMD
        self.datalogger_header = []
        self.datalogger_buffer = []
        self.last_line_debug = ''

        self._on_data = None

    @staticmethod
    def millis():
        return int(round(time.time() * 1000))

    @property
    def on_data(self):
        return self._on_data

    @on_data.setter
    def on_data(self, func):
        self._on_data = func

    def reset_menu(self):
        self.termser.key_escape()
        self.termser.key_escape()
        self.last_menu_selected = 0
        self.menu_timeout = 0
        self.last_selected_menu_item = ''
        self.state = self.STATE_IDLE
        self.mode = self.MODE_TERM
        self.datalogger_header = []
        self.datalogger_buffer = []
        self.active_command = self.DEFAULT_CMD

    def cmd_to_mainmenu(self):
        if self.active_command == self.CMD_IO_AUTO_FAN or self.active_command == self.CMD_IO_HIGH_FAN:
            return self.MENU_PARAMETERS
        if self.active_command == self.CMD_DATA_START:
            self.state = self.STATE_DATALOGGER
            self.mode = self.MODE_BULK
            self.termser.set_raw_mode()
            self.datalogger_header = None
            self.datalogger_buffer = []
            return self.MENU_DATALOGGER

        return '-1'

    def cmd_to_menu(self):
        if self.active_command == self.CMD_IO_AUTO_FAN or self.active_command == self.CMD_IO_HIGH_FAN:
            return self.MENU_IO_FAN

        return -1

    def handle_menu(self):
        if self.active_command == self.CMD_IO_AUTO_FAN:
            self.set_fan_auto()
        elif self.active_command == self.CMD_IO_HIGH_FAN:
            self.set_fan_high()

    def should_wait(self, wait):
        return self.millis() - self.menu_timeout <= (wait * 1000)

    def handle_datalogger(self):

        if self.should_wait(2):
            return

        if self.termser.has_raw_data():
            self.datalogger_buffer += self.termser.get_raw_data()

            data = ''.join(self.datalogger_buffer)
            idx = data.find("Interval")
            header = 1479
            if idx != -1:
                ln = 21
                data = data[idx + ln:]
                self.datalogger_buffer = list(data)

            if not self.datalogger_header and len(data) >= header:
                hdr = map(lambda x: x.strip()
                                     .replace('(', '')
                                     .replace(')', '')
                                     .replace(' ', '_')
                                     .replace('.', ''), data[0:header].split(','))
                self.datalogger_header = zip(hdr[0::2], hdr[1::2])
                self.log.debug('HEADER[%s]', str(self.datalogger_header))
                data = data[header+1:]
                self.datalogger_buffer = list(data)

            idx = data.find('\r\n')
            if idx != -1:
                entries = data[:idx].split(',')
                self.datalogger_buffer = list(data[idx+2:])

                log_entries = dict()
                for i, h in enumerate(self.datalogger_header):
                    log_entries[h[1]] = {
                        "value": entries[(i*2)+1],
                        "status": entries[(i*2)]
                    }

                if self.on_data:
                    self.on_data(log_entries)

    def set_fan_high(self):
        print(self.termser.get_row(51))
        if self.termser.get_row(51).find('   3-standen :') != -1:
            self.log.info('Yep, SET a new value for this parameter')
            self.reset_menu()

    def set_fan_auto(self):
        if self.termser.get_row(51).find('   3-standen :') != -1:
            self.log.info('Yep, RESET value for this parameter')
            self.reset_menu()

    def set_command_fan_high(self):
        self.termser.set_normal_mode()
        self.reset_menu()
        self.active_command = self.CMD_IO_HIGH_FAN

    def set_command_fan_auto(self):
        self.termser.set_normal_mode()
        self.reset_menu()
        self.active_command = self.CMD_IO_AUTO_FAN

    def set_command_data_start(self):
        self.active_command = self.CMD_DATA_START

    def set_command_data_stop(self):
        self.active_command = self.CMD_DATA_STOP
        self.termser.set_normal_mode()
        self.reset_menu()

    def interrupt(self):
        self.termser.interrupt()

    def start(self):
        self.termser.reset()
        self.termser.key_escape()
        self.termser.key_escape()

        while self.termser.running():

            time.sleep(0.1)

            if self.mode == self.MODE_TERM:
                line = self.termser.current_row()

                if self.last_line_debug != line:
                    self.log.debug('LINE: %s', line)
                    self.last_line_debug = line

                if line.find('Voer code in') != -1:
                    self.state = self.STATE_LOGIN
                    self.log.info('LOGIN: Entered %s', self.LOGIN_CODE)
                    self.termser.writeln(self.LOGIN_CODE)
                elif line.find('Voer beveiligingscode in') != -1:
                    self.state = self.STATE_CHALLENGE
                    self.log.info('LOGIN: Entered pincode %s', self.PIN_CODE)
                    self.termser.writeln(self.PIN_CODE)
                elif self.termser.get_row(2).find(" EXTRAMENU") != -1:
                    if self.state != self.STATE_EXTRA_MENU:
                        self.state = self.STATE_EXTRA_MENU
                        self.log.info('We are in the main menu')

                    goto_mainmenu = self.cmd_to_mainmenu()
                    if goto_mainmenu != '-1':
                        self.termser.write(goto_mainmenu)
                        self.menu_timeout = self.millis()

                elif self.termser.get_row(1).find("IO status") != -1:
                    self.state = self.STATE_IO_STATUS

                    selected_row = self.termser.selected_row().strip()
                    if selected_row != self.last_selected_menu_item:
                        if selected_row != '':

                            selected_menu = int(selected_row[1:3])
                            self.log.debug('MAINMENU: Active menu item "%d"', selected_menu)

                            goto_menu = self.cmd_to_menu()
                            if goto_menu != -1:

                                if selected_menu < goto_menu:
                                    self.termser.key_down()
                                elif selected_menu > goto_menu:
                                    self.termser.key_up()
                                else:
                                    self.termser.key_enter()

                        self.last_selected_menu_item = selected_row
                elif self.state == self.STATE_IO_STATUS:
                    self.handle_menu()
                # wait 5 seconds, and reset to main menu
                elif self.state > self.STATE_EXTRA_MENU and self.millis() - self.menu_timeout > 5000:
                    self.reset_menu()

            else:
                if self.state == self.STATE_DATALOGGER:
                    self.handle_datalogger()

        self.termser.close()
