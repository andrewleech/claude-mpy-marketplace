"""Tests for gen_hardware.py: generated text per port, project edits, refusal rules, unix run."""

import ast
import copy
import json
import os
import shutil
import subprocess
from pathlib import Path

import gen_hardware
import pytest
from gen_hardware import Call

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROJECT_FIXTURE = FIXTURES / "gen_project"
BOARD = "GENBOARD"

UNIX_MPY = Path("/home/corona/micropython/ports/unix/build-standard/micropython")
STDLIB_CANDIDATES = [
    Path("/home/corona/micropython/lib/micropython-lib/python-stdlib"),
    *sorted(
        Path("/tmp").glob(
            "mpy_app_template_test_*/src/libs/micropython-lib/python-stdlib"
        )
    ),
]
MOCK_CANDIDATES = [
    Path("/tmp/mm"),
    *sorted(
        Path("/tmp").glob("mpy_app_template_test_*/src/libs/micropython-mock-machine")
    ),
]
EXTMOD = Path("/home/corona/micropython/extmod")

FULL = {
    "peripherals": [
        {
            "name": "led",
            "kind": "led",
            "pins": {"pin": "LED_GREEN"},
            "active_high": True,
        },
        {
            "name": "button",
            "kind": "gpio",
            "direction": "in",
            "pull": "up",
            "pins": {"pin": "BTN"},
        },
        {
            "name": "reset_out",
            "kind": "gpio",
            "direction": "out",
            "value": 1,
            "pins": {"pin": "RESET_OUT"},
        },
        {
            "name": "sensors",
            "kind": "i2c",
            "bus_id": 1,
            "freq": 400000,
            "pins": {"scl": "I2C1_SCL", "sda": "I2C1_SDA"},
            "devices": [{"name": "imu", "addr": "0x68", "part": "ICM-42688"}],
        },
        {
            "name": "flash",
            "kind": "spi",
            "bus_id": 2,
            "baudrate": 1000000,
            "pins": {"sck": "SPI2_SCK", "mosi": "SPI2_MOSI", "miso": "SPI2_MISO"},
            "devices": [{"name": "nor", "cs": "FLASH_CS", "part": "W25Q128"}],
        },
        {
            "name": "console",
            "kind": "uart",
            "bus_id": 4,
            "baudrate": 115200,
            "pins": {"tx": "U4_TX", "rx": "U4_RX"},
        },
        {"name": "vbat", "kind": "adc", "pins": {"pin": "VBAT"}},
        {"name": "fan", "kind": "pwm", "freq": 25000, "pins": {"pin": "FAN"}},
    ]
}

PIN_FORM_PORTS = ("rp2", "esp32", "samd")
FIXED_FORM_PORTS = ("stm32", "mimxrt")
ALL_PORTS = PIN_FORM_PORTS + FIXED_FORM_PORTS


# ----------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------


