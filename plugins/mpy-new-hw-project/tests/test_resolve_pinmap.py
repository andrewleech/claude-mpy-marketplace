import json

import pytest

import parse_netlist
import resolve_pinmap


def nets(fixtures, name):
    return parse_netlist.parse_file(fixtures / name)


def run(fixtures, nets_name, port, table_name, mcu_ref="U1", **kw):
    doc = nets(fixtures, nets_name)
    table_errors = []
    table = resolve_pinmap.table_from_csv(fixtures / table_name, table_errors)
    return resolve_pinmap.resolve(
        doc, mcu_ref, port, table, table_errors=table_errors, **kw
    )


@pytest.mark.parametrize(
    "nets_name", ["stm32_board_kicad.net", "stm32_board_protel.net", "stm32_board.csv"]
)
def test_stm32_ok_all_formats(fixtures, nets_name):
    res = run(fixtures, nets_name, "stm32", "stm32_pin_table.csv")
    assert res["errors"] == []
    assert res["status"] == "ok"
    assert {a["port_name"] for a in res["anchors"]} == {
        "PA3",
        "PA4",
        "PA5",
        "PD8",
        "PD9",
        "PE2",
    }
    by_pin = {p["package_pin"]: p for p in res["pins"]}
    assert by_pin["34"] == {
        "package_pin": "34",
        "port_name": "PA3",
        "net": "PA3",
        "anchor": True,
    }
    assert by_pin["46"]["port_name"] == "PB0"
    assert by_pin["46"]["anchor"] is False
    assert [p["package_pin"] for p in res["pins"]] == sorted(by_pin, key=int)


def test_kicad_net_names_kept_as_in_source(fixtures):
    res = run(fixtures, "stm32_board_kicad.net", "stm32", "stm32_pin_table.csv")
    by_pin = {p["package_pin"]: p for p in res["pins"]}
    assert by_pin["35"]["net"] == "/PA4"
    assert by_pin["35"]["anchor"] is True
    assert by_pin["101"]["net"] == "/power/3V3_SENSE"


def test_wrong_table_fails_with_specific_error(fixtures):
    res = run(fixtures, "stm32_board_kicad.net", "stm32", "stm32_pin_table_wrong.csv")
    assert res["status"] == "fail"
    assert (
        "package pin 34: net 'PA3' names port pad PA3 but the pin table maps pin 34 to PA4"
        in res["errors"]
    )
    assert (
        "package pin 35: net '/PA4' names port pad PA4 but the pin table maps pin 35 to PA3"
        in res["errors"]
    )


def test_cli_wrong_table_exit_1(fixtures, tmp_path, capsys):
    nets_json = tmp_path / "nets.json"
    parse_netlist.main([str(fixtures / "stm32_board_kicad.net"), "-o", str(nets_json)])
    out = tmp_path / "pinmap.json"
    rc = resolve_pinmap.main(
        [
            "--nets", str(nets_json),
            "--mcu-ref", "U1",
            "--port", "stm32",
            "--pin-table", str(fixtures / "stm32_pin_table_wrong.csv"),
            "-o", str(out),
        ]
    )  # fmt: skip
    assert rc == 1
    doc = json.loads(out.read_text())
    assert doc["status"] == "fail"
    assert "maps pin 34 to PA4" in capsys.readouterr().err


def test_cli_ok_writes_pinmap(fixtures, tmp_path, capsys):
    nets_json = tmp_path / "nets.json"
    parse_netlist.main([str(fixtures / "stm32_board_protel.net"), "-o", str(nets_json)])
    out = tmp_path / "pinmap.json"
    rc = resolve_pinmap.main(
        [
            "--nets", str(nets_json),
            "--mcu-ref", "U1",
            "--port", "stm32",
            "--pin-table", str(fixtures / "stm32_pin_table.csv"),
            "--af-file", str(fixtures / "stm32_af.csv"),
            "-o", str(out),
        ]
    )  # fmt: skip
    assert rc == 0
    doc = json.loads(out.read_text())
    assert set(doc) == {"port", "mcu_ref", "status", "pins", "anchors", "errors"}
    assert doc["status"] == "ok"
    err = capsys.readouterr().err.strip().splitlines()[-1]
    assert (
        err
        == f"resolve_pinmap: ok, {len(doc['pins'])} pins, {len(doc['anchors'])} anchors"
    )


def test_confirmed_advice_only_when_anchors_are_the_only_error(fixtures):
    few = run(
        fixtures, "stm32_board_kicad.net", "stm32", "stm32_pin_table.csv", min_anchors=7
    )
    assert any("--confirmed" in e for e in few["errors"])
    wrong = run(
        fixtures,
        "stm32_board_kicad.net",
        "stm32",
        "stm32_pin_table_wrong.csv",
        min_anchors=99,
    )
    assert any(e.startswith("only ") for e in wrong["errors"])
    assert not any("--confirmed" in e for e in wrong["errors"])


