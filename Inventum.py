from __future__ import print_function
import time

import TermSerial as Serial


class Inventum:

    STATE_IDLE = 0
    STATE_LOGIN = 1
    STATE_LOGIN_CODE_ENTERED = 2
    STATE_CHALLENGE = 3
    STATE_CHALLENGE_ENTERED = 4
    STATE_EXTRA_MENU = 5
    STATE_EXTRA_MENU_SELECTED = 6
    STATE_IO_STATUS = 7
    STATE_DATALOGGER = 8
    STATE_DATALOGGER_EXITED = 9
    STATE_IO_CHANGE_FAN = 10
    STATE_CMD_FAN_HIGH = 11
    STATE_CMD_FAN_RESET = 12

    MODE_TERM = 1
    MODE_BULK = 2

    MENU_IO = '6'
    MENU_IO_FAN = 17

    MENU_DATALOGGER = '9'

    LOGIN_CODE = '3845'  # Seems to be working for most Inventum Ecolution devices
    PIN_CODE = '19'

    def __init__(self, logger, device, reset_after):
        self.log = logger
        self.termser = Serial.TermSerial(device)
        self.datalogger_start = 0
        self.last_seen = self.millis()
        self.last_selected_menu_item = ''
        self.mode = self.MODE_TERM
        self.datalogger_header = []
        self.datalogger_buffer = []
        self.last_line_debug = ''
        self.reset_timeout = reset_after

        self._current_state = self.STATE_IDLE
        self.target_state = self.STATE_DATALOGGER

        self.last_command = self.millis()
        self.last_datalogger_entry = self.millis()
        self.current_status = 0

        self._on_data = None

    def __reset__(self):
        self.datalogger_start = 0
        self.last_seen = self.millis()
        self.last_selected_menu_item = ''
        self.mode = self.MODE_TERM
        self.datalogger_header = []
        self.datalogger_buffer = []
        self.last_line_debug = ''
        self._current_state = self.STATE_IDLE
        self.target_state = self.STATE_DATALOGGER

    @staticmethod
    def millis():
        return int(round(time.time() * 1000))

    @property
    def on_data(self):
        return self._on_data

    @on_data.setter
    def on_data(self, func):
        self._on_data = func

    def interrupt(self):
        self.termser.interrupt()

    def set_command_fan_high(self):
        self.last_command = self.millis()
        if self.current_status != 3:
            self.set_target_state(self.STATE_CMD_FAN_HIGH)

    def set_command_fan_auto(self):
        self.last_command = self.millis()
        if self.current_status == 3:
            self.set_target_state(self.STATE_CMD_FAN_RESET)

    def set_command_data_start(self):
        self.set_target_state(self.STATE_DATALOGGER)

    def set_command_data_stop(self):
        self.set_target_state(self.STATE_EXTRA_MENU)

    def __handle_on_data(self, log_entries):
        self.last_datalogger_entry = self.millis()
        if '3-standen' in log_entries:
            self.current_status = int(log_entries['3-standen']['value'])

        if self.on_data:
            self.on_data(log_entries)

    def __workflow_enter_login_code(self):
        self.log.debug('LOGIN: Entered %s', self.LOGIN_CODE)
        self.termser.writeln(self.LOGIN_CODE)
        self._current_state = self.STATE_LOGIN_CODE_ENTERED

    def __workflow_enter_pincode(self):
        self.log.debug('LOGIN: Entered pincode %s', self.PIN_CODE)
        self.termser.writeln(self.PIN_CODE)
        self._current_state = self.STATE_CHALLENGE_ENTERED

    def __workflow_goto_io_menu(self):
        self.termser.write(self.MENU_IO)
        self._current_state = self.STATE_EXTRA_MENU_SELECTED

    def __workflow_goto_datalogger(self):
        self.termser.write(self.MENU_DATALOGGER)
        self._current_state = self.STATE_DATALOGGER
        self.mode = self.MODE_BULK
        self.termser.set_raw_mode()
        self.datalogger_header = None
        self.datalogger_buffer = []
        self.datalogger_start = self.millis()
        self.last_datalogger_entry = self.millis()
        self.log.info('Entering datalogger sequence')

    def __workflow_io_select_fan(self):
        selected_row = self.termser.selected_row().strip()
        if selected_row != '' and selected_row != self.last_selected_menu_item:
            # /hack for now. Need to figure out this time out sequence
            self.last_seen = self.millis()
            # /endhack

            selected_menu = int(selected_row[1:3])
            self.log.debug('IO Status: Active menu item "%d"', selected_menu)

            if selected_menu < self.MENU_IO_FAN:
                self.termser.key_down()
            elif selected_menu > self.MENU_IO_FAN:
                self.termser.key_up()
            else:
                self.termser.key_enter()

            self.last_selected_menu_item = selected_row

    def __workflow_io_set_fan_high(self):
        self.log.info("SET value for parameter '3-standen' to: 3")
        self.termser.writeln('3')
        self._current_state = self.STATE_IDLE
        self.set_target_state(self.STATE_EXTRA_MENU)

    def __workflow_io_set_fan_auto(self):
        self.log.info("RESET value for parameter '3-standen'")
        self.termser.key_escape()
        self._current_state = self.STATE_IDLE
        self.set_target_state(self.STATE_EXTRA_MENU)

    def __should_wait(self, wait):
        return self.millis() - self.datalogger_start <= (wait * 1000)

    def __workflow_datalogger_read(self):

        if self.__should_wait(2):
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
                # self.log.debug('HEADER[%s]', str(self.datalogger_header))
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

                # self.log.debug('DATA[%s]', str(log_entries))
                self.__handle_on_data(log_entries)

    def __workflow_exit_datalogger(self):
        self.termser.set_normal_mode()
        self.termser.key_escape()
        self.mode = self.MODE_TERM
        self.datalogger_header = []
        self.datalogger_buffer = []
        self._current_state = self.STATE_DATALOGGER_EXITED

    def __workflow_io_previous_menu(self):
        self.termser.key_escape()
        self._current_state = self.STATE_IDLE

    def __check_current_status(self):
        if self._current_state == self.STATE_DATALOGGER:
            if self.millis() - self.last_datalogger_entry >= (5 * 60 * 1000):
                self.__workflow_exit_datalogger()

            elif self.current_status == 3 and self.millis() - self.last_command >= (self.reset_timeout * 60 * 1000):
                self.last_command = self.millis()
                self.set_target_state(self.STATE_CMD_FAN_RESET)

    def set_target_state(self, state):
        self.target_state = state
        self.last_seen = self.millis()

    def handle_workflow(self):

        self.__check_current_status()

        if self._current_state == self.STATE_LOGIN:
            self.__workflow_enter_login_code()
        elif self._current_state == self.STATE_CHALLENGE:
            self.__workflow_enter_pincode()
        elif self._current_state == self.STATE_EXTRA_MENU:
            if self.target_state == self.STATE_CMD_FAN_HIGH or self.target_state == self.STATE_CMD_FAN_RESET:
                self.__workflow_goto_io_menu()
            elif self.target_state == self.STATE_DATALOGGER:
                self.__workflow_goto_datalogger()
        elif self._current_state == self.STATE_IO_STATUS:
            if self.target_state == self.STATE_CMD_FAN_HIGH or self.target_state == self.STATE_CMD_FAN_RESET:
                self.__workflow_io_select_fan()
            elif self.target_state == self.STATE_EXTRA_MENU:
                self.__workflow_io_previous_menu()
        elif self._current_state == self.STATE_IO_CHANGE_FAN:
            if self.target_state == self.STATE_CMD_FAN_HIGH:
                self.__workflow_io_set_fan_high()
            elif self.target_state == self.STATE_CMD_FAN_RESET:
                self.__workflow_io_set_fan_auto()
        elif self._current_state == self.STATE_DATALOGGER:
            if self.target_state == self.STATE_CMD_FAN_HIGH or self.target_state == self.STATE_CMD_FAN_RESET:
                self.__workflow_exit_datalogger()
            elif self.target_state == self.STATE_EXTRA_MENU:
                self.__workflow_exit_datalogger()
            elif self.target_state == self.STATE_DATALOGGER:
                self.__workflow_datalogger_read()

    def start(self):
        self.termser.reset()
        self.termser.key_escape()
        self.termser.key_escape()

        self.log.info('Starting up TERM interface on Inventum Ecolution. Waiting for login...')

        while self.termser.running():

            time.sleep(0.1)

            if self.mode == self.MODE_TERM:
                line = self.termser.current_row()

                if self.last_line_debug != line:
                    self.log.debug('LINE: %s', line)
                    self.last_line_debug = line

                if line.find('Voer code in') != -1:
                    self._current_state = self.STATE_LOGIN

                elif line.find('Voer beveiligingscode in') != -1:
                    self._current_state = self.STATE_CHALLENGE

                elif self.termser.get_row(2).find(" EXTRAMENU") != -1 and self._current_state != self.STATE_EXTRA_MENU:
                    self._current_state = self.STATE_EXTRA_MENU
                    self.last_seen = self.millis()
                    self.log.info('Login successful')

                elif self.termser.get_row(1).find("IO status") != -1 and self._current_state != self.STATE_IO_STATUS:
                    self._current_state = self.STATE_IO_STATUS
                    self.log.debug('Activated IO Status menu')

                elif self.termser.get_row(51).find('   3-standen :') != -1:
                    self._current_state = self.STATE_IO_CHANGE_FAN
                    self.log.debug('Selected "3-standen" menu item for change')

                # wait 5 seconds, and reset to main menu
                elif self._current_state >= self.STATE_EXTRA_MENU and self.millis() - self.last_seen > 5000:
                    self.__reset__()

            self.handle_workflow()

        self.termser.close()
