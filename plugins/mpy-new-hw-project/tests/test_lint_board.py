"""Tests for lint_board.py: C macro evaluator, pin tables, port rules, CLI."""

import json
import shutil
from pathlib import Path

import lint_board
import pytest
from lint_board import CEval, CEvalError, _tokenize, parse_c_macros

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MPY = FIXTURES / "lint_mpy"
BOARDS = FIXTURES / "lint_boards"
REAL_MPY = Path("/home/corona/micropython")
needs_real = pytest.mark.skipif(
    not (REAL_MPY / "ports" / "stm32").is_dir(), reason="no MicroPython checkout"
)


# ----------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------


def per(name, kind, pins, **extra):
    return {"name": name, "kind": kind, "pins": pins, **extra}


def lint(port, board, peripherals=None, tmp_path=None, mpy=MPY):
    """Lint a board directory, writing peripherals to a temporary file when given."""
    pfile = None
    if peripherals is not None:
        pfile = tmp_path / "peripherals.json"
        pfile.write_text(json.dumps({"peripherals": peripherals}))
    return lint_board.lint_board(mpy, port, Path(board), pfile)


def board_copy(tmp_path, name, **files):
    """Copy a fixture board and replace or add files; None removes a file."""
    dest = tmp_path / "board"
    shutil.copytree(BOARDS / name, dest)
    for fname, text in files.items():
        fname = fname.replace("__", ".")
        if text is None:
            (dest / fname).unlink()
        else:
            (dest / fname).write_text(text)
    return dest


def has(messages, *needles):
    return any(all(n in m for n in needles) for m in messages)


# ----------------------------------------------------------------------------------------
# C expression evaluator and macro parser
# ----------------------------------------------------------------------------------------


def evaluate(expr, macros=None):
    return CEval(macros or {}).evaluate(_tokenize(expr))


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("1 + 2 * 3", 7),
        ("(1 + 2) * 3", 9),
        ("0x10 >> 2", 4),
        ("1 << 4 | 1", 17),
        ("6 & 3 == 2", 0),  # == binds tighter than &
        ("(6 & 3) == 2", 1),
        ("1 && 0 || 1", 1),
        ("!0 + ~0", 0),
        ("-3 + 5", 2),
        ("7u + 1UL", 8),
        ("9 % 4 + 9 / 4", 3),
    ],
)
def test_evaluator_arithmetic(expr, expected):
    assert evaluate(expr) == expected


def test_evaluator_rejects_unknown_names_and_garbage():
    with pytest.raises(CEvalError):
        evaluate("UNKNOWN + 1")
    with pytest.raises(CEvalError):
        evaluate("1 +")
    with pytest.raises(CEvalError):
        evaluate("1 2")
    with pytest.raises(CEvalError):
        evaluate("1 / 0")


def test_function_like_macros_nest_and_bind_parameters():
    macros = parse_c_macros(
        "#define PERIPH(u, p) (((p) & 8) >> 3) == (u)\n"
        "#define VALID(u, p) (((p) & 3) == 2 && PERIPH(u, p))\n"
        "#define BASE 8\n",
        {},
    )
    ev = CEval(macros)
    assert ev.call("VALID", [0, 2]) == 1
    assert ev.call("VALID", [1, 2]) == 0
    assert ev.call("VALID", [1, 10]) == 1
    assert ev.call("VALID", [0, 3]) == 0
    assert evaluate("BASE + 1", macros) == 9


def test_continuation_lines_and_comments_are_handled():
    macros = parse_c_macros(
        "#define A(x) /* c */ ((x) + \\\n    1)  // tail\n",
        {},
    )
    assert CEval(macros).call("A", [4]) == 5


UART_SRC = """
#define IS_VALID_PERIPH(uart, pin)  (((((pin) + 4) & 8) >> 3) == (uart))
#if PICO_RP2350
#define IS_VALID_TX(uart, pin)      (((pin) & 1) == 0 && IS_VALID_PERIPH(uart, pin))
#else
#define IS_VALID_TX(uart, pin)      (((pin) & 3) == 0 && IS_VALID_PERIPH(uart, pin))
#endif
"""


def test_conditionals_on_known_names_choose_the_branch():
    on = CEval(parse_c_macros(UART_SRC, {"PICO_RP2350": 1}))
    off = CEval(parse_c_macros(UART_SRC, {"PICO_RP2350": 0}))
    assert on.call("IS_VALID_TX", [0, 2]) == 1
    assert off.call("IS_VALID_TX", [0, 2]) == 0
    assert on.call("IS_VALID_TX", [0, 1]) == 0
    assert off.call("IS_VALID_TX", [0, 0]) == 1


def test_conditionals_on_unknown_names_take_the_first_branch():
    macros = parse_c_macros(
        "#if MICROPY_SOMETHING\n#define X 1\n#else\n#define X 2\n#endif\n"
        "#ifdef MICROPY_OTHER\n#define Y 3\n#else\n#define Y 4\n#endif\n",
        {"PICO_RP2350": 0},
    )
    assert evaluate("X", macros) == 1
    assert evaluate("Y", macros) == 3


def test_elif_and_nested_conditionals():
    src = (
        "#if PICO_RP2350\n#define V 1\n#elif PICO_RP2040\n#define V 2\n#else\n#define V 3\n#endif\n"
        "#if PICO_RP2350\n#if MICROPY_X\n#define W 5\n#endif\n#endif\n"
    )
    assert evaluate("V", parse_c_macros(src, {"PICO_RP2350": 1, "PICO_RP2040": 0})) == 1
    assert evaluate("V", parse_c_macros(src, {"PICO_RP2350": 0, "PICO_RP2040": 1})) == 2
    assert evaluate("V", parse_c_macros(src, {"PICO_RP2350": 0, "PICO_RP2040": 0})) == 3
    assert "W" in parse_c_macros(src, {"PICO_RP2350": 1})
    assert "W" not in parse_c_macros(src, {"PICO_RP2350": 0})


# ----------------------------------------------------------------------------------------
# pins.csv
# ----------------------------------------------------------------------------------------


def test_pins_csv_hidden_prefix_comments_and_unnamed_rows_are_accepted(tmp_path):
    board = board_copy(
        tmp_path, "stm32_ok", pins__csv="A,PA2\n-B,-PA3\n# c\n\n,PB6\nC,PB7\n"
    )
    result = lint("stm32", board)
    assert result == {"errors": [], "warnings": [], "unchecked": []}


def test_pins_csv_rows_need_exactly_two_entries(tmp_path):
    board = board_copy(
        tmp_path, "stm32_ok", pins__csv="A,PA2\nB,PA3,extra\nLONELY\nC,\n"
    )
    errors = lint("stm32", board)["errors"]
    assert has(errors, "pins.csv:2: expecting two entries")
    assert has(errors, "pins.csv:3: expecting two entries")
    assert has(errors, "pins.csv:4: missing port pin name")


