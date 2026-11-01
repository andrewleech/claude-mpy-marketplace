import json
import subprocess
import sys

import pytest

import parse_netlist
import resolve_pinmap
import validate_facts

MCU = {
    "part": "STM32F767ZIT6",
    "port": "stm32",
    "mcu_ref": "U1",
    "package": "LQFP144",
    "series": "f7",
    "seed_board": "NUCLEO_F767ZI",
    "source": "user-confirmed",
}

PERIPHERALS = {
    "peripherals": [
        {"name": "led", "kind": "led", "pins": {"pin": "LED_GREEN"}, "active_high": True, "source": "user-confirmed"},
        {"name": "button", "kind": "gpio", "direction": "in", "pull": "up", "pins": {"pin": "USER_BTN"}, "source": "script"},
        {
            "name": "sensors", "kind": "i2c", "bus_id": 2, "freq": 400000, "source": "inferred",
            "pins": {"scl": "I2C2_SCL", "sda": "I2C2_SDA"},
            "devices": [{"name": "imu", "addr": "0x68", "part": "ICM-42688"}],
        },
        {
            "name": "flash", "kind": "spi", "bus_id": 2, "baudrate": 1000000, "source": "script",
            "pins": {"sck": "SPI2_SCK", "mosi": "SPI2_MOSI", "miso": "SPI2_MISO"},
            "devices": [{"name": "nor", "cs": "FLASH_CS", "part": "W25Q128"}],
        },
        {"name": "console", "kind": "uart", "bus_id": 4, "baudrate": 115200, "source": "script", "pins": {"tx": "U4_TX", "rx": "U4_RX"}},
        {"name": "vbat", "kind": "adc", "pins": {"pin": "P_3V3_SENSE"}, "source": "script"},
        {"name": "fan", "kind": "pwm", "freq": 25000, "pins": {"pin": "FAN_PWM"}, "source": "script"},
    ]
}  # fmt: skip


@pytest.fixture
def facts(tmp_path, fixtures):
    d = tmp_path / "facts"
    d.mkdir()
    nets = parse_netlist.parse_file(fixtures / "stm32_board_kicad.net")
    (d / "nets.json").write_text(json.dumps(nets))
    errors = []
    table = resolve_pinmap.table_from_csv(fixtures / "stm32_pin_table.csv", errors)
    pinmap = resolve_pinmap.resolve(nets, "U1", "stm32", table)
    (d / "pinmap.json").write_text(json.dumps(pinmap))
    (d / "mcu.json").write_text(json.dumps(MCU))
    (d / "peripherals.json").write_text(json.dumps(PERIPHERALS))
    return d


def write(d, name, obj):
    (d / name).write_text(json.dumps(obj))


def test_valid_facts_all_stages(facts):
    for stage in ("mcu", "pinmap", "peripherals", "all"):
        rep = validate_facts.validate(facts, stage)
        assert rep["errors"] == [], stage
        assert rep["ok"] is True


