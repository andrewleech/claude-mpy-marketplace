import asyncio
import unittest

from hardware import Blinky
from machine import Pin


class RecordingPin(Pin):
    """A pin that remembers everything written to it."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.writes = []

    def value(self, val=None):
        if val is None:
            return super().value()
        self.writes.append(int(bool(val)))
        return super().value(val)


class TestBlinky(unittest.TestCase):
    def test_starts_idle(self):
        blinky = Blinky(RecordingPin("TEST", Pin.OUT), 0.01, 0.01)
        self.assertFalse(blinky.running.is_set())

    def test_start_and_stop_gate_the_task(self):
        blinky = Blinky(RecordingPin("TEST", Pin.OUT), 0.01, 0.01)
        blinky.start()
        self.assertTrue(blinky.running.is_set())
        blinky.stop()
        self.assertFalse(blinky.running.is_set())

    def test_stop_leaves_the_led_off(self):
        pin = RecordingPin("TEST", Pin.OUT)
        pin.value(1)
        blinky = Blinky(pin, 0.01, 0.01)
        blinky.stop()
        self.assertEqual(pin.value(), 0)

    def test_running_drives_the_led_both_ways(self):
        pin = RecordingPin("TEST", Pin.OUT)
        blinky = Blinky(pin, 0.01, 0.01)

        async def run():
            blinky.start()
            task = asyncio.create_task(blinky.task())
            # Several periods, so the assertion does not depend on timing.
            await asyncio.sleep(0.1)
            task.cancel()

        asyncio.run(run())
        self.assertIn(1, pin.writes)
        self.assertIn(0, pin.writes)

    def test_idle_task_leaves_the_led_alone(self):
        pin = RecordingPin("TEST", Pin.OUT)
        blinky = Blinky(pin, 0.01, 0.01)

        async def run():
            task = asyncio.create_task(blinky.task())
            await asyncio.sleep(0.05)
            task.cancel()

        asyncio.run(run())
        self.assertEqual(pin.writes, [])