def test_pins_csv_duplicate_name_on_another_pad_is_an_error(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv="A,PA2\nA,PA3\n")
    assert has(
        lint("stm32", board)["errors"], "duplicate pin name A (first maps to PA2)"
    )


def test_pins_csv_hidden_name_collides_with_visible_name(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv="A,PA2\n-A,PA3\n")
    assert has(lint("stm32", board)["errors"], "duplicate pin name A")


def test_pins_csv_name_repeated_for_the_same_pad_is_a_warning(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv="A,PA2\nA,PA2\n")
    result = lint("stm32", board)
    assert result["errors"] == []
    assert has(result["warnings"], "pins.csv:2: A listed more than once")


def test_pins_csv_port_name_the_port_does_not_accept_is_an_error(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv="A,PA2\nB,PZ9\nC,X1\n")
    errors = lint("stm32", board)["errors"]
    assert has(errors, "PZ9 is not a pad of the stm32 port")
    assert has(errors, "X1 is not a pad of the stm32 port")


def test_pins_csv_pad_without_af_row_is_a_warning(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv="A,PA2\nC,PA4\n")
    result = lint("stm32", board)
    assert result["errors"] == []
    assert has(result["warnings"], "PA4 has no row in", "only plain GPIO use")
    # The pad takes part in no bus, so a bus function on it is reported.
    result = lint(
        "stm32",
        board,
        [per("u", "uart", {"tx": "C"}, bus_id=2)],
        tmp_path,
    )
    assert has(result["errors"], "C (PA4) has no UART2_TX or USART2_TX")


def test_pins_csv_bad_identifier(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv="1BAD,PA2\nGOOD,PA3\n")
    errors = lint("stm32", board)["errors"]
    assert has(errors, "'1BAD' is not a valid Python identifier")


def test_pins_csv_missing_is_error_except_on_cmake_ports(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv=None)
    assert has(lint("stm32", board)["errors"], "pins.csv not found")
    for port, name in (("esp32", "esp32_ok"), ("rp2", "rp2040_ok")):
        board = tmp_path / f"{port}_board"
        shutil.copytree(BOARDS / name, board)
        (board / "pins.csv").unlink()
        result = lint(port, board)
        assert result["errors"] == []
        assert has(result["warnings"], "no pins.csv")


def test_rp2_without_pins_csv_accepts_cpu_pin_names(tmp_path):
    board = tmp_path / "board"
    shutil.copytree(BOARDS / "rp2040_ok", board)
    (board / "pins.csv").unlink()
    result = lint(
        "rp2",
        board,
        [
            per("i", "i2c", {"scl": "GPIO5", "sda": "GPIO4"}, bus_id=0),
            per("g", "gpio", {"pin": "GP3"}),
        ],
        tmp_path,
    )
    assert has(result["errors"], "pin GP3 cannot be resolved without pins.csv")
    assert not has(result["errors"], "'i'")


def test_empty_pins_csv_is_an_error(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv="# nothing\n")
    assert has(lint("stm32", board)["errors"], "no pin rows")


