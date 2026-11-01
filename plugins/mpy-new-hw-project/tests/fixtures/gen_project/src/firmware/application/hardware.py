"""
Hardware objects for the device.

Everything that touches a peripheral is constructed here, so the unix port can
substitute src/unix/simulation and the rest of the application stays portable.
"""

import asyncio
import logging

from machine import Pin

import device_config

log = logging.getLogger("hardware")


class Blinky:
    """Flashes an LED, as a stand-in for the application's real work."""

    def __init__(self, pin, on_time, off_time):
        self.pin = pin
        self.on_time = on_time
        self.off_time = off_time
        self.running = asyncio.Event()

    async def task(self):
        log.info("Starting blinky")
        while True:
            await self.running.wait()

            self.pin.value(1)
            await asyncio.sleep(self.on_time)

            self.pin.value(0)
            await asyncio.sleep(self.off_time)

    def start(self):
        self.running.set()

    def stop(self):
        self.running.clear()
        self.pin.value(0)


class DeviceCollection:
    """The device's hardware, gathered so tests can substitute the lot."""

    def __init__(self, blinky):
        self.blinky = blinky


led = Pin(device_config.LED_PIN, Pin.OUT)

devices = DeviceCollection(
    blinky=Blinky(led, device_config.LED_ON_TIME, device_config.LED_OFF_TIME),
)


def shutdown():
    devices.blinky.stop()
