#if PICO_RP2350A
#define NUM_ADC_CHANNELS _u(5)
#define ADC_BASE_PIN _u(26)
#else
#define NUM_ADC_CHANNELS _u(9)
#define ADC_BASE_PIN _u(40)
#endif