def git(project, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t"}
    env |= {"GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(
        ["git", "-C", str(project), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def make_project(tmp_path, port="stm32", commit=True):
    """Copy the template files into a project; esp32 gets a pins.csv with GPIO numbers."""
    project = tmp_path / "project"
    shutil.copytree(PROJECT_FIXTURE, project)
    # The fixture keeps a suffix so pytest does not collect the template's test file.
    blink = project / "src/firmware/test/test_blink.py"
    (project / "src/firmware/test/test_blink.py.fixture").rename(blink)
    if port == "esp32":
        pins = project / "src/system" / BOARD / "pins.csv"
        rows = [line for line in pins.read_text().splitlines() if "," in line]
        pins.write_text(
            "".join(f"{r.split(',')[0]},GPIO{i}\n" for i, r in enumerate(rows))
        )
    if commit:
        git(project, "init", "-q")
        git(project, "add", "-A")
        git(project, "commit", "-qm", "base")
    return project


def run(project, port, design, *extra, board=BOARD):
    pfile = project.parent / "peripherals.json"
    pfile.write_text(json.dumps(design))
    argv = [
        "--project",
        str(project),
        "--port",
        port,
        "--peripherals",
        str(pfile),
        "--board-name",
        board,
        *extra,
    ]
    return gen_hardware.main(argv)


def generated(project):
    app = project / "src/firmware/application"
    return {
        "config": (app / "device_config.py").read_text(),
        "hardware": (app / "hardware.py").read_text(),
        "test": (project / "src/firmware/test/test_hardware.py").read_text(),
        "device": (app / "device.py").read_text(),
    }


def design_of(*peripherals):
    return {"peripherals": [copy.deepcopy(p) for p in peripherals]}


def by_name(*names):
    return design_of(*[p for p in FULL["peripherals"] if p["name"] in names])


def calls(source, func):
    return [
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == func
    ]


def keywords(call):
    return [k.arg for k in call.keywords]


def constants(source):
    """Module level NAME = literal assignments of a Python file."""
    out = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


# ----------------------------------------------------------------------------------------
# rendering helpers
# ----------------------------------------------------------------------------------------


def test_call_renders_on_one_line_when_it_fits():
    call = Call(
        "Pin", [(None, "device_config.X_PIN"), (None, "Pin.OUT"), ("value", "1")]
    )
    assert call.render(4, "a=", ",") == [
        "    a=Pin(device_config.X_PIN, Pin.OUT, value=1),"
    ]


def test_call_wraps_at_the_line_length_boundary():
    inner = Call("Pin", [(None, "x" * 10)])
    # "f(" + key + "=" + "Pin(xxxxxxxxxx)" + ")" is len(key) + 19 characters.
    fits = Call("f", [("k" * 80, inner)]).render(0)
    assert len(fits) == 1 and len(fits[0]) == gen_hardware.LINE_LENGTH
    wraps = Call("f", [("k" * 81, inner)]).render(0)
    assert wraps[0] == "f("
    assert wraps[1] == "    " + "k" * 81 + "=Pin("
    assert wraps[2] == "        xxxxxxxxxx,"
    assert wraps[-1] == ")"


def test_nested_calls_wrap_inside_out():
    pin = Call("Pin", [(None, "device_config." + "A" * 40)])
    call = Call("I2C", [(None, "id"), ("scl", pin), ("sda", pin)])
    lines = call.render(4, "sensors=", ",")
    assert lines[0] == "    sensors=I2C("
    assert lines[1] == "        id,"
    assert lines[2] == "        scl=Pin(device_config." + "A" * 40 + "),"
    assert lines[-1] == "    ),"
    assert all(len(line) <= gen_hardware.LINE_LENGTH for line in lines)


def test_def_lines_wrap_with_trailing_comma():
    short = gen_hardware.def_lines(4, "__init__", ["self", "a"])
    assert short == ["    def __init__(self, a):"]
    params = ["self"] + [f"parameter_number_{i}" for i in range(8)]
    lines = gen_hardware.def_lines(4, "__init__", params)
    assert lines[0] == "    def __init__("
    assert lines[1] == "        self,"
    assert lines[-2] == "        parameter_number_7,"
    assert lines[-1] == "    ):"


# ----------------------------------------------------------------------------------------
# constructor forms per port
# ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("port", ALL_PORTS)
def test_generated_files_compile_for_every_port(tmp_path, port):
    project = make_project(tmp_path, port)
    assert run(project, port, FULL) == 0
    files = generated(project)
    for name, text in files.items():
        compile(text, name, "exec")


@pytest.mark.parametrize("port", PIN_FORM_PORTS)
def test_pin_argument_ports_pass_the_pins_to_the_bus_constructors(tmp_path, port):
    project = make_project(tmp_path, port)
    assert run(project, port, FULL) == 0
    hw = generated(project)["hardware"]
    (i2c,) = calls(hw, "I2C")
    (spi,) = calls(hw, "SPI")
    (uart,) = calls(hw, "UART")
    assert len(i2c.args) == 1 and keywords(i2c) == ["scl", "sda", "freq"]
    assert len(spi.args) == 1 and keywords(spi) == ["baudrate", "sck", "mosi", "miso"]
    assert len(uart.args) == 1 and keywords(uart) == ["baudrate", "tx", "rx"]
    for call in (i2c, spi, uart):
        for kw in call.keywords:
            if kw.arg in ("scl", "sda", "sck", "mosi", "miso", "tx", "rx"):
                assert isinstance(kw.value, ast.Call) and kw.value.func.id == "Pin"
    cfg = constants(generated(project)["config"])
    assert {"SENSORS_SCL_PIN", "FLASH_MISO_PIN", "CONSOLE_TX_PIN"} <= set(cfg)


@pytest.mark.parametrize("port", FIXED_FORM_PORTS)
def test_fixed_pin_ports_pass_only_id_and_rate(tmp_path, port):
    project = make_project(tmp_path, port)
    assert run(project, port, FULL) == 0
    files = generated(project)
    (i2c,) = calls(files["hardware"], "I2C")
    (spi,) = calls(files["hardware"], "SPI")
    (uart,) = calls(files["hardware"], "UART")
    assert (len(i2c.args), keywords(i2c)) == (1, ["freq"])
    assert (len(spi.args), keywords(spi)) == (1, ["baudrate"])
    assert (len(uart.args), keywords(uart)) == (1, ["baudrate"])
    cfg = constants(files["config"])
    assert not any(
        k.startswith(("SENSORS_S", "FLASH_SCK", "CONSOLE_TX"))
        for k in cfg
        if "PIN" in k
    )
    assert cfg["SENSORS_ID"] == 1 and cfg["FLASH_BAUDRATE"] == 1000000


@pytest.mark.parametrize("port", ALL_PORTS)
def test_single_pin_kinds_take_the_same_form_on_every_port(tmp_path, port):
    project = make_project(tmp_path, port)
    assert run(project, port, FULL) == 0
    hw = generated(project)["hardware"]
    (adc,) = calls(hw, "ADC")
    assert len(adc.args) == 1 and adc.args[0].func.id == "Pin" and not adc.keywords
    (pwm,) = calls(hw, "PWM")
    assert keywords(pwm) == ["freq", "duty_u16"] and pwm.args[0].func.id == "Pin"
    pins = {ast.unparse(c) for c in calls(hw, "Pin")}
    assert "Pin(device_config.BUTTON_PIN, Pin.IN, Pin.PULL_UP)" in pins
    assert "Pin(device_config.RESET_OUT_PIN, Pin.OUT, value=1)" in pins
    assert "Pin(device_config.NOR_CS_PIN, Pin.OUT, value=1)" in pins
    assert "Pin(device_config.LED_PIN, Pin.OUT, value=0)" in pins


def test_config_constants_for_the_full_design(tmp_path):
    project = make_project(tmp_path, "rp2")
    assert run(project, "rp2", FULL) == 0
    cfg = constants(generated(project)["config"])
    assert cfg["LED_PIN"] == "LED_GREEN"
    assert cfg["LED_ON_TIME"] == 1.0 and cfg["LED_OFF_TIME"] == 1.0
    assert cfg["AUTORUN"] is True
    assert cfg["SENSORS_ID"] == 1 and cfg["SENSORS_FREQ"] == 400000
    assert cfg["SENSORS_SCL_PIN"] == "I2C1_SCL" and cfg["SENSORS_SDA_PIN"] == "I2C1_SDA"
    assert cfg["IMU_ADDR"] == 0x68
    assert cfg["NOR_CS_PIN"] == "FLASH_CS"
    assert cfg["CONSOLE_ID"] == 4 and cfg["CONSOLE_BAUDRATE"] == 115200
    assert cfg["VBAT_PIN"] == "VBAT"
    assert cfg["FAN_PIN"] == "FAN" and cfg["FAN_FREQ"] == 25000
    assert generated(project)["config"].startswith('"""\nApplication settings')
    assert "# Logging threshold applied in main.py." in generated(project)["config"]
    assert "IMU_ADDR = 0x68  # ICM-42688" in generated(project)["config"]


def test_bus_defaults_apply_when_rates_are_missing(tmp_path):
    design = design_of(
        {
            "name": "i",
            "kind": "i2c",
            "bus_id": 0,
            "pins": {"scl": "I2C1_SCL", "sda": "I2C1_SDA"},
        },
        {
            "name": "s",
            "kind": "spi",
            "bus_id": 0,
            "pins": {"sck": "SPI2_SCK", "mosi": "SPI2_MOSI"},
        },
        {"name": "u", "kind": "uart", "bus_id": 0, "pins": {"tx": "U4_TX"}},
        {"name": "p", "kind": "pwm", "pins": {"pin": "FAN"}},
    )
    project = make_project(tmp_path, "rp2")
    assert run(project, "rp2", design) == 0
    cfg = constants(generated(project)["config"])
    assert (cfg["I_FREQ"], cfg["S_BAUDRATE"], cfg["U_BAUDRATE"], cfg["P_FREQ"]) == (
        400000,
        1000000,
        115200,
        1000,
    )
    hw = generated(project)["hardware"]
    (spi,) = calls(hw, "SPI")
    assert keywords(spi) == ["baudrate", "sck", "mosi"]  # no miso pin, none passed
    (uart,) = calls(hw, "UART")
    assert keywords(uart) == ["baudrate", "tx"]


def test_unsupported_kind_for_a_port_exits_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(gen_hardware.SUPPORTED_KINDS, "samd", {"led", "gpio"})
    project = make_project(tmp_path, "samd")
    assert run(project, "samd", by_name("vbat")) == 1
    assert "kind adc is not generated for port samd" in capsys.readouterr().err
    assert git(project, "status", "--porcelain").stdout == ""


# ----------------------------------------------------------------------------------------
# esp32 pin numbers
# ----------------------------------------------------------------------------------------


def test_esp32_pins_are_gpio_numbers_from_the_board_pins_csv(tmp_path):
    project = make_project(tmp_path, "esp32")
    assert run(project, "esp32", FULL) == 0
    files = generated(project)
    cfg = constants(files["config"])
    pins = (project / "src/system" / BOARD / "pins.csv").read_text().splitlines()
    numbers = {
        line.split(",")[0]: int(line.split("GPIO")[1])
        for line in pins
        if "GPIO" in line
    }
    assert cfg["LED_PIN"] == numbers["LED_GREEN"]
    assert cfg["SENSORS_SCL_PIN"] == numbers["I2C1_SCL"]
    assert cfg["NOR_CS_PIN"] == numbers["FLASH_CS"]
    assert all(isinstance(v, int) for k, v in cfg.items() if k.endswith("_PIN"))
    assert 'hasattr(Pin.cpu, "GPIO%d" % pin)' in files["test"]


def test_esp32_integer_pin_without_a_board_name_is_not_checked_in_the_test(tmp_path):
    project = make_project(tmp_path, "esp32")
    rows = (project / "src/system" / BOARD / "pins.csv").read_text().splitlines()
    free = len(rows) + 3
    design = design_of(
        {"name": "led", "kind": "led", "pins": {"pin": "LED_GREEN"}},
        {"name": "a", "kind": "gpio", "pins": {"pin": str(free)}},
    )
    assert run(project, "esp32", design) == 0
    text = generated(project)["test"]
    assert '"LED_PIN"' in text and '"A_PIN"' not in text
    assert (
        'hasattr(Pin.cpu, "GPIO%d" % pin), name)  # type: ignore[attr-defined]' in text
    )
    assert_tests_ok(unix_run(project, RUN_HARDWARE_TESTS))


def test_esp32_accepts_gpio_names_and_numbers_without_a_pins_csv(tmp_path):
    project = make_project(tmp_path, "esp32", commit=False)
    (project / "src/system" / BOARD / "pins.csv").unlink()
    design = design_of(
        {"name": "a", "kind": "gpio", "pins": {"pin": "GPIO7"}},
        {"name": "b", "kind": "gpio", "pins": {"pin": "8"}},
    )
    assert run(project, "esp32", design, "--force") == 0
    cfg = constants(generated(project)["config"])
    assert (cfg["A_PIN"], cfg["B_PIN"]) == (7, 8)
    assert "PINS_CSV" not in generated(project)["test"]


def test_esp32_unresolvable_pin_exits_one(tmp_path, capsys):
    project = make_project(tmp_path, "esp32")
    assert (
        run(
            project,
            "esp32",
            design_of({"name": "a", "kind": "gpio", "pins": {"pin": "NOPE"}}),
        )
        == 1
    )
    assert "esp32 pin 'NOPE' has no GPIO number" in capsys.readouterr().err


def test_esp32_pins_csv_option_supplies_the_mapping(tmp_path):
    project = make_project(tmp_path, "esp32", commit=False)
    (project / "src/system" / BOARD / "pins.csv").unlink()
    elsewhere = tmp_path / "elsewhere.csv"
    elsewhere.write_text("MYPIN,GPIO21\n")
    design = design_of({"name": "a", "kind": "gpio", "pins": {"pin": "MYPIN"}})
    assert run(project, "esp32", design, "--pins-csv", str(elsewhere), "--force") == 0
    assert constants(generated(project)["config"])["A_PIN"] == 21


def test_esp32_pin_mapped_to_a_non_gpio_name_exits_one(tmp_path, capsys):
    project = make_project(tmp_path, "esp32", commit=False)
    (project / "src/system" / BOARD / "pins.csv").write_text("X,PA3\n")
    design = design_of({"name": "a", "kind": "gpio", "pins": {"pin": "X"}})
    assert run(project, "esp32", design, "--force") == 1
    assert "maps to 'PA3'" in capsys.readouterr().err


# ----------------------------------------------------------------------------------------
# led handling and device.py
# ----------------------------------------------------------------------------------------


def test_led_design_leaves_device_py_and_test_blink_alone(tmp_path):
    project = make_project(tmp_path)
    original = (project / "src/firmware/application/device.py").read_text()
    assert run(project, "stm32", FULL) == 0
    assert generated(project)["device"] == original
    assert (project / "src/firmware/test/test_blink.py").exists()
    hw = generated(project)["hardware"]
    assert "class Blinky:" in hw and "import asyncio" in hw
    assert (
        "blinky=Blinky(led, device_config.LED_ON_TIME, device_config.LED_OFF_TIME),"
        in hw
    )
    assert "devices.blinky.stop()" in hw


def test_design_without_led_patches_device_py_and_deletes_test_blink(tmp_path, capsys):
    project = make_project(tmp_path)
    assert run(project, "stm32", by_name("button", "vbat")) == 0
    summary = json.loads(capsys.readouterr().out)
    files = generated(project)
    assert "TASKS = ()" in files["device"]
    assert "devices.blinky" not in files["device"]
    assert "    start_repl()\n\n    loop.run_forever()" in files["device"]
    assert not (project / "src/firmware/test/test_blink.py").exists()
    assert summary["deleted"] == ["src/firmware/test/test_blink.py"]
    assert "src/firmware/application/device.py" in summary["patched"]
    hw, cfg = files["hardware"], files["config"]
    assert "Blinky" not in hw and "asyncio" not in hw and "LED_" not in hw
    assert "LED_" not in cfg
    assert "def shutdown():\n    pass\n" in hw
    compile(files["device"], "device.py", "exec")


def test_device_py_patch_is_idempotent_and_reversible(tmp_path, capsys):
    project = make_project(tmp_path)
    app = project / "src/firmware/application"
    original = (app / "device.py").read_text()
    assert run(project, "stm32", by_name("button"), "--force") == 0
    patched = generated(project)["device"]
    assert patched != original
    assert run(project, "stm32", by_name("button"), "--force") == 0
    assert generated(project)["device"] == patched
    # Blinky is gone from hardware.py, so a led design cannot be generated until it returns.
    assert run(project, "stm32", by_name("led", "button"), "--force") == 1
    assert "has no Blinky class" in capsys.readouterr().err
    assert generated(project)["device"] == patched
    git(project, "checkout", "--", "src/firmware/application/hardware.py")
    git(project, "checkout", "--", "src/firmware/application/device_config.py")
    assert run(project, "stm32", by_name("led", "button"), "--force") == 0
    assert generated(project)["device"] == original


def test_device_py_without_the_expected_text_fails_without_writing(tmp_path, capsys):
    project = make_project(tmp_path, commit=False)
    device = project / "src/firmware/application/device.py"
    device.write_text("TASKS = (something_else,)\n")
    assert run(project, "stm32", by_name("button"), "--force") == 1
    assert "device.py has neither" in capsys.readouterr().err
    assert not (project / "src/firmware/test/test_hardware.py").exists()
    assert (
        "class Blinky" in (project / "src/firmware/application/hardware.py").read_text()
    )


def test_active_low_led_is_inverted_for_blinky(tmp_path):
    design = design_of(
        {
            "name": "led",
            "kind": "led",
            "pins": {"pin": "LED_GREEN"},
            "active_high": False,
        }
    )
    project = make_project(tmp_path)
    assert run(project, "stm32", design) == 0
    files = generated(project)
    hw = files["hardware"]
    assert "class InvertedPin:" in hw
    assert "led = Pin(device_config.LED_PIN, Pin.OUT, value=1)" in hw
    assert "blinky=Blinky(InvertedPin(led), " in hw
    assert "# Pin driving the status LED, active low." in files["config"]
    assert "self.assertEqual(hardware.led.value(), 1)" in files["test"]


def test_more_than_one_led_is_refused(tmp_path, capsys):
    project = make_project(tmp_path)
    two = design_of(
        {"name": "a", "kind": "led", "pins": {"pin": "LED_GREEN"}},
        {"name": "b", "kind": "led", "pins": {"pin": "LED_RED"}},
    )
    assert run(project, "stm32", two) == 1
    assert "only one led peripheral" in capsys.readouterr().err


def test_no_peripherals_still_yields_valid_files(tmp_path):
    project = make_project(tmp_path)
    assert run(project, "stm32", design_of()) == 0
    files = generated(project)
    for name, text in files.items():
        compile(text, name, "exec")
    assert "devices = DeviceCollection()" in files["hardware"]
    assert "import device_config" not in files["hardware"]
    assert "def test_shutdown_runs(self):" in files["test"]


# ----------------------------------------------------------------------------------------
# simulation machine.py
# ----------------------------------------------------------------------------------------


def test_spi_design_leaves_the_simulation_machine_py_alone(tmp_path, capsys):
    project = make_project(tmp_path)
    machine = project / "src/unix/simulation/machine.py"
    before = machine.read_text()
    assert "class SPI(_MockSPI):" in before  # the template carries the SPI adapter
    assert run(project, "rp2", by_name("flash")) == 0
    assert machine.read_text() == before
    assert "machine.py" not in capsys.readouterr().out


# ----------------------------------------------------------------------------------------
# refusal to overwrite
# ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relative",
    [
        "src/firmware/application/hardware.py",
        "src/firmware/application/device_config.py",
        "src/firmware/application/device.py",
    ],
)
def test_modified_file_blocks_generation_unless_forced(tmp_path, capsys, relative):
    project = make_project(tmp_path)
    target = project / relative
    target.write_text(target.read_text() + "# local edit\n")
    assert run(project, "stm32", FULL) == 1
    assert relative in capsys.readouterr().err
    assert not (project / "src/firmware/test/test_hardware.py").exists()
    assert target.read_text().endswith("# local edit\n")
    assert run(project, "stm32", FULL, "--force") == 0


def test_refusal_message_tells_what_to_do(tmp_path, capsys):
    project = make_project(tmp_path)
    target = project / "src/firmware/application/hardware.py"
    target.write_text(target.read_text() + "# local edit\n")
    assert run(project, "stm32", FULL) == 1
    captured = capsys.readouterr()
    assert "differ from git HEAD or are not tracked yet" in captured.err
    assert "Commit the previous output, or use --force" in captured.err
    assert json.loads(captured.out)["errors"]


def test_stdout_is_only_the_json_result(tmp_path, capsys):
    project = make_project(tmp_path)
    assert run(project, "stm32", FULL) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["written"]


def test_untracked_test_hardware_blocks_generation(tmp_path, capsys):
    project = make_project(tmp_path)
    (project / "src/firmware/test/test_hardware.py").write_text("# mine\n")
    assert run(project, "stm32", FULL) == 1
    assert "test_hardware.py" in capsys.readouterr().err
    assert (project / "src/firmware/test/test_hardware.py").read_text() == "# mine\n"


def test_modified_test_blink_blocks_deletion(tmp_path, capsys):
    project = make_project(tmp_path)
    blink = project / "src/firmware/test/test_blink.py"
    blink.write_text(blink.read_text() + "# local edit\n")
    assert run(project, "stm32", by_name("button")) == 1
    assert "test_blink.py" in capsys.readouterr().err
    assert blink.exists()


def test_committed_generated_files_can_be_regenerated(tmp_path):
    project = make_project(tmp_path)
    assert run(project, "stm32", FULL) == 0
    git(project, "add", "-A")
    git(project, "commit", "-qm", "gen")
    changed = by_name("led", "vbat")
    assert run(project, "stm32", changed) == 0
    hw = generated(project)["hardware"]
    assert "ADC(" in hw and "I2C(" not in hw and "class Blinky:" in hw


def test_project_without_git_needs_force(tmp_path, capsys):
    project = make_project(tmp_path, commit=False)
    assert run(project, "stm32", FULL) == 1
    assert "not a git checkout" in capsys.readouterr().err
    assert run(project, "stm32", FULL, "--force") == 0


# ----------------------------------------------------------------------------------------
# design validation
# ----------------------------------------------------------------------------------------


def bad(*peripherals):
    return design_of(*peripherals)


@pytest.mark.parametrize(
    "peripherals,message",
    [
        ([{"name": "a", "kind": "dac", "pins": {"pin": "FAN"}}], "unknown kind 'dac'"),
        (
            [{"name": "a", "kind": "i2c", "pins": {"scl": "X", "sda": "Y"}}],
            "bus_id missing",
        ),
        (
            [{"name": "a", "kind": "i2c", "bus_id": 1, "pins": {"scl": "X"}}],
            "pins.sda missing",
        ),
        (
            [{"name": "a", "kind": "uart", "bus_id": 1, "pins": {}}],
            "needs one of pins.tx",
        ),
        (
            [{"name": "a", "kind": "gpio", "pins": {"pin": "X", "tx": "Y"}}],
            "unexpected pin role 'tx'",
        ),
        (
            [
                {"name": "a", "kind": "gpio", "pins": {"pin": "X"}},
                {"name": "A", "kind": "gpio", "pins": {"pin": "Y"}},
            ],
            "already used",
        ),
        ([{"name": "led", "kind": "gpio", "pins": {"pin": "X"}}], "'led' is reserved"),
        (
            [{"name": "devices", "kind": "gpio", "pins": {"pin": "X"}}],
            "'devices' is reserved",
        ),
        (
            [{"name": "1a", "kind": "gpio", "pins": {"pin": "X"}}],
            "cannot be used as a Python name",
        ),
        (
            [{"name": "class", "kind": "gpio", "pins": {"pin": "X"}}],
            "cannot be used as a Python",
        ),
        (
            [
                {
                    "name": "a",
                    "kind": "i2c",
                    "bus_id": 1,
                    "pins": {"scl": "X", "sda": "Y"},
                    "devices": [{"name": "d", "addr": "0x80"}],
                }
            ],
            "not a 7-bit address",
        ),
        (
            [
                {
                    "name": "a",
                    "kind": "i2c",
                    "bus_id": 1,
                    "pins": {"scl": "X", "sda": "Y"},
                    "devices": [{"name": "d", "cs": "Z"}],
                }
            ],
            "cs applies to spi devices",
        ),
        (
            [
                {
                    "name": "a",
                    "kind": "gpio",
                    "direction": "sideways",
                    "pins": {"pin": "X"},
                }
            ],
            "direction must be in or out",
        ),
        (
            [{"name": "a", "kind": "gpio", "pull": "middle", "pins": {"pin": "X"}}],
            "pull must be up, down or none",
        ),
        (
            [{"name": "a", "kind": "pwm", "freq": 0, "pins": {"pin": "X"}}],
            "freq must be at least 1",
        ),
        (
            [{"name": "a", "kind": "uart", "bus_id": "x", "pins": {"tx": "X"}}],
            "bus_id must be an integer",
        ),
        (
            [
                {
                    "name": "nor_cs",
                    "kind": "i2c",
                    "bus_id": 0,
                    "pins": {"scl": "X", "sda": "Y"},
                },
                {
                    "name": "flash",
                    "kind": "spi",
                    "bus_id": 1,
                    "pins": {"sck": "X", "mosi": "Y"},
                    "devices": [{"name": "nor", "cs": "Z"}],
                },
            ],
            "two objects would be named devices.nor_cs",
        ),
        (
            [
                {"name": "nor_cs", "kind": "gpio", "pins": {"pin": "BTN"}},
                {
                    "name": "flash",
                    "kind": "spi",
                    "bus_id": 1,
                    "pins": {"sck": "X", "mosi": "Y"},
                    "devices": [{"name": "nor", "cs": "Z"}],
                },
            ],
            "constant NOR_CS_PIN is generated for both nor_cs and nor",
        ),
    ],
)
def test_invalid_designs_exit_one_and_write_nothing(
    tmp_path, capsys, peripherals, message
):
    project = make_project(tmp_path)
    assert run(project, "stm32", design_of(*peripherals)) == 1
    captured = capsys.readouterr()
    assert message in captured.err
    assert message in json.loads(captured.out)["errors"][0]
    assert git(project, "status", "--porcelain").stdout == ""


def test_failed_generation_reports_json_errors(tmp_path, capsys):
    project = make_project(tmp_path)
    assert run(project, "stm32", by_name("sensors"), "--force", board="bad/name") == 1
    out = json.loads(capsys.readouterr().out)
    assert list(out) == ["errors"]


def test_usage_errors_exit_two(tmp_path, capsys):
    assert (
        gen_hardware.main(
            [
                "--project",
                str(tmp_path / "nope"),
                "--port",
                "stm32",
                "--peripherals",
                "x",
                "--board-name",
                "B",
            ]
        )
        == 2
    )
    with pytest.raises(SystemExit) as exc:
        gen_hardware.main(["--project", str(tmp_path), "--port", "unix"])
    assert exc.value.code == 2


def test_project_without_template_files_is_refused(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run(empty, "stm32", FULL) == 1
    assert "not an app-template project" in capsys.readouterr().err


def test_bad_board_name_is_refused(tmp_path, capsys):
    project = make_project(tmp_path)
    assert run(project, "stm32", FULL, board="../evil") == 1
    assert "not a directory name" in capsys.readouterr().err


def test_names_over_the_length_limit_are_refused(tmp_path, capsys):
    project = make_project(tmp_path)
    name = "n" * (gen_hardware.MAX_NAME_LENGTH + 1)
    assert (
        run(
            project,
            "stm32",
            design_of({"name": name, "kind": "gpio", "pins": {"pin": "BTN"}}),
        )
        == 1
    )
    assert "longer than 24 characters" in capsys.readouterr().err
    ok = "n" * gen_hardware.MAX_NAME_LENGTH
    assert (
        run(
            project,
            "stm32",
            design_of({"name": ok, "kind": "gpio", "pins": {"pin": "BTN"}}),
        )
        == 0
    )


# ----------------------------------------------------------------------------------------
# the test file
# ----------------------------------------------------------------------------------------


def test_test_file_points_at_the_board_pins_csv(tmp_path):
    project = make_project(tmp_path)
    assert run(project, "stm32", FULL) == 0
    text = generated(project)["test"]
    assert f'PINS_CSV = "../../../../src/system/{BOARD}/pins.csv"' in text
    assert "Pin.board.configure(PINS_CSV)  # type: ignore[attr-defined]" in text
    assert "Pin.board.configure(None)  # type: ignore[attr-defined]" in text
    assert '"LED_PIN",' in text and '"NOR_CS_PIN",' in text
    assert "SENSORS_SCL_PIN" not in text  # stm32 buses carry no pin constants


def test_test_file_has_no_board_checks_without_a_board_pins_csv(tmp_path):
    project = make_project(tmp_path, commit=False)
    (project / "src/system" / BOARD / "pins.csv").unlink()
    assert run(project, "stm32", FULL, "--force") == 0
    text = generated(project)["test"]
    assert "PINS_CSV" not in text and "TestBoardPins" not in text


def test_pad_form_pins_are_not_checked_against_the_board(tmp_path):
    project = make_project(tmp_path, "rp2")
    design = design_of(
        {"name": "a", "kind": "gpio", "pins": {"pin": "GPIO7"}},
        {"name": "b", "kind": "gpio", "pins": {"pin": "BTN"}},
    )
    assert run(project, "rp2", design) == 0
    text = generated(project)["test"]
    assert '"B_PIN"' in text and '"A_PIN"' not in text


def test_pad_form_pins_are_still_checked_on_stm32(tmp_path):
    project = make_project(tmp_path)
    design = design_of({"name": "a", "kind": "gpio", "pins": {"pin": "PA7"}})
    assert run(project, "stm32", design) == 0
    assert '"A_PIN"' in generated(project)["test"]


def test_pins_missing_from_pins_csv_are_noted(tmp_path, capsys):
    project = make_project(tmp_path)
    design = design_of({"name": "a", "kind": "gpio", "pins": {"pin": "NOT_THERE"}})
    assert run(project, "stm32", design) == 0
    assert (
        "pin NOT_THERE of a is not in"
        in json.loads(capsys.readouterr().out)["notes"][0]
    )


# ----------------------------------------------------------------------------------------
# ruff
# ----------------------------------------------------------------------------------------

ruff = pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not installed")

LONG = design_of(
    {"name": "led", "kind": "led", "pins": {"pin": "LED_GREEN"}},
    {
        "name": "sensor_bus_with_long_nam",
        "kind": "i2c",
        "bus_id": 1,
        "pins": {"scl": "I2C1_SCL", "sda": "I2C1_SDA"},
        "devices": [{"name": "device_with_long_name_xx", "addr": 0x10}],
    },
    {
        "name": "spi_peripheral_long_name",
        "kind": "spi",
        "bus_id": 2,
        "pins": {"sck": "SPI2_SCK", "mosi": "SPI2_MOSI", "miso": "SPI2_MISO"},
        "devices": [{"name": "flash_chip_long_name_xx", "cs": "FLASH_CS"}],
    },
    {
        "name": "gpio_with_a_long_name_xx",
        "kind": "gpio",
        "direction": "in",
        "pull": "down",
        "pins": {"pin": "BTN"},
    },
    {
        "name": "pwm_output_long_name_fan",
        "kind": "pwm",
        "freq": 25000,
        "pins": {"pin": "FAN"},
    },
)


@ruff
@pytest.mark.parametrize("port", ALL_PORTS)
@pytest.mark.parametrize(
    "design", [FULL, LONG, by_name("button"), design_of()], ids=str
)
def test_generated_files_pass_ruff_format_and_check(tmp_path, port, design):
    project = make_project(tmp_path, port)
    assert run(project, port, design) == 0
    paths = [
        project / "src/firmware/application/device_config.py",
        project / "src/firmware/application/hardware.py",
        project / "src/firmware/application/device.py",
        project / "src/firmware/test/test_hardware.py",
    ]
    names = [str(p) for p in paths]
    fmt = subprocess.run(
        ["ruff", "format", "--check", "--isolated", "--line-length", "99", *names],
        capture_output=True,
        text=True,
        check=False,
    )
    assert fmt.returncode == 0, fmt.stdout + fmt.stderr
    lint = subprocess.run(
        [
            "ruff",
            "check",
            "--isolated",
            "--select",
            "E,F",
            "--line-length",
            "99",
            *names,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert lint.returncode == 0, lint.stdout + lint.stderr


# ----------------------------------------------------------------------------------------
# run on the unix port with mock_machine
# ----------------------------------------------------------------------------------------


def unix_env():
    if not UNIX_MPY.is_file():
        pytest.skip("no unix MicroPython binary")
    stdlib = next((p for p in STDLIB_CANDIDATES if (p / "unittest").is_dir()), None)
    mock = next((p for p in MOCK_CANDIDATES if (p / "mock_machine.py").is_file()), None)
    if stdlib is None or mock is None or not EXTMOD.is_dir():
        pytest.skip("micropython-lib or mock_machine not available")
    return stdlib, mock


def unix_run(project, code):
    stdlib, mock = unix_env()
    path = [
        project / "src/firmware/application",
        project / "src/firmware/test",
        project / "src/unix/simulation",
        mock,
        stdlib / "logging",
        stdlib / "unittest",
        EXTMOD,
    ]
    cwd = project / "src/unix/build/frozen_mpy"
    cwd.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MICROPYPATH": ":".join(map(str, path))}
    return subprocess.run(
        [str(UNIX_MPY), "-c", code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def output(result):
    return result.stdout + result.stderr


def assert_run_ok(result):
    text = output(result)
    assert result.returncode == 0 and "Traceback" not in text, text


def assert_tests_ok(result, count=None):
    # unittest.main() on the unix port exits 0 even when tests fail; read the summary.
    assert_run_ok(result)
    text = output(result)
    assert "\nOK" in text and "FAILED" not in text, text
    if count is not None:
        assert f"Ran {count} tests" in text, text


RUN_HARDWARE_TESTS = "import unittest; unittest.main('test_hardware')"


@pytest.mark.parametrize("port", ALL_PORTS)
def test_generated_tests_pass_on_the_unix_port(tmp_path, port):
    project = make_project(tmp_path, port)
    assert run(project, port, FULL) == 0
    assert_tests_ok(unix_run(project, RUN_HARDWARE_TESTS), count=9)


def test_generated_tests_pass_with_pad_form_pins_on_the_unix_port(tmp_path):
    project = make_project(tmp_path, "rp2")
    design = design_of(
        {"name": "led", "kind": "led", "pins": {"pin": "LED_GREEN"}},
        {"name": "a", "kind": "gpio", "pins": {"pin": "GPIO7"}},
    )
    assert run(project, "rp2", design) == 0
    assert_tests_ok(unix_run(project, RUN_HARDWARE_TESTS))


def test_generated_tests_pass_with_an_active_low_led(tmp_path):
    design = copy.deepcopy(FULL)
    design["peripherals"][0]["active_high"] = False
    project = make_project(tmp_path, "rp2")
    assert run(project, "rp2", design) == 0
    assert_tests_ok(unix_run(project, RUN_HARDWARE_TESTS), count=9)


def test_blink_tests_and_application_import_on_the_unix_port(tmp_path):
    project = make_project(tmp_path, "rp2")
    assert run(project, "rp2", FULL) == 0
    assert_tests_ok(
        unix_run(project, "import unittest; unittest.main('test_blink')"), count=5
    )
    result = unix_run(project, "import device, hardware; print(device.TASKS)")
    assert_run_ok(result)
    assert "Blinky" in result.stdout


def test_design_without_led_imports_on_the_unix_port(tmp_path):
    project = make_project(tmp_path, "rp2")
    assert run(project, "rp2", by_name("button", "flash", "fan")) == 0
    assert_tests_ok(unix_run(project, RUN_HARDWARE_TESTS))
    result = unix_run(project, "import device; print(device.TASKS)")
    assert_run_ok(result)
    assert result.stdout.strip().endswith("()")


def test_a_wrong_pin_name_fails_the_generated_board_test_on_the_unix_port(tmp_path):
    project = make_project(tmp_path, "rp2")
    assert run(project, "rp2", by_name("button")) == 0
    pins = project / "src/system" / BOARD / "pins.csv"
    pins.write_text(pins.read_text().replace("BTN,", "OTHER_NAME,"))
    text = output(unix_run(project, RUN_HARDWARE_TESTS))
    assert "FAILED" in text
    assert "test_pin_constants_exist_on_the_board" in text


def test_a_missing_board_file_fails_the_loaded_check_on_the_unix_port(tmp_path):
    project = make_project(tmp_path, "rp2")
    assert run(project, "rp2", by_name("button")) == 0
    (project / "src/system" / BOARD / "pins.csv").unlink()
    text = output(unix_run(project, RUN_HARDWARE_TESTS))
    assert "FAILED" in text
    assert "test_board_file_is_loaded" in text