def test_too_few_anchors_rejected_without_confirmed(fixtures):
    res = run(
        fixtures, "stm32_board_kicad.net", "stm32", "stm32_pin_table.csv", min_anchors=7
    )
    assert res["status"] == "fail"
    assert any(
        "only 6 anchor(s), need 7" in e and "--confirmed" in e for e in res["errors"]
    )


def test_too_few_anchors_accepted_with_confirmed(fixtures):
    res = run(
        fixtures, "stm32_board_kicad.net", "stm32", "stm32_pin_table.csv",
        min_anchors=7, confirmed=True,
    )  # fmt: skip
    assert res["status"] == "ok"
    assert res["confirmed"] is True


def test_no_anchors_at_all_fails():
    doc = {
        "components": {"U1": {}},
        "nets": {
            "LED": [{"ref": "U1", "pin": "46", "pinfunction": None}],
            "BTN": [{"ref": "U1", "pin": "47", "pinfunction": None}],
        },
    }
    table = [("46", "PB0"), ("47", "PB1")]
    res = resolve_pinmap.resolve(doc, "U1", "stm32", table)
    assert res["status"] == "fail"
    assert res["anchors"] == []
    res = resolve_pinmap.resolve(doc, "U1", "stm32", table, confirmed=True)
    assert res["status"] == "ok"


def test_duplicate_package_pin(fixtures):
    doc = nets(fixtures, "stm32_board.csv")
    res = resolve_pinmap.resolve(
        doc, "U1", "stm32", [("34", "PA3"), ("34", "PA4")], confirmed=True
    )
    assert res["status"] == "fail"
    assert any("package pin 34 appears twice" in e for e in res["errors"])


def test_duplicate_port_name(fixtures):
    doc = nets(fixtures, "stm32_board.csv")
    res = resolve_pinmap.resolve(
        doc, "U1", "stm32", [("46", "PB0"), ("47", "PB0")], confirmed=True
    )
    assert res["status"] == "fail"
    assert any(
        "port name PB0 is mapped to two package pins (46 and 47)" in e
        for e in res["errors"]
    )


def test_invalid_port_name(fixtures):
    doc = nets(fixtures, "stm32_board.csv")
    res = resolve_pinmap.resolve(doc, "U1", "stm32", [("46", "GPIO3")], confirmed=True)
    assert res["status"] == "fail"
    assert any(
        "package pin 46: 'GPIO3' is not a valid stm32 port name" in e
        for e in res["errors"]
    )


def test_port_name_missing_from_af_file(fixtures):
    from common import load_port_names

    names = load_port_names("stm32", fixtures / "stm32_af.csv")
    doc = nets(fixtures, "stm32_board.csv")
    res = resolve_pinmap.resolve(
        doc, "U1", "stm32", [("46", "PB7")], af_names=names, confirmed=True
    )
    assert any("'PB7' is not in the AF file" in e for e in res["errors"])


def test_net_names_a_pad_but_pin_not_in_table(fixtures):
    doc = nets(fixtures, "stm32_board.csv")
    table = [("46", "PB0"), ("47", "PB1")]
    res = resolve_pinmap.resolve(doc, "U1", "stm32", table, confirmed=True)
    assert any(
        "package pin 34: net 'PA3' names port pad PA3 but the pin table has no entry for pin 34"
        in e
        for e in res["errors"]
    )


def test_esp32_gpio_range_uses_num_gpios(fixtures):
    doc = nets(fixtures, "stm32_board.csv")
    table = [("46", "GPIO99")]
    res = resolve_pinmap.resolve(
        doc, "U1", "esp32", table, confirmed=True, num_gpios=55
    )
    assert (
        "package pin 46: 'GPIO99' is not a valid esp32 port name: make-pins.py accepts "
        "GPIO0 to GPIO54 (NUM_GPIOS = 55)" in res["errors"]
    )
    res = resolve_pinmap.resolve(doc, "U1", "esp32", table, confirmed=True)
    assert not any("GPIO99" in e for e in res["errors"])


def test_unknown_mcu_ref(fixtures):
    doc = nets(fixtures, "stm32_board.csv")
    res = resolve_pinmap.resolve(doc, "U9", "stm32", [("1", "PA0")], confirmed=True)
    assert any("MCU reference 'U9' is not in the netlist" in e for e in res["errors"])


