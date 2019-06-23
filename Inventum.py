from __future__ import print_function
import time

import TermSerial as Serial


class Inventum:

    def __init__(self, ):
        self.termser = Serial.TermSerial('/dev/ttyACM0')
        self.menu = -1
        self.last_menu_selected = 0
        self.menu_timeout = 0
        self.last_selected_menu_item = ''

    @staticmethod
    def millis():
        return int(round(time.time() * 1000))

    def reset_menu(self):
        self.termser.key_escape()
        self.termser.key_escape()
        self.menu = -1
        self.last_menu_selected = 0
        self.menu_timeout = 0
        self.last_selected_menu_item = ''

    def select_io_row(self, menu_item):
        if self.last_menu_selected < menu_item:
            self.termser.key_down()
            self.last_menu_selected = self.last_menu_selected + 1

    def start(self):
        self.termser.reset()
        self.termser.key_escape()

        while self.termser.running():

            time.sleep(0.1)

            line = self.termser.current_row()
            if line.find('Voer code in') != -1:
                print('We need to enter code')
                self.termser.writeln('3845')
            elif line.find('Voer beveiligingscode in') != -1:
                print('We need to enter security code')
                self.termser.writeln('19')
            elif self.termser.get_row(2).find(" EXTRAMENU") != -1:
                print('We are logged in!')
                self.menu = 0
                self.termser.write('6')
                self.menu_timeout = self.millis()
            elif self.termser.get_row(1).find("IO status") != -1:
                self.menu = 6

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
            elif self.millis() - self.menu_timeout > 5000:  # wait 5 seconds, and reset to main menu
                self.reset_menu()

        self.termser.close()
