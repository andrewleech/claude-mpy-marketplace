import json

import pytest

import common


@pytest.mark.parametrize(
    "name",
    [
        "Net-(U1-PA3)",
        "/Net-(R5-Pad1)",
        "/sheet/Net-(R5-Pad1)",
        "unconnected-(U1-PA2)",
        "NetU1_5",
        "NetR12_A1",
        "N$12",
        "",
    ],
)
def test_unnamed(name):
    assert common.is_unnamed_net(name)


@pytest.mark.parametrize(
    "name", ["PA3", "/PA4", "NetworkLED", "NetSPI1_CS", "GND", "/power/3V3_SENSE"]
)
def test_named(name):
    assert not common.is_unnamed_net(name)


@pytest.mark.parametrize(
    "net,expected",
    [
        ("PA3", "PA3"),
        ("/PA4", "PA4"),
        ("/sheet/led-green", "LED_GREEN"),
        ("/power/3V3_SENSE", "P_3V3_SENSE"),
        ("I2C2.SCL", "I2C2_SCL"),
        ("+3V3", "_3V3"),
    ],
)
def test_board_pin_name(net, expected):
    assert common.board_pin_name(net) == expected


def test_strip_sheet():
    assert common.strip_sheet("/a/b/NAME") == "NAME"
    assert common.strip_sheet("NAME") == "NAME"
    assert common.strip_sheet("/sheet/Net-(U1-PA3/ADC)") == "Net-(U1-PA3/ADC)"


@pytest.mark.parametrize(
    "port,good,bad",
    [
        ("stm32", ["PA3", "PK15", "PB10"], ["PL1", "PA", "GPIO3", "PA123"]),
        ("samd", ["PA00", "PD21"], ["PA0", "PE01"]),
        ("rp2", ["GPIO0", "GPIO29"], ["GP0", "PA3"]),
        ("esp32", ["GPIO48"], ["IO4"]),
        (
            "mimxrt",
            ["GPIO_AD_B0_03", "GPIO_EMC_41", "GPIO_SD_B1_00"],
            ["PA3", "GPIO_AD_B0_0"],
        ),
    ],
)
def test_port_name_pattern(port, good, bad):
    pat = common.port_name_pattern(port)
    assert all(pat.match(g) and pat.fullmatch(g) for g in good)
    assert not any(pat.match(b) for b in bad)


def test_port_name_pattern_extra_names():
    pat = common.port_name_pattern("mimxrt", ["WAKEUP"])
    assert pat.match("WAKEUP")
    assert not common.port_name_pattern("mimxrt").match("WAKEUP")


def test_find_port_name():
    assert common.find_port_name("PA3-WKUP", "stm32") == "PA3"
    assert common.find_port_name("PA3/WKUP", "stm32") == "PA3"
    assert common.find_port_name("VSS", "stm32") is None
    assert common.find_port_name(None, "stm32") is None


def test_unknown_port():
    with pytest.raises(ValueError):
        common.port_name_pattern("nrf")


def test_load_port_names(fixtures):
    stm = common.load_port_names("stm32", fixtures / "stm32_af.csv")
    assert {"PA3", "PB10", "PE2"} <= stm
    assert "" not in stm
    rt = common.load_port_names("mimxrt", fixtures / "mimxrt_af.csv")
    assert "GPIO_AD_B0_03" in rt and "WAKEUP" in rt


def test_dump_json_file_and_stdout(tmp_path, capsys):
    common.dump_json({"a": 1}, tmp_path / "sub" / "x.json")
    assert json.loads((tmp_path / "sub" / "x.json").read_text()) == {"a": 1}
    common.dump_json({"b": 2}, None)
    assert json.loads(capsys.readouterr().out) == {"b": 2}


def test_gpio_limit_reads_make_pins(fixtures):
    mpy = fixtures / "lint_mpy"
    assert common.gpio_limit("esp32", mpy) == 55
    assert common.gpio_limit("rp2", mpy) is None
    assert common.gpio_limit("esp32", None) is None
    assert common.gpio_limit("esp32", fixtures) is None


def test_gpio_range_error():
    assert common.gpio_range_error("esp32", "GPIO54", 55) is None
    assert common.gpio_range_error("esp32", "GPIO99", None) is None
    err = common.gpio_range_error("esp32", "GPIO55", 55)
    assert err == (
        "'GPIO55' is not a valid esp32 port name: make-pins.py accepts GPIO0 to GPIO54 "
        "(NUM_GPIOS = 55)"
    )


def test_natural_key():
    assert sorted(["A10", "A2", "10", "9"], key=common.natural_key)[:2] == ["9", "10"]
    assert sorted(["34", "100", "9"], key=common.natural_key) == ["9", "34", "100"]
