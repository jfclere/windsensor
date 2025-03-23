#!/usr/bin/python
#   networking daemon running on Raspberry PI for wind-measuring
#   Copyright (C) 2014-2015 Patrick Rudolph

#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.

#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.


import http.server
import socketserver
import subprocess
import sys
import threading
from _thread import start_new_thread
import time
import RPi.GPIO as GPIO
import math
import time

# ring buffer to be able to report max med min in x minutes interval
class RingBuffer:

    def __init__(self, size: int):
        self.buffer =  [1] * size
        self.pos = 0

    def add(self, value: int):
        if self.pos >= len(self.buffer):
            self.pos = 0
        self.buffer[self.pos] = value
        self.pos += 1

    @property
    def median(self) -> int:
        values = sorted(list(self.buffer))
        return values[round(len(values) * 0.5)] # not really the medium value but the one in middle of the sorted value.

    @property
    def max(self) -> int:
        values = sorted(list(self.buffer))
        return values[len(values)-1]

    @property
    def min(self) -> int:
        values = sorted(list(self.buffer))
        return values[0]


PINSENSOR=37

# RPi.GPIO Layout verwenden (wie Pin-Nummern)
GPIO.setmode(GPIO.BOARD)

# Pin 37 (GPIO 26) auf Input setzen
GPIO.setup(PINSENSOR, GPIO.IN, pull_up_down=GPIO.PUD_UP)

imp_per_sec = 0
actual_windspeed_msec = 0
events = []
rb = RingBuffer(600) # 10 minutes buffer

def interrupt(val):
        global imp_per_sec
        imp_per_sec += 1

GPIO.add_event_detect(PINSENSOR, GPIO.RISING, callback = interrupt, bouncetime = 5)

def ws100_imp_to_mpersec(val):
        #y = 8E-09x5 - 2E-06x4 + 0,0002x3 - 0,0073x2 + 0,4503x + 0,11

        y = float("8e-9") * math.pow(val,5) - float("2e-6") * math.pow(val,4) + float("2e-4") * math.pow(val,3) - float("7.3e-3") * math.pow(val,2) + 0.4503 * val + 0.11
        if y < 0.2:
                y = 0
        return y

# calcul the value every sec (so we have m/s)
def threadeval():
        global imp_per_sec
        global actual_windspeed_msec
        global rb
        while 1:
                actual_windspeed_msec = ws100_imp_to_mpersec(imp_per_sec)
                #print("actual_windspeed_msec %f" % actual_windspeed_msec)
                imp_per_sec = 0
                rb.add(int(round(actual_windspeed_msec)))
                for x in events:
                    x.set()
                time.sleep(1)

# calcul 600 sec max, med and min values
def threadeval600():
        global imp_per_sec
        global actual_windspeed_msec
        global rb
        while 1:
                time.sleep(600)
                print("sec600_windspeed_msec med %d" % rb.median)
                print("sec600_windspeed_msec max %d" % rb.max)
                print("sec600_windspeed_msec min %d" % rb.min)

start_new_thread(threadeval, ())
start_new_thread(threadeval600, ())

HOST = ''
PORT = 2400

############################################################################

class MyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def do_GET(self):
        global actual_windspeed_msec
        self.event = threading.Event()
        events.append(self.event)
        print(self.client_address)

        self.send_response(200)
        self.send_header('transfer-encoding', 'chunked')
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        while 1:
            self.event.wait()
            self.event.clear()
            try:
                text = '{"windspeed": %f, "time": "%s"}\n' % (actual_windspeed_msec,time.strftime('%X %x %Z'))
                chunk = '{0:x}\r\n'.format(len(text)) + text + '\r\n'
                self.wfile.write(chunk.encode(encoding='utf-8'))
                #self.wfile.flush()
            except Exception as e:
                print(e)
                break

        events.remove(self.event)

############################################################################

if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer((HOST, PORT), MyHandler)
    # terminate with Ctrl-C
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.socket.close()
        sys.exit(0)

############################################################################
