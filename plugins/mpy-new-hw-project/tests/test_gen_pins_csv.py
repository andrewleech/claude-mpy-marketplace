import json

import gen_pins_csv
import parse_netlist
import resolve_pinmap
from common import is_unnamed_net


def pinmap(
    fixtures,
    nets_name="stm32_board_kicad.net",
    port="stm32",
    table="stm32_pin_table.csv",
):
    doc = parse_netlist.parse_file(fixtures / nets_name)
    errors = []
    tbl = resolve_pinmap.table_from_csv(fixtures / table, errors)
    res = resolve_pinmap.resolve(doc, "U1", port, tbl, table_errors=errors)
    assert res["status"] == "ok", res["errors"]
    return res


def test_rows_from_kicad_design(fixtures):
    rows, skipped, errors, _ = gen_pins_csv.build_rows(pinmap(fixtures), "stm32")
    assert errors == []
    d = dict(rows)
    assert d["PA3"] == "PA3"
    assert d["PA4"] == "PA4"  # "/PA4" loses the sheet prefix
    assert d["LED_GREEN"] == "PB0"
    assert d["USER_BTN"] == "PB1"
    assert d["I2C2_SCL"] == "PB10"
    assert d["P_3V3_SENSE"] == "PC0"  # digit first gets the P_ prefix
    assert len(d) == len(rows)
    assert any(s.endswith("Net-(R5-Pad1)") for s in skipped)
    assert not any(name.startswith("NET") for name, _ in rows)


def test_protel_unnamed_net_skipped(fixtures):
    rows, skipped, errors, _ = gen_pins_csv.build_rows(
        pinmap(fixtures, "stm32_board_protel.net"), "stm32"
    )
    assert errors == []
    assert "100:NetR5_1" in skipped
    assert "PC9" not in {p for _, p in rows}


def test_exclude_by_net_or_board_name(fixtures):
    rows, skipped, _, _ = gen_pins_csv.build_rows(
        pinmap(fixtures), "stm32", exclude={"user_btn", "/PA4"}
    )
    names = {n for n, _ in rows}
    assert "USER_BTN" not in names and "PA4" not in names
    assert "47:USER_BTN" in skipped


def test_self_named_kept_on_stm32_by_default(fixtures):
    rows, _, _, _ = gen_pins_csv.build_rows(pinmap(fixtures), "stm32")
    assert ("PA3", "PA3") in rows


def test_self_named_skipped_on_rp2_by_default():
    pm = {
        "pins": [
            {"package_pin": "1", "port_name": "GPIO3", "net": "GPIO3", "anchor": False},
            {"package_pin": "2", "port_name": "GPIO4", "net": "LED", "anchor": False},
        ]
    }
    rows, skipped, _, _ = gen_pins_csv.build_rows(pm, "rp2")
    assert rows == [("LED", "GPIO4")]
    assert "1:GPIO3" in skipped
    rows, _, _, _ = gen_pins_csv.build_rows(pm, "rp2", keep_self_named=True)
    assert ("GPIO3", "GPIO3") in rows


def test_keep_self_named_forces_on_stm32_off(fixtures):
    rows, _, _, _ = gen_pins_csv.build_rows(
        pinmap(fixtures), "stm32", keep_self_named=False
    )
    assert not any(n == p for n, p in rows)
    assert ("LED_GREEN", "PB0") in rows


def test_name_collision_is_error():
    pm = {
        "pins": [
            {"package_pin": "1", "port_name": "PA0", "net": "/s1/LED", "anchor": False},
            {"package_pin": "2", "port_name": "PA1", "net": "/s2/led", "anchor": False},
        ]
    }
    rows, _, errors, _ = gen_pins_csv.build_rows(pm, "stm32")
    assert rows == [("LED", "PA0")]
    assert errors == ["board pin name LED is used by nets '/s1/LED' and '/s2/led'"]


def test_invalid_port_name_is_error():
    pm = {
        "pins": [
            {"package_pin": "1", "port_name": "GPIO3", "net": "X", "anchor": False}
        ]
    }
    _, _, errors, _ = gen_pins_csv.build_rows(pm, "stm32")
    assert errors and "'GPIO3' is not a valid stm32 port name" in errors[0]


