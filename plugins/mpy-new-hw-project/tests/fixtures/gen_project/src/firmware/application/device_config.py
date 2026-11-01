"""
Application settings and their defaults.

Plain module-level constants, so nothing has to be imported or frozen to read
them. Override by editing this file, or shadow the module with a copy on the
device filesystem (boot.py puts the filesystem ahead of frozen modules).
"""

import logging

# Name of the pin driving the status LED. Board specific: this default matches
# the board the project was generated for and will need changing for another.
LED_PIN = "LED"

# Blink timing, in seconds.
LED_ON_TIME = 1.0
LED_OFF_TIME = 1.0

# Start the application tasks automatically on boot. Set False to bring the
# device up at the REPL with the hardware initialised but idle.
AUTORUN = True

# Logging threshold applied in main.py.
LOG_LEVEL = logging.INFO
