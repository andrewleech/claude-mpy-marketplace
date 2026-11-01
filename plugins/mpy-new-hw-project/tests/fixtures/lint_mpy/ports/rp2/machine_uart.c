#define IS_VALID_PERIPH(uart, pin)  (((((pin) + 4) & 8) >> 3) == (uart))
#if PICO_RP2350
#define IS_VALID_TX(uart, pin)      (((pin) & 1) == 0 && IS_VALID_PERIPH(uart, pin))
#define IS_VALID_RX(uart, pin)      (((pin) & 1) == 1 && IS_VALID_PERIPH(uart, pin))
#else
#define IS_VALID_TX(uart, pin)      (((pin) & 3) == 0 && IS_VALID_PERIPH(uart, pin))
#define IS_VALID_RX(uart, pin)      (((pin) & 3) == 1 && IS_VALID_PERIPH(uart, pin))
#endif
#define IS_VALID_CTS(uart, pin)     (((pin) & 3) == 2 && IS_VALID_PERIPH(uart, pin))
#define IS_VALID_RTS(uart, pin)     (((pin) & 3) == 3 && IS_VALID_PERIPH(uart, pin))
