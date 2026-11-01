#if MICROPY_PY_MACHINE_SPI

#ifdef MICROPY_HW_SPI_NO_DEFAULT_PINS
#define MICROPY_SPI_PINS_ARG_OPTS MP_ARG_REQUIRED
#else
#define MICROPY_SPI_PINS_ARG_OPTS 0
#endif

#define IS_VALID_PERIPH(spi, pin)   ((((pin) & 8) >> 3) == (spi))
#define IS_VALID_SCK(spi, pin)      (((pin) & 3) == 2 && IS_VALID_PERIPH(spi, pin))
#define IS_VALID_MOSI(spi, pin)     (((pin) & 3) == 3 && IS_VALID_PERIPH(spi, pin))
#define IS_VALID_MISO(spi, pin)     (((pin) & 3) == 0 && IS_VALID_PERIPH(spi, pin))

#endif
