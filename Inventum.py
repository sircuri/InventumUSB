from __future__ import print_function
import time

import TermSerial as Serial


class Inventum:

    LOGIN = 1
    CHALLENGE = 2
    EXTRA_MENU = 3
    IO_STATUS = 4

    LOGIN_CODE = '3845'  # Seems to be working for most Inventum Ecolution devices
    PIN_CODE = '19'

    def __init__(self, logger):
        self.log = logger
        self.termser = Serial.TermSerial('/dev/ttyACM0')
        self.last_menu_selected = 0
        self.menu_timeout = 0
        self.last_selected_menu_item = ''
        self.state = self.LOGIN

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
                self.state = self.LOGIN
                self.log.info('LOGIN: Entered %s', self.LOGIN_CODE)
                self.termser.writeln(self.LOGIN_CODE)
            elif line.find('Voer beveiligingscode in') != -1:
                self.state = self.CHALLENGE
                self.log.info('LOGIN: Entered pincode %s', self.PIN_CODE)
                self.termser.writeln(self.PIN_CODE)
            elif self.termser.get_row(2).find(" EXTRAMENU") != -1:
                self.state = self.EXTRA_MENU
                self.log.info('We are in the main menu')

                self.termser.write('6')
                self.menu_timeout = self.millis()
            elif self.termser.get_row(1).find("IO status") != -1:
                self.state = self.IO_STATUS

                selected_row = self.termser.selected_row().strip()
                if selected_row != self.last_selected_menu_item:

                    if selected_row != '':

                        print(selected_row)
                        selected_menu = int(selected_row[1:3])
                        if selected_menu < 17:
                            self.termser.key_down()
                        elif selected_menu > 17:
                            self.termser.key_up()
                        else:
                            print ("Joy... found the menu item")
                            self.termser.key_enter()

                    self.last_selected_menu_item = selected_row

            elif self.termser.get_row(51).find('   3-standen :') != -1:
                print('Yep, enter a new value for this parameter')
                self.reset_menu()
            elif self.state > self.EXTRA_MENU and self.millis() - self.menu_timeout > 5000:  # wait 5 seconds, and reset to main menu
                self.reset_menu()

        self.termser.close()
