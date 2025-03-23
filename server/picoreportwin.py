#!/usr/bin/python3
# SPDX-License-Identifier: Apache-2.0

import os
import time
import socket
import sys
import wifi

from _thread import start_new_thread
from machine import Pin

from nodeinfo import nodeinfo
from windsensor import RingBuffer, interrupt, threadeval, getval600

# wait until we have an IP
i = 1
while i < 30:
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
  except: 
    time.sleep(1)
    i += 1
    continue
  break
net = True 
if i == 30:
  # We don't have network
  net = False

if not net:
  print("NO Network!")

mywifi = wifi.Picow()
try:
    mywifi.connectwifi()
except Exception as e:
    print("exception in connectwifi()")
    print(str(e))
    time.sleep(10)
    machine.reset()

myinfo = nodeinfo()
if myinfo.read(mywifi):
  # Use some default values
  print("myinfo.read() Failed!")
  myinfo.TIME_ACTIVE = 0
  myinfo.WAIT_TIME = 120
  myinfo.MAINT_MODE = False
else:
  print("Connected")

# prepare the wind logic
PINSENSOR=22
pinsensor=Pin(PINSENSOR, Pin.IN, Pin.PULL_UP)
pinsensor.irq(handler=interrupt, trigger=Pin.IRQ_RISING)

start_new_thread(threadeval, ())

# send the stuff
if net:
  while True:
    time.sleep(600) # 10 minutes
    try:
      mess = getval600()
      mess = bytes(mess, 'utf-8')
      url = "/webdav/" + myinfo.REMOTE_DIR + "/wind.txt"
      mywifi.sendserver(mess, url)
    except Exception as ex:
      print("Send Wind to web failed")
      print(str(ex))