def test_missing_mpconfigboard_file_is_an_error(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", mpconfigboard__mk=None)
    assert has(lint("stm32", board)["errors"], "no mpconfigboard.mk")


def test_af_file_missing_from_checkout_is_an_error(tmp_path):
    board = board_copy(
        tmp_path, "stm32_ok", mpconfigboard__mk="AF_FILE = boards/nope.csv\n"
    )
    assert has(lint("stm32", board)["errors"], "nope.csv not found")


def test_af_file_comes_from_an_included_makefile(tmp_path):
    mpy = tmp_path / "mpy"
    shutil.copytree(MPY, mpy)
    base = mpy / "ports/stm32/boards/LINT_BASE"
    base.mkdir(parents=True)
    (base / "mpconfigboard.mk").write_text(
        "MCU_SERIES = f7\nAF_FILE ?= boards/lint_af.csv\n"
    )
    board = board_copy(
        tmp_path,
        "stm32_ok",
        mpconfigboard__mk="include boards/LINT_BASE/mpconfigboard.mk\n",
    )
    assert lint("stm32", board, mpy=mpy)["errors"] == []


def test_conditional_assignment_does_not_override_an_earlier_value(tmp_path):
    text = "AF_FILE = boards/lint_af.csv\nAF_FILE ?= boards/nope.csv\n"
    board = board_copy(tmp_path, "stm32_ok", mpconfigboard__mk=text)
    assert lint("stm32", board)["errors"] == []


# ----------------------------------------------------------------------------------------
# peripheral structure
# ----------------------------------------------------------------------------------------


def test_peripheral_structure_errors(tmp_path):
    result = lint(
        "stm32",
        BOARDS / "stm32_ok",
        [
            per("a", "dac", {"pin": "ADC_IN"}),
            per("b", "i2c", {"scl": "I2C1_SCL"}, bus_id=1),
            per("c", "gpio", {"pin": "ADC_IN", "extra": "ADC_IN"}),
            per("d", "uart", {}, bus_id=2),
            per("e", "i2c", {"scl": "I2C1_SCL", "sda": "I2C1_SDA"}),
            per("b", "gpio", {"pin": "ADC_IN"}),
            per("1x", "gpio", {"pin": "ADC_IN"}),
        ],
        tmp_path,
    )
    errors = result["errors"]
    assert has(errors, "'a'", "unknown kind 'dac'")
    assert has(errors, "'b'", "pins.sda missing")
    assert has(errors, "'c'", "unexpected pin role 'extra'")
    assert has(errors, "'d'", "at least one of pins.tx, pins.rx")
    assert has(errors, "'e'", "bus_id missing")
    assert has(errors, "'b'", "duplicate peripheral name")
    assert has(errors, "name must be a Python identifier")


def test_unknown_pin_name_is_an_error(tmp_path):
    result = lint(
        "stm32", BOARDS / "stm32_ok", [per("x", "gpio", {"pin": "NOPE"})], tmp_path
    )
    assert has(result["errors"], "pin NOPE is not in pins.csv")


def test_non_string_pin_is_an_error(tmp_path):
    result = lint(
        "stm32", BOARDS / "stm32_ok", [per("x", "gpio", {"pin": 5})], tmp_path
    )
    assert has(result["errors"], "pin name must be a non-empty string")


def test_chip_select_pin_must_exist(tmp_path):
    spi = per(
        "flash",
        "spi",
        {"sck": "SPI3_SCK", "mosi": "SPI3_MOSI"},
        bus_id=3,
        devices=[{"name": "nor", "cs": "NOPE"}],
    )
    result = lint("stm32", BOARDS / "stm32_ok", [spi], tmp_path)
    assert has(result["errors"], "device 'nor' cs", "NOPE is not in pins.csv")


def test_shared_pad_gives_warning(tmp_path):
    result = lint(
        "stm32",
        BOARDS / "stm32_ok",
        [per("a", "gpio", {"pin": "LED_GREEN"}), per("b", "gpio", {"pin": "FLASH_CS"})],
        tmp_path,
    )
    assert result["errors"] == []
    assert has(result["warnings"], "PC13 is used by a.pin, b.pin")


def test_malformed_peripherals_file_is_a_usage_error(tmp_path):
    bad = tmp_path / "p.json"
    bad.write_text('{"peripherals": 3}')
    with pytest.raises(lint_board.UsageError):
        lint_board.lint_board(MPY, "stm32", BOARDS / "stm32_ok", bad)
    bad.write_text("not json")
    with pytest.raises(lint_board.UsageError):
        lint_board.lint_board(MPY, "stm32", BOARDS / "stm32_ok", bad)


# ----------------------------------------------------------------------------------------
# stm32
# ----------------------------------------------------------------------------------------

STM32_GOOD = [
    per("led", "led", {"pin": "LED_GREEN"}),
    per("sensors", "i2c", {"scl": "I2C1_SCL", "sda": "I2C1_SDA"}, bus_id=1),
    per(
        "flash",
        "spi",
        {"sck": "SPI3_SCK", "mosi": "SPI3_MOSI", "miso": "SPI3_MISO"},
        bus_id=3,
        devices=[{"name": "nor", "cs": "FLASH_CS"}],
    ),
    per("console", "uart", {"tx": "U2_TX", "rx": "U2_RX"}, bus_id=2),
    per("aux", "uart", {"tx": "U4_TX", "rx": "U4_RX"}, bus_id=4),
    per("vbat", "adc", {"pin": "ADC_IN"}),
    per("fan", "pwm", {"pin": "FAN_PWM"}),
]


def test_stm32_accepts_pins_that_match_the_bus_ids(tmp_path):
    result = lint("stm32", BOARDS / "stm32_ok", STM32_GOOD, tmp_path)
    assert result["errors"] == []
    # LED_GREEN and FLASH_CS share PC13 in the fixture.
    assert has(result["warnings"], "PC13")


def test_stm32_pin_without_the_bus_function(tmp_path):
    result = lint(
        "stm32",
        BOARDS / "stm32_ok",
        [per("s", "spi", {"sck": "SPI3_MOSI", "mosi": "SPI3_MOSI"}, bus_id=3)],
        tmp_path,
    )
    assert has(
        result["errors"],
        "SPI3_MOSI (PB5) has no SPI3_SCK for sck of spi bus 3",
        "SPI3_SCK is on PB3",
    )


def test_stm32_wrong_bus_id_for_pins(tmp_path):
    result = lint(
        "stm32",
        BOARDS / "stm32_ok",
        [per("s", "i2c", {"scl": "I2C1_SCL", "sda": "I2C1_SDA"}, bus_id=2)],
        tmp_path,
    )
    assert has(result["errors"], "I2C1_SCL (PB8) has no I2C2_SCL")
    assert has(result["errors"], "I2C1_SDA (PB9) has no I2C2_SDA")


def test_stm32_bus_without_pin_macro_on_the_board(tmp_path):
    header = (BOARDS / "stm32_ok" / "mpconfigboard.h").read_text()
    header = header.replace("#define MICROPY_HW_I2C1_SCL (pin_B8)\n", "")
    board = board_copy(tmp_path, "stm32_ok", mpconfigboard__h=header)
    result = lint(
        "stm32",
        board,
        [per("s", "i2c", {"scl": "I2C1_SCL", "sda": "I2C1_SDA"}, bus_id=1)],
        tmp_path,
    )
    expected = (
        "peripheral 's': mpconfigboard.h does not define MICROPY_HW_I2C1_SCL; "
        "I2C(1) has no scl pin on this board"
    )
    assert result["errors"] == [expected]


def test_stm32_uart_accepts_usart_and_uart_signal_names(tmp_path):
    result = lint(
        "stm32",
        BOARDS / "stm32_ok",
        [
            per("a", "uart", {"tx": "U2_TX"}, bus_id=2),
            per("b", "uart", {"tx": "U4_TX"}, bus_id=4),
        ],
        tmp_path,
    )
    assert result["errors"] == []


def test_stm32_uart_tx_on_rx_pad(tmp_path):
    result = lint(
        "stm32",
        BOARDS / "stm32_ok",
        [per("a", "uart", {"tx": "U2_RX"}, bus_id=2)],
        tmp_path,
    )
    assert has(result["errors"], "U2_RX (PA3) has no UART2_TX or USART2_TX")


def test_stm32_board_macro_pin_differs_from_peripheral_pin(tmp_path):
    header = (
        (BOARDS / "stm32_ok" / "mpconfigboard.h")
        .read_text()
        .replace("pin_B8", "pin_B6")
    )
    board = board_copy(tmp_path, "stm32_ok", mpconfigboard__h=header)
    result = lint(
        "stm32",
        board,
        [per("s", "i2c", {"scl": "I2C1_SCL", "sda": "I2C1_SDA"}, bus_id=1)],
        tmp_path,
    )
    assert has(
        result["errors"],
        "MICROPY_HW_I2C1_SCL is pin_B6 but the peripheral uses I2C1_SCL (PB8)",
    )


def test_stm32_unparsable_board_macro_is_unchecked(tmp_path):
    header = (
        (BOARDS / "stm32_ok" / "mpconfigboard.h")
        .read_text()
        .replace("(pin_B8)", "PIN(B8)")
    )
    board = board_copy(tmp_path, "stm32_ok", mpconfigboard__h=header)
    result = lint(
        "stm32",
        board,
        [per("s", "i2c", {"scl": "I2C1_SCL", "sda": "I2C1_SDA"}, bus_id=1)],
        tmp_path,
    )
    assert result["errors"] == []
    assert has(result["unchecked"], "MICROPY_HW_I2C1_SCL")


def test_stm32_adc_and_pwm_functions(tmp_path):
    result = lint(
        "stm32",
        BOARDS / "stm32_ok",
        [
            per("v", "adc", {"pin": "FAN_PWM"}),  # PB6 has no ADC channel
            per("f", "pwm", {"pin": "FLASH_CS"}),  # PC13 has no timer channel
        ],
        tmp_path,
    )
    assert has(result["errors"], "'v'", "FAN_PWM (PB6) has no ADC channel")
    assert has(result["errors"], "'f'", "FLASH_CS (PC13) has no TIMx_CHy")


def test_stm32_non_numeric_bus_id_is_unchecked(tmp_path):
    result = lint(
        "stm32",
        BOARDS / "stm32_ok",
        [per("s", "uart", {"tx": "U2_TX"}, bus_id="LP1")],
        tmp_path,
    )
    assert result["errors"] == []
    assert has(result["unchecked"], "bus_id 'LP1' is not a number")


# ----------------------------------------------------------------------------------------
# mimxrt
# ----------------------------------------------------------------------------------------

MIMXRT_GOOD = [
    per("console", "uart", {"tx": "D1", "rx": "D0"}, bus_id=1),
    per("sensors", "i2c", {"scl": "SCL", "sda": "SDA"}, bus_id=0),
    per("flash", "spi", {"sck": "SCK", "mosi": "SDO", "miso": "SDI"}, bus_id=0),
    per("vbat", "adc", {"pin": "A0"}),
    per("fan", "pwm", {"pin": "PWM1"}),
]


def test_mimxrt_maps_bus_numbers_through_the_index_tables(tmp_path):
    result = lint("mimxrt", BOARDS / "mimxrt_ok", MIMXRT_GOOD, tmp_path)
    assert result["errors"] == []
    assert result["unchecked"] == []


def test_mimxrt_bus_not_in_index_table(tmp_path):
    result = lint(
        "mimxrt",
        BOARDS / "mimxrt_ok",
        [
            per("a", "uart", {"tx": "D1"}, bus_id=0),  # entry 0 means absent
            per("b", "uart", {"tx": "D1"}, bus_id=5),
        ],
        tmp_path,
    )
    assert has(result["errors"], "'a'", "UART(0) does not exist")
    assert has(result["errors"], "'b'", "UART(5) does not exist")


def test_mimxrt_pin_not_on_the_bus_instance(tmp_path):
    result = lint(
        "mimxrt",
        BOARDS / "mimxrt_ok",
        [per("c", "uart", {"tx": "SCL", "rx": "D0"}, bus_id=1)],
        tmp_path,
    )
    assert has(
        result["errors"],
        "SCL (GPIO_AD_B1_00) has no LPUART6_TXD",
        "LPUART6_TXD is on GPIO_AD_B0_02",
    )
    assert not has(result["errors"], "GPIO_AD_B0_03")


def test_mimxrt_pad_missing_from_iomux_table(tmp_path):
    header = (
        (BOARDS / "mimxrt_ok/mpconfigboard.h")
        .read_text()
        .replace("IOMUXC_GPIO_AD_B1_15_LPSPI3_SCK", "IOMUXC_GPIO_B0_10_LPSPI3_SCK")
    )
    board = board_copy(tmp_path, "mimxrt_ok", mpconfigboard__h=header)
    result = lint("mimxrt", board, MIMXRT_GOOD, tmp_path)
    assert has(
        result["errors"],
        "IOMUX_TABLE_SPI does not route SCK (GPIO_AD_B1_15) as sck of LPSPI3",
        "it routes GPIO_B0_10",
    )
    assert not has(result["errors"], "'console'", "'sensors'")


def test_mimxrt_without_iomux_table_is_unchecked(tmp_path):
    header = "\n".join(
        ln
        for ln in (BOARDS / "mimxrt_ok/mpconfigboard.h").read_text().splitlines()
        if ln.startswith("#define MICROPY_HW_")
    )
    board = board_copy(tmp_path, "mimxrt_ok", mpconfigboard__h=header)
    result = lint("mimxrt", board, MIMXRT_GOOD, tmp_path)
    assert result["errors"] == []
    assert has(result["unchecked"], "no IOMUX_TABLE_UART")


def test_mimxrt_pad_name_values_need_no_pins_csv_row(tmp_path):
    result = lint(
        "mimxrt",
        BOARDS / "mimxrt_ok",
        [per("console", "uart", {"tx": "GPIO_AD_B0_02", "rx": "D0"}, bus_id=1)],
        tmp_path,
    )
    assert result["errors"] == []


def test_mimxrt_without_index_table_is_unchecked(tmp_path):
    board = board_copy(tmp_path, "mimxrt_ok", mpconfigboard__h="")
    result = lint("mimxrt", board, MIMXRT_GOOD[:3], tmp_path)
    assert result["errors"] == []
    assert has(result["unchecked"], "MICROPY_HW_UART_INDEX")
    assert has(result["unchecked"], "MICROPY_HW_I2C_INDEX")
    assert has(result["unchecked"], "MICROPY_HW_SPI_INDEX")


def test_mimxrt_adc_and_pwm(tmp_path):
    result = lint(
        "mimxrt",
        BOARDS / "mimxrt_ok",
        [per("v", "adc", {"pin": "PWM1"}), per("f", "pwm", {"pin": "SCL"})],
        tmp_path,
    )
    assert has(result["errors"], "PWM1 (GPIO_B0_10) has no ADC channel")
    assert has(result["errors"], "SCL (GPIO_AD_B1_00) has no FLEXPWM")


def test_mimxrt_hidden_pin_row_is_not_an_error(tmp_path):
    result = lint("mimxrt", BOARDS / "mimxrt_ok")
    assert result["errors"] == []


# ----------------------------------------------------------------------------------------
# samd
# ----------------------------------------------------------------------------------------


def test_samd_accepts_pads_that_match_the_bus_rules(tmp_path):
    result = lint(
        "samd",
        BOARDS / "samd_ok",
        [
            per("i", "i2c", {"scl": "SCL", "sda": "SDA"}, bus_id=1),
            per("s", "spi", {"sck": "D1", "mosi": "D0", "miso": "D2"}, bus_id=1),
            per("s2", "spi", {"sck": "D1", "mosi": "D3"}, bus_id=1),
            per("u", "uart", {"tx": "TX", "rx": "RX"}, bus_id=0),
            per("a", "adc", {"pin": "A0"}),
            per("p", "pwm", {"pin": "D5"}),
        ],
        tmp_path,
    )
    assert result["errors"] == []


def test_samd_default_id_without_matching_bus_warns(tmp_path):
    header = "#define MICROPY_HW_DEFAULT_I2C_ID (2)\n#define MICROPY_HW_DEFAULT_UART_ID (0)\n"
    board = board_copy(tmp_path, "samd_ok", mpconfigboard__h=header)
    periph = [
        per("i", "i2c", {"scl": "SCL", "sda": "SDA"}, bus_id=1),
        per("u", "uart", {"tx": "TX", "rx": "RX"}, bus_id=0),
    ]
    result = lint("samd", board, periph, tmp_path)
    assert result["errors"] == []
    assert has(result["warnings"], "MICROPY_HW_DEFAULT_I2C_ID is 2", "bus_id 2")
    assert not has(result["warnings"], "MICROPY_HW_DEFAULT_UART_ID")
    assert not has(result["warnings"], "MICROPY_HW_DEFAULT_SPI_ID")


def test_self_named_pins_csv_row_is_an_error_on_pad_addressed_ports(tmp_path):
    board = board_copy(tmp_path, "samd_ok", pins__csv="D0,PA16\nPA17,PA17\n")
    result = lint("samd", board)
    assert has(
        result["errors"], "pins.csv: PA17 is listed under its own pad name", "duplicate"
    )
    board = board_copy(tmp_path / "x", "rp2040_ok", pins__csv="GPIO3,GPIO3\n")
    assert has(lint("rp2", board)["errors"], "GPIO3 is listed under its own pad name")


def test_stm32_self_named_pins_csv_row_is_allowed(tmp_path):
    board = board_copy(tmp_path, "stm32_ok", pins__csv="PA2,PA2\n")
    assert not has(lint("stm32", board)["errors"], "own pad name")


def test_samd_i2c_pads_swapped(tmp_path):
    result = lint(
        "samd",
        BOARDS / "samd_ok",
        [per("i", "i2c", {"scl": "SDA", "sda": "SCL"}, bus_id=1)],
        tmp_path,
    )
    errors = result["errors"]
    assert has(errors, "SDA (PA16) is SERCOM1 pad 0; I2C scl needs pad 1")
    assert has(errors, "SCL (PA17) is SERCOM1 pad 1; I2C sda needs pad 0")


def test_samd_pin_not_on_the_sercom(tmp_path):
    result = lint(
        "samd",
        BOARDS / "samd_ok",
        [per("i", "i2c", {"scl": "SCL", "sda": "SDA"}, bus_id=4)],
        tmp_path,
    )
    assert has(
        result["errors"], "SCL (PA17) has no SERCOM4 pad for scl", "no SERCOM pins"
    )


def test_samd_pad_pair_rules_depend_on_the_series(tmp_path):
    # SERCOM1: PA18 is pad 2, PA19 is pad 3; mosi=2/sck=3 exists on SAMD21 only.
    spi = per("s", "spi", {"sck": "D7", "mosi": "D6"}, bus_id=1)
    r21 = lint("samd", BOARDS / "samd21_ok", [spi], tmp_path)
    assert r21["errors"] == []
    board = board_copy(tmp_path, "samd_ok", pins__csv="D6,PA18\nD7,PA19\n")
    r51 = lint("samd", board, [spi], tmp_path)
    assert has(r51["errors"], "mosi=2, sck=3 are not a supported pair on SAMD51")


def test_samd_spi_needs_mosi(tmp_path):
    result = lint(
        "samd",
        BOARDS / "samd_ok",
        [per("s", "spi", {"sck": "D1", "miso": "D2"}, bus_id=1)],
        tmp_path,
    )
    assert has(result["errors"], "samd SPI needs mosi")


def test_samd_uart_tx_pad_rules_depend_on_the_series(tmp_path):
    # SERCOM0 pad 2 is PA06 on the SAMD51 fixture; SAMD21 allows tx on pad 2.
    u51 = per("u", "uart", {"tx": "D6", "rx": "D5"}, bus_id=0)
    assert has(
        lint("samd", BOARDS / "samd_ok", [u51], tmp_path)["errors"],
        "D6 (PA06) is SERCOM0 pad 2; UART tx needs pad [0]",
    )
    u21 = per("u", "uart", {"tx": "D2", "rx": "D3"}, bus_id=0)
    assert lint("samd", BOARDS / "samd21_ok", [u21], tmp_path)["errors"] == []


def test_samd_uart_needs_tx(tmp_path):
    result = lint(
        "samd", BOARDS / "samd_ok", [per("u", "uart", {"rx": "RX"}, bus_id=0)], tmp_path
    )
    assert has(result["errors"], "samd UART needs tx")


def test_samd_adc_and_pwm(tmp_path):
    result = lint(
        "samd",
        BOARDS / "samd_ok",
        [per("a", "adc", {"pin": "D0"}), per("p", "pwm", {"pin": "D3"})],
        tmp_path,
    )
    assert has(result["errors"], "D0 (PA16) has no ADC channel")
    assert has(result["errors"], "D3 (PA19) has no TC/TCC signal")


def test_samd_sercom_cells_are_hex(tmp_path):
    table = lint_board.load_samd_table(MPY / "ports/samd/mcu/samd51/pin-af-table.csv")
    assert table.pads["PA16"]["sercom"]["sercom1"] == (1, 0)
    assert table.pads["PA16"]["sercom"]["sercom2"] == (3, 1)
    assert table.pads["PA04"]["sercom"]["sercom2"] == (0, 0)
    assert "tc" not in table.pads["PA04"]["sercom"]
    assert table.pads["PA02"]["adc"] is True


def test_samd_table_skips_comments_and_foreign_rows(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("# c\nPin,EIC,ADC0,SERCOM1,SERCOM2\nXX1,1,,,\nPa01,1,,10,\n")
    table = lint_board.load_samd_table(path)
    assert list(table.pads) == ["PA01"]


# ----------------------------------------------------------------------------------------
# rp2
# ----------------------------------------------------------------------------------------


def rp2_names(*numbers):
    return [f"GP{n}" for n in numbers]


def test_rp2040_accepts_valid_bus_pins(tmp_path):
    result = lint(
        "rp2",
        BOARDS / "rp2040_ok",
        [
            per("i0", "i2c", {"scl": "GP5", "sda": "GP4"}, bus_id=0),
            per("i1", "i2c", {"scl": "GP3", "sda": "GP2"}, bus_id=1),
            per("s0", "spi", {"sck": "GP2", "mosi": "GP3", "miso": "GP0"}, bus_id=0),
            per("s1", "spi", {"sck": "GP10", "mosi": "GP11", "miso": "GP8"}, bus_id=1),
            per("u0", "uart", {"tx": "GP0", "rx": "GP1"}, bus_id=0),
            per("u1", "uart", {"tx": "GP4", "rx": "GP5"}, bus_id=1),
            per("u0b", "uart", {"tx": "GP12", "rx": "GP13"}, bus_id=0),
            per("a", "adc", {"pin": "GP26"}),
            per("p", "pwm", {"pin": "GP15"}),
            per("l", "led", {"pin": "LED"}),
        ],
        tmp_path,
    )
    assert result["errors"] == []
    assert result["unchecked"] == []


def test_rp2_wrong_bus_id_for_pins(tmp_path):
    result = lint(
        "rp2",
        BOARDS / "rp2040_ok",
        [
            per("i", "i2c", {"scl": "GP3", "sda": "GP2"}, bus_id=0),
            per("s", "spi", {"sck": "GP10", "mosi": "GP11"}, bus_id=0),
            per("u", "uart", {"tx": "GP4"}, bus_id=0),
            per("z", "i2c", {"scl": "GP5", "sda": "GP4"}, bus_id=2),
        ],
        tmp_path,
    )
    errors = result["errors"]
    assert has(
        errors, "'i'", "GP3 (GPIO3) cannot be scl of I2C(0)", "IS_VALID_SCL(0, 3)"
    )
    assert has(errors, "'i'", "GP2 (GPIO2) cannot be sda of I2C(0)")
    assert has(errors, "'s'", "GP10 (GPIO10) cannot be sck of SPI(0)")
    assert has(errors, "'u'", "GP4 (GPIO4) cannot be tx of UART(0)")
    assert has(errors, "'z'", "GP5 (GPIO5) cannot be scl of I2C(2)")


def test_rp2_wrong_function_for_pad(tmp_path):
    result = lint(
        "rp2",
        BOARDS / "rp2040_ok",
        [per("s", "spi", {"sck": "GP3", "mosi": "GP2"}, bus_id=0)],
        tmp_path,
    )
    assert has(result["errors"], "GP3 (GPIO3) cannot be sck")
    assert has(result["errors"], "GP2 (GPIO2) cannot be mosi")


def test_rp2040_and_rp2350_differ_on_uart_tx_pad(tmp_path):
    uart = per("u", "uart", {"tx": "GP2", "rx": "GP3"}, bus_id=0)
    r2040 = lint("rp2", BOARDS / "rp2040_ok", [uart], tmp_path)
    assert has(r2040["errors"], "GP2 (GPIO2) cannot be tx of UART(0)")
    assert has(r2040["errors"], "GP3 (GPIO3) cannot be rx of UART(0)")
    r2350 = lint("rp2", BOARDS / "rp2350_ok", [uart], tmp_path)
    assert r2350["errors"] == []
    assert r2350["warnings"] == []  # PICO_PLATFORM read from mpconfigvariant.cmake


def test_rp2_missing_platform_warns_and_assumes_rp2040(tmp_path):
    board = board_copy(
        tmp_path, "rp2040_ok", mpconfigboard__cmake='set(PICO_BOARD "x")\n'
    )
    result = lint("rp2", board)
    assert has(result["warnings"], "no PICO_PLATFORM")


def test_rp2_adc_range_follows_the_package(tmp_path):
    adc26 = per("a", "adc", {"pin": "GP26"})
    adc29 = per("b", "adc", {"pin": "GP29"})
    adc25 = per("c", "adc", {"pin": "GP25"})
    adc40 = per("d", "adc", {"pin": "GP40"})
    r = lint("rp2", BOARDS / "rp2040_ok", [adc26, adc29, adc25], tmp_path)
    assert r["errors"] == [
        "peripheral 'c': GP25 (GPIO25) is not an ADC pin; ADC gpios are 26 to 29"
    ]
    r = lint("rp2", BOARDS / "rp2350_ok", [adc26, adc29, adc25], tmp_path)
    assert len(r["errors"]) == 1
    r = lint("rp2", BOARDS / "rp2350b_ok", [adc26, adc40], tmp_path)
    assert has(r["errors"], "'a'", "GP26 (GPIO26) is not an ADC pin", "40 to 47")
    assert not has(r["errors"], "'d'")


def test_rp2_adc_unchecked_without_sdk_headers(tmp_path):
    mpy = tmp_path / "mpy"
    shutil.copytree(MPY, mpy)
    shutil.rmtree(mpy / "lib")
    result = lint(
        "rp2", BOARDS / "rp2040_ok", [per("a", "adc", {"pin": "GP26"})], tmp_path, mpy
    )
    assert result["errors"] == []
    assert has(result["unchecked"], "platform_defs.h not in checkout")


def test_rp2_external_gpio_is_a_pin_but_not_a_bus_pad(tmp_path):
    result = lint(
        "rp2",
        BOARDS / "rp2350_ok",
        [
            per("g", "gpio", {"pin": "WL_GPIO0"}),
            per("i", "i2c", {"scl": "WL_GPIO0", "sda": "GP4"}, bus_id=0),
        ],
        tmp_path,
    )
    assert has(result["errors"], "WL_GPIO0 (EXT_GPIO0) is not a GPIO pad")
    assert not has(result["errors"], "'g'")


def test_rp2_missing_macro_source_is_an_error(tmp_path):
    mpy = tmp_path / "mpy"
    shutil.copytree(MPY, mpy)
    (mpy / "ports/rp2/machine_uart.c").unlink()
    result = lint("rp2", BOARDS / "rp2040_ok", None, tmp_path, mpy)
    assert has(result["errors"], "machine_uart.c not found")


def test_rp2_pad_name_values_need_no_pins_csv_row(tmp_path):
    result = lint(
        "rp2",
        BOARDS / "rp2040_ok",
        [per("l", "gpio", {"pin": "LED"}), per("m", "gpio", {"pin": "GPIO24"})],
        tmp_path,
    )
    assert result["errors"] == []
    result = lint(
        "rp2", BOARDS / "rp2040_ok", [per("m", "gpio", {"pin": "GPIO99"})], tmp_path
    )
    assert has(result["errors"], "pin GPIO99 is not in pins.csv")


def test_stm32_pad_name_value_needs_a_pins_csv_row(tmp_path):
    result = lint(
        "stm32", BOARDS / "stm32_ok", [per("m", "gpio", {"pin": "PA1"})], tmp_path
    )
    assert has(result["errors"], "pin PA1 is not in pins.csv")


RP2_ALL_DEFAULTS = """
#define MICROPY_HW_I2C0_SCL (9)
#define MICROPY_HW_I2C0_SDA (8)
#define MICROPY_HW_SPI0_SCK (18)
#define MICROPY_HW_SPI0_MOSI (19)
#define MICROPY_HW_SPI0_MISO (16)
"""


def rp2_no_header_board(tmp_path, header):
    return board_copy(
        tmp_path,
        "rp2040_ok",
        mpconfigboard__h=header,
        mpconfigboard__cmake='set(PICO_BOARD "none")\nset(PICO_PLATFORM "rp2040")\n',
    )


def test_rp2_no_board_header_requires_default_bus_pins(tmp_path):
    result = lint(
        "rp2", rp2_no_header_board(tmp_path, '#define MICROPY_HW_BOARD_NAME "x"\n')
    )
    assert has(result["errors"], "no MICROPY_HW_I2C0_SCL", "I2C0")
    assert has(result["errors"], "no MICROPY_HW_SPI0_SCK", "SPI0")
    assert not has(result["errors"], "I2C1")


def test_rp2_no_board_header_with_defaults_is_clean(tmp_path):
    result = lint("rp2", rp2_no_header_board(tmp_path, RP2_ALL_DEFAULTS))
    assert result["errors"] == []


def test_rp2_no_default_pins_macros_waive_the_requirement(tmp_path):
    header = "#define MICROPY_HW_I2C_NO_DEFAULT_PINS (1)\n#define MICROPY_HW_SPI_NO_DEFAULT_PINS (1)\n"
    assert lint("rp2", rp2_no_header_board(tmp_path, header))["errors"] == []


def test_rp2_board_with_header_does_not_need_default_pins(tmp_path):
    board = board_copy(tmp_path, "rp2040_ok", mpconfigboard__h="#define X 1\n")
    assert lint("rp2", board)["errors"] == []


def test_rp2_incomplete_default_pin_groups(tmp_path):
    header = (
        RP2_ALL_DEFAULTS
        + "#define MICROPY_HW_I2C1_SCL (3)\n#define MICROPY_HW_SPI1_SCK (10)\n"
    )
    result = lint("rp2", rp2_no_header_board(tmp_path, header))
    assert has(result["errors"], "MICROPY_HW_I2C1_SCL but not MICROPY_HW_I2C1_SDA")
    assert has(
        result["errors"],
        "MICROPY_HW_SPI1_SCK but not MICROPY_HW_SPI1_MOSI, MICROPY_HW_SPI1_MISO",
    )


def test_rp2_uart_defaults_need_all_four_macros(tmp_path):
    header = (
        RP2_ALL_DEFAULTS
        + "#define MICROPY_HW_UART0_TX (0)\n#define MICROPY_HW_UART0_RX (1)\n"
    )
    result = lint("rp2", rp2_no_header_board(tmp_path, header))
    assert has(
        result["errors"], "MICROPY_HW_UART0_CTS, MICROPY_HW_UART0_RTS", "machine_uart.c"
    )
    header = RP2_ALL_DEFAULTS + "".join(
        f"#define MICROPY_HW_UART0_{r} ({i})\n"
        for i, r in enumerate(("TX", "RX", "CTS", "RTS"))
    )
    assert lint("rp2", rp2_no_header_board(tmp_path / "ok", header))["errors"] == []


# ----------------------------------------------------------------------------------------
# esp32
# ----------------------------------------------------------------------------------------


def test_esp32_checks_names_only(tmp_path):
    result = lint(
        "esp32",
        BOARDS / "esp32_ok",
        [
            per("i", "i2c", {"scl": "SCL", "sda": "SDA"}, bus_id=0),
            per("g", "gpio", {"pin": "D2"}),
            per("a", "adc", {"pin": "D0"}),
        ],
        tmp_path,
    )
    assert result["errors"] == []
    assert has(
        result["unchecked"], "'i'" if False else "i: i2c pin functions not checked"
    )
    assert has(result["unchecked"], "a: adc pin functions not checked")
    assert not has(result["unchecked"], "g:")


def test_esp32_bad_port_name_in_pins_csv(tmp_path):
    board = board_copy(tmp_path, "esp32_ok", pins__csv="D0,GPIO1\nD1,PA3\n")
    assert has(lint("esp32", board)["errors"], "PA3 is not a pad of the esp32 port")


def test_esp32_gpio_above_num_gpios_is_an_error(tmp_path):
    board = board_copy(tmp_path, "esp32_ok", pins__csv="D0,GPIO54\nBAD,GPIO55\n")
    result = lint("esp32", board)
    assert has(
        result["errors"],
        "GPIO55 is not a pad of the esp32 port",
        "GPIO0 to GPIO54",
        "NUM_GPIOS = 55",
    )
    assert not has(result["errors"], "GPIO54 is not")
    board = board_copy(tmp_path / "b", "esp32_ok", pins__csv=None)
    result = lint("esp32", board, [per("g", "gpio", {"pin": "GPIO99"})], tmp_path)
    assert has(result["errors"], "GPIO99", "NUM_GPIOS = 55")


def test_esp32_range_unchecked_without_make_pins(tmp_path):
    mpy = tmp_path / "mpy"
    shutil.copytree(MPY, mpy)
    (mpy / "ports/esp32/boards/make-pins.py").unlink()
    result = lint("esp32", BOARDS / "esp32_ok", None, tmp_path, mpy)
    assert has(result["unchecked"], "esp32 pad range not checked")


def test_esp32_self_named_pins_csv_row_is_an_error(tmp_path):
    board = board_copy(tmp_path, "esp32_ok", pins__csv="D0,GPIO1\nGPIO4,GPIO4\n")
    assert has(lint("esp32", board)["errors"], "GPIO4 is listed under its own pad name")


def test_esp32_without_pins_csv_accepts_gpio_numbers(tmp_path):
    board = board_copy(tmp_path, "esp32_ok", pins__csv=None)
    result = lint(
        "esp32",
        board,
        [per("g", "gpio", {"pin": "5"}), per("h", "gpio", {"pin": "GPIO6"})],
        tmp_path,
    )
    assert result["errors"] == []
    result = lint("esp32", board, [per("g", "gpio", {"pin": "LED"})], tmp_path)
    assert has(result["errors"], "cannot be resolved without pins.csv")


# ----------------------------------------------------------------------------------------
# command line
# ----------------------------------------------------------------------------------------


def test_cli_exit_codes_and_output(tmp_path, capsys):
    pfile = tmp_path / "p.json"
    pfile.write_text(json.dumps({"peripherals": STM32_GOOD}))
    common = ["--micropython", str(MPY), "--port", "stm32", "--board-dir"]
    assert (
        lint_board.main(
            common + [str(BOARDS / "stm32_ok"), "--peripherals", str(pfile)]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert set(out) == {"errors", "warnings", "unchecked"}

    pfile.write_text(json.dumps({"peripherals": [per("x", "gpio", {"pin": "NOPE"})]}))
    report = tmp_path / "report.json"
    code = lint_board.main(
        common
        + [str(BOARDS / "stm32_ok"), "--peripherals", str(pfile), "-o", str(report)]
    )
    assert code == 1
    assert capsys.readouterr().out == ""
    assert has(json.loads(report.read_text())["errors"], "NOPE")


def test_cli_usage_errors(tmp_path, capsys):
    missing = [
        "--micropython",
        str(MPY),
        "--port",
        "stm32",
        "--board-dir",
        str(tmp_path / "no"),
    ]
    assert lint_board.main(missing) == 2
    assert "board directory" in capsys.readouterr().err
    assert (
        lint_board.main(
            [
                "--micropython",
                str(tmp_path),
                "--port",
                "samd",
                "--board-dir",
                str(tmp_path),
            ]
        )
        == 2
    )
    with pytest.raises(SystemExit) as exc:
        lint_board.main(
            ["--micropython", str(MPY), "--port", "unix", "--board-dir", str(tmp_path)]
        )
    assert exc.value.code == 2


# ----------------------------------------------------------------------------------------
# real MicroPython checkout
# ----------------------------------------------------------------------------------------

REAL_SEEDS = [
    ("stm32", "NUCLEO_F767ZI"),
    ("rp2", "RPI_PICO"),
    ("rp2", "RPI_PICO2"),
    ("rp2", "RPI_PICO_W"),
    ("rp2", "RPI_PICO2_W"),
    ("mimxrt", "TEENSY40"),
    ("samd", "ADAFRUIT_ITSYBITSY_M4_EXPRESS"),
    ("esp32", "SEEED_XIAO_ESP32C3"),
    ("esp32", "ESP32_GENERIC"),
]


def real_board(port, board):
    path = REAL_MPY / "ports" / port / "boards" / board
    if not path.is_dir():
        pytest.skip(f"{board} not in checkout")
    return path


def board_name_for(board_dir, port_name):
    """First board pin name that maps to the port name."""
    mapping, _ = lint_board.read_pins_csv(board_dir / "pins.csv", lint_board.Report())
    for name, target in mapping.items():
        if target == port_name:
            return name
    pytest.skip(f"{port_name} has no board name in {board_dir.name}")


@needs_real
@pytest.mark.parametrize("port,board", REAL_SEEDS)
def test_real_seed_boards_have_no_errors(port, board):
    result = lint_board.lint_board(REAL_MPY, port, real_board(port, board))
    assert result["errors"] == []


@needs_real
def test_real_stm32_nucleo_peripherals(tmp_path):
    board = real_board("stm32", "NUCLEO_F767ZI")
    n = lambda p: board_name_for(board, p)
    good = [
        per("i", "i2c", {"scl": n("PB8"), "sda": n("PB9")}, bus_id=1),
        per(
            "s", "spi", {"sck": n("PB3"), "mosi": n("PB5"), "miso": n("PB4")}, bus_id=3
        ),
        per("u", "uart", {"tx": n("PD5"), "rx": n("PD6")}, bus_id=2),
        per("a", "adc", {"pin": n("PA3")}),
    ]
    assert (
        lint_board.lint_board(REAL_MPY, "stm32", board, _write(tmp_path, good))[
            "errors"
        ]
        == []
    )
    bad = [
        per("u", "uart", {"tx": n("PD6"), "rx": n("PD5")}, bus_id=2),
        per("i", "i2c", {"scl": n("PF1"), "sda": n("PF0")}, bus_id=3),
    ]
    errors = lint_board.lint_board(REAL_MPY, "stm32", board, _write(tmp_path, bad))[
        "errors"
    ]
    assert has(errors, "'u'", "(PD6) has no")
    assert has(errors, "'i'", "(PF1) has no I2C3_SCL")


def _write(tmp_path, peripherals):
    path = tmp_path / "real_peripherals.json"
    path.write_text(json.dumps({"peripherals": peripherals}))
    return path


@needs_real
def test_real_rp2_pico_and_pico2(tmp_path):
    pico = real_board("rp2", "RPI_PICO")
    pico2 = real_board("rp2", "RPI_PICO2")
    good = [
        per("i", "i2c", {"scl": "GP5", "sda": "GP4"}, bus_id=0),
        per("s", "spi", {"sck": "GP18", "mosi": "GP19", "miso": "GP16"}, bus_id=0),
        per("u", "uart", {"tx": "GP0", "rx": "GP1"}, bus_id=0),
        per("a", "adc", {"pin": "GP26"}),
    ]
    assert (
        lint_board.lint_board(REAL_MPY, "rp2", pico, _write(tmp_path, good))["errors"]
        == []
    )
    wrong_bus = [per("i", "i2c", {"scl": "GP5", "sda": "GP4"}, bus_id=1)]
    errors = lint_board.lint_board(REAL_MPY, "rp2", pico, _write(tmp_path, wrong_bus))[
        "errors"
    ]
    assert has(errors, "GP5 (GPIO5) cannot be scl of I2C(1)")
    uart = [per("u", "uart", {"tx": "GP2", "rx": "GP3"}, bus_id=0)]
    assert lint_board.lint_board(REAL_MPY, "rp2", pico, _write(tmp_path, uart))[
        "errors"
    ]
    assert (
        lint_board.lint_board(REAL_MPY, "rp2", pico2, _write(tmp_path, uart))["errors"]
        == []
    )


@needs_real
def test_real_mimxrt_teensy40(tmp_path):
    board = real_board("mimxrt", "TEENSY40")
    n = lambda p: board_name_for(board, p)
    # Logical UART 1 is LPUART6 on this board; logical I2C 1 is LPI2C1.
    good = [
        per(
            "u", "uart", {"tx": n("GPIO_AD_B0_02"), "rx": n("GPIO_AD_B0_03")}, bus_id=1
        ),
        per(
            "i", "i2c", {"scl": n("GPIO_AD_B1_00"), "sda": n("GPIO_AD_B1_01")}, bus_id=0
        ),
    ]
    assert (
        lint_board.lint_board(REAL_MPY, "mimxrt", board, _write(tmp_path, good))[
            "errors"
        ]
        == []
    )
    bad = [
        per("u", "uart", {"tx": n("GPIO_AD_B0_02"), "rx": n("GPIO_AD_B0_03")}, bus_id=2)
    ]
    errors = lint_board.lint_board(REAL_MPY, "mimxrt", board, _write(tmp_path, bad))[
        "errors"
    ]
    assert has(errors, "no LPUART4_TXD") or has(errors, "has no LPUART")


@needs_real
def test_real_samd_itsybitsy_m4(tmp_path):
    board = real_board("samd", "ADAFRUIT_ITSYBITSY_M4_EXPRESS")
    n = lambda p: board_name_for(board, p)
    good = [per("i", "i2c", {"scl": n("PA13"), "sda": n("PA12")}, bus_id=2)]
    assert (
        lint_board.lint_board(REAL_MPY, "samd", board, _write(tmp_path, good))["errors"]
        == []
    )
    swapped = [per("i", "i2c", {"scl": n("PA12"), "sda": n("PA13")}, bus_id=2)]
    errors = lint_board.lint_board(REAL_MPY, "samd", board, _write(tmp_path, swapped))[
        "errors"
    ]
    assert has(errors, "(PA12) is SERCOM2 pad 0; I2C scl needs pad 1")


@needs_real
def test_real_esp32_board_with_pins_csv_marks_buses_unchecked(tmp_path):
    board = real_board("esp32", "SEEED_XIAO_ESP32C3")
    name = board_name_for(board, "GPIO4")
    result = lint_board.lint_board(
        REAL_MPY,
        "esp32",
        board,
        _write(tmp_path, [per("u", "uart", {"tx": name}, bus_id=1)]),
    )
    assert result["errors"] == []
    assert has(result["unchecked"], "uart pin functions not checked")
