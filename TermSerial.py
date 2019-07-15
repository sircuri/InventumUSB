from __future__ import print_function

import serial
import sys
import time

class TermSerial:
    ESC = b'\033'
    CSI = b'['

    def __init__(self, device, rows=53, cols=80, baudrate=9600, parity=serial.PARITY_NONE, timeout=10):
        self.device = device
        self.serial = TermSerial._get_serial(device, baudrate, parity, timeout)
        self.row = 0
        self.col = 0
        self.rows = rows
        self.cols = cols
        self.buffer = [b' ' for _ in xrange(rows * cols)]
        self.mode = 0
        self.chars = ''
        self.sgr = 0
        self.sgr_line = [0 for _ in xrange(rows)]
        self.keep_running = True

    def reset(self):
        self.serial.flushInput()
        self.serial.flushOutput()

        self.row = 0
        self.col = 0
        self.buffer = [b' ' for _ in xrange(self.rows * self.cols)]
        self.mode = 0
        self.chars = ''
        self.sgr = 0
        self.sgr_line = [0 for _ in xrange(self.rows)]
        self.keep_running = True

    def interrupt(self):
        self.keep_running = False
        self.key_escape()
        self.key_escape()
        time.sleep(4)
        self.reset()

    # def dump(self):
    #     for row in xrange(self.rows):
    #         print(str(self.sgr_line[row]) + '~' + str(row + 1).rjust(2) + ': ' + ''.join(
    #             self.buffer[row * self.cols: (row + 1) * self.cols - 1]))
    #         if row == self.row:
    #             print('      ' + ''.join([' ' for _ in xrange(self.col)]) + '^')

    def set_raw_mode(self):
        self.mode = -1

    def has_raw_data(self):
        return len(self.buffer) > 0

    def get_raw_data(self):
        data = self.buffer
        self.buffer = []
        return data

    def set_normal_mode(self):
        self.reset()

    def has_bytes_waiting(self):
        return self.serial.inWaiting() > 0

    def read(self, length=-1):
        waiting = self.serial.inWaiting()
        bytes_to_read = min(waiting, length)
        if length == -1:  # read everything if -1
            bytes_to_read = waiting
        return self.serial.read(bytes_to_read)

    def writeln(self, value):
        self.write(value)
        self.key_enter()

    def write(self, value):
        for v in value:
            self.serial.write(v.encode())
            self.serial.read(1)

    def to_idx(self):
        return self.coord_to_idx(self.row + 1, self.col + 1)

    '''
    Rows and columns are 1-based
    '''
    def coord_to_idx(self, row, col):
        # print('('+str(row)+','+str(col)+') = ' + str(((row - 1) * self.cols) + (col - 1)))
        return ((row - 1) * self.cols) + (col - 1)

    def set_char(self, c):
        # print(str(self.to_idx()) + ' - ' + str(ord(c)))
        self.buffer[self.to_idx()] = c
        self.col = self.col + 1

    '''
    Rows and columns are 1-based
    '''
    def set_cursor(self, row, col):
        self.row = row - 1
        self.col = col - 1
        self.sgr_line[self.row] = self.sgr

    def cr(self):
        self.row = self.row + 1
        self.col = 0

    def nl(self):
        self.col = 0

    def clear_screen(self, full=False):
        if full:
            self.buffer = [' ' for _ in xrange(self.rows * self.cols)]
        else:
            num_items = self.rows * self.cols - self.to_idx()
            self.buffer[self.to_idx():self.rows * self.cols] = [' '] * num_items

    def selected_row(self):
        try:
            r = self.sgr_line.index(7, 2)
            return self.get_row(r + 1)
        except:
            return ""

    '''
    Rows and columns are 1-based
    '''
    def get_row(self, row):
        start = self.coord_to_idx(row, 1)
        end = start + self.cols - 1
        return b''.join(self.buffer[start:end])

    def current_row(self):
        return self.get_row(self.row + 1)

    def clear_line(self):
        num_items = self.coord_to_idx(self.row + 2, 1) - 1 - self.to_idx()
        self.buffer[self.to_idx():self.coord_to_idx(self.row + 2, 1) - 1] = [' '] * num_items

    def running(self):

        if self.has_bytes_waiting():
            chrs = self.read()
            if self.mode == -1:
                self.buffer += list(chrs)
            else:
                for c in chrs:
                    try:
                        if c == self.ESC:
                            if self.mode > 0:
                                # That is strange, reset and move on to next char
                                self.reset()
                                continue
                            self.mode = 1
                        elif c == self.CSI and self.mode == 1:
                            self.mode = 2
                        elif self.mode == 2:
                            # we are in escape mode. Handle commands
                            if c == b'J':
                                if len(self.chars) > 0:
                                    self.clear_screen(True)
                                    self.set_cursor(1, 1)
                                    self.chars = ''
                                else:
                                    self.clear_screen(False)
                                self.mode = 0
                            elif c == b'K':
                                self.clear_line()
                                self.mode = 0
                            elif c == b'm' or c == b'M':
                                if len(self.chars) > 0:
                                    self.sgr = int(self.chars)
                                else:
                                    self.sgr = 0
                                self.chars = ''
                                self.mode = 0
                            elif c == b'H':
                                pos = self.chars.split(';')
                                self.set_cursor(int(pos[0]), int(pos[1]))
                                self.chars = ''
                                self.mode = 0
                            elif c in '0123456789;':
                                self.chars += c
                            continue
                        elif c == b'\r':
                            self.cr()
                        elif c == b'\n':
                            self.nl()
                        else:
                            self.set_char(c)
                    except:
                        print("Error: ", sys.exc_info())
                        self.reset()

        return self.keep_running

    def press_key(self, value):
        self.serial.write(value)

    def key_escape(self):
        self.press_key(b'\033')

    def key_enter(self):
        self.press_key(b'\015')

    def key_up(self):
        self.press_key(b'\033[A')

    def key_down(self):
        self.press_key(b'\033[B')

    def close(self):
        self.serial.close()

    @staticmethod
    def _get_serial(device, baudrate, parity, timeout):
        ser = serial.Serial()
        ser.port = device
        ser.baudrate = baudrate
        ser.parity = parity
        ser.timeout = timeout
        ser.write_timeout = 2
        ser.open()
        return ser