def test_from_pinfunction_matches_table(fixtures):
    doc = nets(fixtures, "stm32_board.csv")
    table = resolve_pinmap.table_from_pinfunction(doc["nets"], "U1", "stm32", set())
    assert ("34", "PA3") in table
    assert ("12", "VDD") not in table
    res = resolve_pinmap.resolve(doc, "U1", "stm32", table)
    assert res["status"] == "ok"
    assert len(res["anchors"]) == 6


def test_from_pinfunction_cli(fixtures, tmp_path):
    nets_json = tmp_path / "nets.json"
    parse_netlist.main([str(fixtures / "stm32_board_kicad.net"), "-o", str(nets_json)])
    out = tmp_path / "pinmap.json"
    rc = resolve_pinmap.main(
        ["--nets", str(nets_json), "--mcu-ref", "U1", "--port", "stm32",
         "--from-pinfunction", "-o", str(out)]
    )  # fmt: skip
    assert rc == 0
    assert json.loads(out.read_text())["status"] == "ok"


def test_from_pinfunction_disagreeing_with_net_names_fails(fixtures):
    doc = nets(fixtures, "stm32_board.csv")
    for node in doc["nets"]["PA3"]:
        if node["ref"] == "U1":
            node["pinfunction"] = "PA9"
    table = resolve_pinmap.table_from_pinfunction(doc["nets"], "U1", "stm32", set())
    res = resolve_pinmap.resolve(doc, "U1", "stm32", table)
    assert res["status"] == "fail"
    assert any(
        "net 'PA3' names port pad PA3 but the pin table maps pin 34 to PA9" in e
        for e in res["errors"]
    )


def test_rp2_suffix_and_ok(fixtures):
    res = run(fixtures, "rp2_board.csv", "rp2", "rp2_pin_table.csv")
    assert res["status"] == "ok", res["errors"]
    assert [a["port_name"] for a in res["anchors"]] == [
        "GPIO0",
        "GPIO1",
        "GPIO2",
        "GPIO3",
    ]


def test_rp2_wrong_table(fixtures, tmp_path):
    bad = tmp_path / "t.csv"
    bad.write_text("package_pin,port_name\n2,GPIO1\n3,GPIO0\n4,GPIO2\n5,GPIO3\n")
    res = run(fixtures, "rp2_board.csv", "rp2", str(bad))
    assert res["status"] == "fail"
    assert any(
        "package pin 2: net 'GPIO0' names port pad GPIO0 but the pin table maps pin 2 to GPIO1"
        in e
        for e in res["errors"]
    )


def test_rp2_gpio1_is_not_confused_with_gpio12():
    doc = {
        "components": {"U1": {}},
        "nets": {"GPIO12": [{"ref": "U1", "pin": "9", "pinfunction": None}]},
    }
    res = resolve_pinmap.resolve(doc, "U1", "rp2", [("9", "GPIO1")], confirmed=True)
    assert any(
        "names port pad GPIO12 but the pin table maps pin 9 to GPIO1" in e
        for e in res["errors"]
    )


def test_mimxrt_long_names_with_suffix(fixtures):
    from common import load_port_names

    af = load_port_names("mimxrt", fixtures / "mimxrt_af.csv")
    res = run(
        fixtures, "mimxrt_board.csv", "mimxrt", "mimxrt_pin_table.csv", af_names=af
    )
    assert res["status"] == "ok", res["errors"]
    assert {a["package_pin"]: a["port_name"] for a in res["anchors"]} == {
        "K10": "GPIO_AD_B0_03",
        "L10": "GPIO_AD_B0_04",
        "M10": "GPIO_AD_B1_07",
    }


def test_mimxrt_wrong_table(fixtures, tmp_path):
    bad = tmp_path / "t.csv"
    bad.write_text(
        "package_pin,port_name\nK10,GPIO_AD_B0_04\nL10,GPIO_AD_B0_03\nM10,GPIO_AD_B1_07\n"
        "J10,GPIO_AD_B0_12\nJ11,GPIO_AD_B0_13\n"
    )
    res = run(fixtures, "mimxrt_board.csv", "mimxrt", str(bad))
    assert res["status"] == "fail"
    assert any(
        "package pin K10: net 'GPIO_AD_B0_03' names port pad GPIO_AD_B0_03 but the pin table maps pin K10 to GPIO_AD_B0_04"
        in e
        for e in res["errors"]
    )


def test_bad_table_header(tmp_path, fixtures):
    bad = tmp_path / "t.csv"
    bad.write_text("pin,name\n1,PA0\n")
    errors = []
    assert resolve_pinmap.table_from_csv(bad, errors) == []
    assert errors and "header must be package_pin,port_name" in errors[0]
