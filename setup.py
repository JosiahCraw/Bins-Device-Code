import sys
import os

if not 'Adafruit_SSD1306' in sys.modules:
    os.system("git clone https://github.com/adafruit/Adafruit_Python_SSD1306.git")
    os.system("sudo python3 Adafruit_Python_SSD1306/setup.py install")
if not 'firebase_admin' in sys.modules:
    os.system("sudo pip3 install firebase-admin")
if not 'board' in sys.modules:
    os.system("sudo pip3 install board")
if not 'neopixel' in sys.modules:
    os.system("sudo pip3 install rpi_ws281x adafruit-circuitpython-neopixel")
