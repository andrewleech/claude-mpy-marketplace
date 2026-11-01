"""
The application: task setup and the asyncio event loop.
"""

import asyncio
import logging

import device_config
import hardware
import version
from hardware import devices

log = logging.getLogger("device")

# Top level tasks the device runs. Each is a coroutine function taking no
# arguments; add to this list as the application grows.
TASKS = (devices.blinky.task,)


def start_repl():
    """Start aiorepl with the application modules already in scope."""
    import aiorepl

    namespace = {
        "asyncio": asyncio,
        "device_config": device_config,
        "hardware": hardware,
        "devices": devices,
        "version": version,
    }
    log.info("Starting aiorepl")
    return asyncio.create_task(aiorepl.task(namespace))


def run():
    """Start the application and run until the device resets."""
    log.info("%s %s", version.application_name, version.firmware_version)

    loop = asyncio.get_event_loop()

    for task in TASKS:
        loop.create_task(task())

    start_repl()
    devices.blinky.start()

    loop.run_forever()
