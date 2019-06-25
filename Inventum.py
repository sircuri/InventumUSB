from __future__ import print_function
import time

import TermSerial as Serial


class Inventum:

    STATE_LOGIN = 1
    STATE_CHALLENGE = 2
    STATE_EXTRA_MENU = 3
    STATE_IO_STATUS = 4

    CMD_HIGH_FAN = 1
    CMD_AUTO_FAN = 2

    MENU_PARAMETERS = '6'

    MENU_IO_FAN = 17

    LOGIN_CODE = '3845'  # Seems to be working for most Inventum Ecolution devices
    PIN_CODE = '19'

    def __init__(self, logger):
        self.log = logger
        self.termser = Serial.TermSerial('/dev/ttyACM0')
        self.last_menu_selected = 0
        self.menu_timeout = 0
        self.last_selected_menu_item = ''
        self.state = self.STATE_LOGIN

        self.active_command = self.CMD_AUTO_FAN

        self.last_line_debug = ''

    @staticmethod
    def millis():
        return int(round(time.time() * 1000))

    def reset_menu(self):
        self.termser.key_escape()
        self.termser.key_escape()
        self.last_menu_selected = 0
        self.menu_timeout = 0
        self.last_selected_menu_item = ''

        self.active_command = self.CMD_AUTO_FAN

    def cmd_to_menu(self):
        if self.active_command == self.CMD_AUTO_FAN or self.active_command == self.CMD_HIGH_FAN:
            return self.MENU_IO_FAN

        return -1

    def handle_menu(self):
        if self.active_command == self.CMD_AUTO_FAN:
            self.set_fan_auto()
        elif self.active_command == self.CMD_HIGH_FAN:
            self.set_fan_high()

    def set_fan_high(self):
        if self.termser.get_row(51).find('   3-standen :') != -1:
            print('Yep, SET a new value for this parameter')
            self.reset_menu()

    def set_fan_auto(self):
        if self.termser.get_row(51).find('   3-standen :') != -1:
            print('Yep, RESET value for this parameter')
            self.reset_menu()

    def start(self):
        self.termser.reset()
        self.termser.key_escape()

        while self.termser.running():

            time.sleep(0.1)

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
                self.state = self.STATE_EXTRA_MENU
                self.log.info('We are in the main menu')

                self.termser.write(self.MENU_PARAMETERS)
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

        self.termser.close()