def test_cli_writes_csv(fixtures, tmp_path, capsys):
    pm_path = tmp_path / "pinmap.json"
    pm_path.write_text(json.dumps(pinmap(fixtures)))
    out = tmp_path / "board" / "pins.csv"
    rc = gen_pins_csv.main(
        [
            "--pinmap",
            str(pm_path),
            "--port",
            "stm32",
            "--exclude",
            "USER_BTN",
            "-o",
            str(out),
        ]
    )
    assert rc == 0
    lines = out.read_text().splitlines()
    assert "LED_GREEN,PB0" in lines
    assert "USER_BTN,PB1" not in lines
    assert all(len(line.split(",")) == 2 for line in lines)
    assert json.loads(capsys.readouterr().out)["count"] == len(lines)


def test_cli_collision_exit_1(tmp_path, capsys):
    pm = {
        "port": "stm32",
        "status": "ok",
        "pins": [
            {"package_pin": "1", "port_name": "PA0", "net": "LED", "anchor": False},
            {"package_pin": "2", "port_name": "PA1", "net": "/x/LED", "anchor": False},
        ],
    }
    p = tmp_path / "pinmap.json"
    p.write_text(json.dumps(pm))
    out = tmp_path / "pins.csv"
    assert (
        gen_pins_csv.main(["--pinmap", str(p), "--port", "stm32", "-o", str(out)]) == 1
    )
    assert not out.exists()
    assert "board pin name LED" in capsys.readouterr().err


def test_cli_rejects_failed_pinmap(tmp_path):
    p = tmp_path / "pinmap.json"
    p.write_text(json.dumps({"port": "stm32", "status": "fail", "pins": []}))
    assert gen_pins_csv.main(["--pinmap", str(p), "--port", "stm32"]) == 1


def test_cli_rejects_port_mismatch(fixtures, tmp_path):
    p = tmp_path / "pinmap.json"
    p.write_text(json.dumps(pinmap(fixtures)))
    assert gen_pins_csv.main(["--pinmap", str(p), "--port", "rp2"]) == 1


def test_rp2_rows(fixtures):
    rows, _, errors, _ = gen_pins_csv.build_rows(
        pinmap(fixtures, "rp2_board.csv", "rp2", "rp2_pin_table.csv"), "rp2"
    )
    assert errors == []
    assert ("I2C0_SDA", "GPIO4") in rows
    assert ("GPIO3_LED", "GPIO3") in rows


def test_mimxrt_rows_with_af_names(fixtures):
    from common import load_port_names

    pm = pinmap(fixtures, "mimxrt_board.csv", "mimxrt", "mimxrt_pin_table.csv")
    af = load_port_names("mimxrt", fixtures / "mimxrt_af.csv")
    rows, _, errors, _ = gen_pins_csv.build_rows(pm, "mimxrt", af_names=af)
    assert errors == []
    assert ("UART1_TX", "GPIO_AD_B0_12") in rows


def test_include_pad_adds_unnamed_net_pad(fixtures):
    pm = pinmap(fixtures)
    unnamed = next(p for p in pm["pins"] if is_unnamed_net(p["net"]))
    pad = unnamed["port_name"]
    rows, _, errors, _ = gen_pins_csv.build_rows(pm, "stm32", include_pads={pad: pad})
    assert errors == []
    assert (pad, pad) in rows
    rows, _, errors, _ = gen_pins_csv.build_rows(
        pm, "stm32", include_pads={pad: "SENSE_X"}
    )
    assert errors == [] and ("SENSE_X", pad) in rows


def test_include_pad_unknown_pad_is_error(fixtures):
    _, _, errors, _ = gen_pins_csv.build_rows(
        pinmap(fixtures), "stm32", include_pads={"PG15": "PG15"}
    )
    assert errors == ["--include-pad PG15: pad is not in the pinmap"]


