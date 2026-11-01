"""
`machine` stand-in for running the application on the unix port.

Re-exports mock_machine, which models Pin, I2C, SPI, UART, ADC, PWM, Timer,
WDT and RTC. Anything needing real peripheral behaviour belongs in an on-target
test.
"""

from mock_machine import *
from mock_machine import SPI as _MockSPI


class SPI(_MockSPI):
    """SPI taking the constructor arguments of the hardware ports; the mock takes the id only."""

    def __init__(self, id=None, baudrate=1000000, **kwargs):
        super().__init__(id)
        self.init(baudrate, **kwargs)