def test_cli_exit_codes(facts, capsys):
    assert validate_facts.main(["--facts", str(facts)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    (facts / "mcu.json").unlink()
    assert validate_facts.main(["--facts", str(facts), "--stage", "mcu"]) == 1
    assert "mcu.json: file is missing" in json.loads(capsys.readouterr().out)["errors"]


def test_mcu_missing_keys_and_source(facts):
    bad = {k: v for k, v in MCU.items() if k not in ("seed_board", "source")}
    write(facts, "mcu.json", bad)
    errors = validate_facts.validate(facts, "mcu")["errors"]
    assert "mcu.json: missing required key 'seed_board'" in errors
    assert "mcu.json: missing required key 'source'" in errors


def test_empty_seed_board_warns_at_mcu_stage_and_fails_at_all(facts):
    write(facts, "mcu.json", {**MCU, "seed_board": ""})
    rep = validate_facts.validate(facts, "mcu")
    assert rep["ok"] is True
    assert any("'seed_board' is empty" in w for w in rep["warnings"])
    rep = validate_facts.validate(facts, "all")
    assert rep["ok"] is False
    assert "mcu.json: key 'seed_board' is empty" in rep["errors"]


def test_mcu_bad_source_and_port(facts):
    write(facts, "mcu.json", {**MCU, "source": "guess", "port": "nrf"})
    errors = validate_facts.validate(facts, "mcu")["errors"]
    assert any("source 'guess' is not one of" in e for e in errors)
    assert any("port 'nrf' is not one of" in e for e in errors)


def test_mcu_ref_must_exist_in_nets(facts):
    write(facts, "mcu.json", {**MCU, "mcu_ref": "U7"})
    errors = validate_facts.validate(facts, "mcu")["errors"]
    assert "mcu.json: mcu_ref 'U7' is not in nets.json" in errors


def test_mcu_without_series_warns(facts):
    bad = {k: v for k, v in MCU.items() if k != "series"}
    write(facts, "mcu.json", bad)
    rep = validate_facts.validate(facts, "mcu")
    assert rep["ok"] is True
    assert any("no 'series'" in w for w in rep["warnings"])


def test_pinmap_failed_status_is_error(facts):
    pm = json.loads((facts / "pinmap.json").read_text())
    pm["status"] = "fail"
    write(facts, "pinmap.json", pm)
    errors = validate_facts.validate(facts, "pinmap")["errors"]
    assert any("the pin gate has not passed" in e for e in errors)


def test_pinmap_port_mismatch_with_mcu(facts):
    pm = json.loads((facts / "pinmap.json").read_text())
    pm["port"] = "rp2"
    write(facts, "pinmap.json", pm)
    errors = validate_facts.validate(facts, "all")["errors"]
    assert any("port 'rp2' differs from mcu.json 'stm32'" in e for e in errors)


def test_pinmap_duplicate_board_pin_names(facts):
    pm = json.loads((facts / "pinmap.json").read_text())
    pm["pins"].append(
        {
            "package_pin": "999",
            "port_name": "PB2",
            "net": "/other/led_green",
            "anchor": False,
        }
    )
    write(facts, "pinmap.json", pm)
    errors = validate_facts.validate(facts, "pinmap")["errors"]
    assert any("duplicate board pin name LED_GREEN" in e for e in errors)


def test_pinmap_duplicate_package_pin_and_bad_port_name(facts):
    pm = json.loads((facts / "pinmap.json").read_text())
    pm["pins"].append(
        {"package_pin": "34", "port_name": "GPIO1", "net": "X", "anchor": False}
    )
    write(facts, "pinmap.json", pm)
    errors = validate_facts.validate(facts, "pinmap")["errors"]
    assert any("duplicate package pin 34" in e for e in errors)
    assert any("'GPIO1' is not a valid stm32 port name" in e for e in errors)


def test_pinmap_required_for_all_when_nets_exist(facts):
    (facts / "pinmap.json").unlink()
    assert (
        "pinmap.json: file is missing"
        in validate_facts.validate(facts, "all")["errors"]
    )


def test_pinmap_optional_for_all_without_nets(facts):
    (facts / "pinmap.json").unlink()
    (facts / "nets.json").unlink()
    assert validate_facts.validate(facts, "all")["errors"] == []


def test_unknown_kind(facts):
    doc = json.loads(json.dumps(PERIPHERALS))
    doc["peripherals"][0]["kind"] = "servo"
    write(facts, "peripherals.json", doc)
    errors = validate_facts.validate(facts, "peripherals")["errors"]
    assert any("unknown kind 'servo'" in e for e in errors)


def test_peripheral_missing_source(facts):
    doc = json.loads(json.dumps(PERIPHERALS))
    del doc["peripherals"][5]["source"]
    write(facts, "peripherals.json", doc)
    errors = validate_facts.validate(facts, "peripherals")["errors"]
    assert "peripherals.json[vbat]: missing required key 'source'" in errors


def test_peripheral_pin_roles_and_bus_id(facts):
    doc = {
        "peripherals": [
            {"name": "i", "kind": "i2c", "pins": {"scl": "A"}, "source": "script"},
            {"name": "u", "kind": "uart", "bus_id": 1, "pins": {}, "source": "script"},
            {
                "name": "s",
                "kind": "spi",
                "bus_id": 1,
                "pins": {"sck": "S", "cs": "C"},
                "source": "script",
            },
        ]
    }
    write(facts, "peripherals.json", doc)
    errors = validate_facts.validate(facts, "peripherals")["errors"]
    assert "peripherals.json[i]: i2c needs pin role 'sda'" in errors
    assert "peripherals.json[i]: i2c needs integer 'bus_id'" in errors
    assert "peripherals.json[u]: uart needs at least one of: tx, rx" in errors
    assert "peripherals.json[s]: spi needs at least one of: mosi, miso" in errors
    assert "peripherals.json[s]: unknown pin role 'cs' for kind spi" in errors


def test_duplicate_peripheral_and_device_names(facts):
    doc = json.loads(json.dumps(PERIPHERALS))
    doc["peripherals"].append(dict(doc["peripherals"][0]))
    doc["peripherals"][2]["devices"].append({"name": "imu", "addr": "0x69"})
    write(facts, "peripherals.json", doc)
    errors = validate_facts.validate(facts, "peripherals")["errors"]
    assert "peripherals.json[led]: duplicate peripheral name" in errors
    assert "peripherals.json[sensors]: duplicate device name 'imu'" in errors


def test_device_fields(facts):
    doc = json.loads(json.dumps(PERIPHERALS))
    doc["peripherals"][2]["devices"] = [{"name": "x", "addr": "zz"}, {"name": "y"}]
    doc["peripherals"][3]["devices"] = [{"name": "nor"}]
    write(facts, "peripherals.json", doc)
    errors = validate_facts.validate(facts, "peripherals")["errors"]
    assert "peripherals.json[sensors]: device 'x' addr 'zz' is not a number" in errors
    assert "peripherals.json[sensors]: device 'y' lacks 'addr'" in errors
    assert "peripherals.json[flash]: device 'nor' lacks 'cs'" in errors


def test_gpio_direction_and_pull(facts):
    doc = {
        "peripherals": [
            {
                "name": "b",
                "kind": "gpio",
                "pins": {"pin": "X"},
                "pull": "middle",
                "source": "script",
            }
        ]
    }
    write(facts, "peripherals.json", doc)
    errors = validate_facts.validate(facts, "peripherals")["errors"]
    assert any("gpio needs 'direction'" in e for e in errors)
    assert any("pull 'middle' is not 'up', 'down' or 'none'" in e for e in errors)


def test_gpio_pull_none_is_accepted(facts):
    doc = json.loads(json.dumps(PERIPHERALS))
    doc["peripherals"][1]["pull"] = "none"
    write(facts, "peripherals.json", doc)
    assert validate_facts.validate(facts, "peripherals")["errors"] == []


def test_shared_pin_is_warning_only(facts):
    doc = json.loads(json.dumps(PERIPHERALS))
    doc["peripherals"][1]["pins"]["pin"] = "LED_GREEN"
    write(facts, "peripherals.json", doc)
    rep = validate_facts.validate(facts, "peripherals")
    assert rep["ok"] is True
    assert any("pin LED_GREEN is also used by 'led'" in w for w in rep["warnings"])


def test_invalid_json_reported(facts):
    (facts / "mcu.json").write_text("{not json")
    errors = validate_facts.validate(facts, "mcu")["errors"]
    assert any(e.startswith("mcu.json: invalid JSON") for e in errors)


def test_missing_facts_dir(tmp_path):
    rep = validate_facts.validate(tmp_path / "nope", "all")
    assert rep["ok"] is False


def test_help_runs_as_script(scripts_dir):
    r = subprocess.run(
        [sys.executable, str(scripts_dir / "validate_facts.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "--stage" in r.stdout