def test_cli_include_pad_repeatable(fixtures, tmp_path):
    pm = pinmap(fixtures)
    unnamed = [p["port_name"] for p in pm["pins"] if is_unnamed_net(p["net"])]
    assert unnamed
    p = tmp_path / "pinmap.json"
    p.write_text(json.dumps(pm))
    out = tmp_path / "pins.csv"
    args = ["--pinmap", str(p), "--port", "stm32", "-o", str(out)]
    args += ["--include-pad", f"{unnamed[0]}=MY_PAD"]
    if len(unnamed) > 1:
        args += ["--include-pad", unnamed[1]]
    assert gen_pins_csv.main(args) == 0
    lines = out.read_text().splitlines()
    assert f"MY_PAD,{unnamed[0]}" in lines
    if len(unnamed) > 1:
        assert f"{unnamed[1]},{unnamed[1]}" in lines
    assert gen_pins_csv.main(args + ["--include-pad", "PG15"]) == 1


def test_include_pad_on_named_net_warns(fixtures, tmp_path, capsys):
    pm = pinmap(fixtures)
    p = tmp_path / "pinmap.json"
    p.write_text(json.dumps(pm))
    out = tmp_path / "pins.csv"
    args = [
        "--pinmap",
        str(p),
        "--port",
        "stm32",
        "-o",
        str(out),
        "--include-pad",
        "PB0=X",
    ]
    assert gen_pins_csv.main(args) == 0
    cap = capsys.readouterr()
    assert "--include-pad PB0" in cap.err
    summary = json.loads(cap.out)
    assert len(summary["warnings"]) == 1
    assert "X,PB0" not in out.read_text().splitlines()


def test_esp32_self_named_skipped_by_default():
    pm = {
        "pins": [
            {"package_pin": "1", "port_name": "GPIO4", "net": "GPIO4", "anchor": False},
            {"package_pin": "2", "port_name": "GPIO5", "net": "LED", "anchor": False},
        ]
    }
    rows, _, _, _ = gen_pins_csv.build_rows(pm, "esp32")
    assert rows == [("LED", "GPIO5")]


def test_esp32_gpio_range_error_reports_the_limit():
    pm = {
        "pins": [
            {"package_pin": "1", "port_name": "GPIO99", "net": "X", "anchor": False}
        ]
    }
    _, _, errors, _ = gen_pins_csv.build_rows(pm, "esp32", num_gpios=55)
    assert errors == [
        "package pin 1: 'GPIO99' is not a valid esp32 port name: make-pins.py accepts "
        "GPIO0 to GPIO54 (NUM_GPIOS = 55)"
    ]
    _, _, errors, _ = gen_pins_csv.build_rows(pm, "esp32")
    assert errors == []


def test_cli_micropython_option_range_checks_esp32(fixtures, tmp_path, capsys):
    pm = {
        "port": "esp32",
        "status": "ok",
        "pins": [
            {"package_pin": "1", "port_name": "GPIO99", "net": "X", "anchor": False}
        ],
    }
    p = tmp_path / "pinmap.json"
    p.write_text(json.dumps(pm))
    args = ["--pinmap", str(p), "--port", "esp32"]
    assert gen_pins_csv.main(args) == 0
    capsys.readouterr()
    assert gen_pins_csv.main([*args, "--micropython", str(fixtures / "lint_mpy")]) == 1
    assert "NUM_GPIOS = 55" in capsys.readouterr().err


def test_cli_keep_self_named_flag(tmp_path):
    pm = {
        "port": "rp2",
        "status": "ok",
        "pins": [
            {"package_pin": "1", "port_name": "GPIO3", "net": "GPIO3", "anchor": False}
        ],
    }
    p = tmp_path / "pinmap.json"
    p.write_text(json.dumps(pm))
    out = tmp_path / "pins.csv"
    assert gen_pins_csv.main(["--pinmap", str(p), "--port", "rp2", "-o", str(out)]) == 0
    assert out.read_text() == ""
    assert (
        gen_pins_csv.main(
            ["--pinmap", str(p), "--port", "rp2", "--keep-self-named", "-o", str(out)]
        )
        == 0
    )
    assert out.read_text() == "GPIO3,GPIO3\n"
