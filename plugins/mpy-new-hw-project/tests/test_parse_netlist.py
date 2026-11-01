import json
import subprocess
import sys

import pytest

import common
import parse_netlist

KICAD = "stm32_board_kicad.net"
PROTEL = "stm32_board_protel.net"
CSV = "stm32_board.csv"


def parse(fixtures, name, fmt="auto"):
    return parse_netlist.parse_file(fixtures / name, fmt)


@pytest.mark.parametrize(
    "name,fmt", [(KICAD, "kicad"), (PROTEL, "protel"), (CSV, "csv")]
)
def test_auto_detects_format(fixtures, name, fmt):
    assert parse(fixtures, name)["format"] == fmt


def test_kicad_components_and_nets(fixtures):
    doc = parse(fixtures, KICAD)
    assert doc["components"]["U1"] == {
        "value": "STM32F767ZIT6",
        "footprint": "Package_QFP:LQFP-144_20x20mm_P0.5mm",
    }
    assert "/PA4" in doc["nets"]
    assert "/power/3V3_SENSE" in doc["nets"]
    assert doc["nets"]["PA3"] == [
        {"ref": "U1", "pin": "34", "pinfunction": "PA3"},
        {"ref": "J1", "pin": "1", "pinfunction": None},
    ]


def test_protel_components_and_nets(fixtures):
    doc = parse(fixtures, PROTEL)
    assert doc["components"]["U1"] == {
        "value": "STM32F767ZIT6",
        "footprint": "LQFP-144",
    }
    assert doc["nets"]["PA3"] == [
        {"ref": "U1", "pin": "34", "pinfunction": None},
        {"ref": "J1", "pin": "1", "pinfunction": None},
    ]
    assert "NetR5_1" in doc["nets"]


def test_protel_splits_on_last_hyphen():
    text = "[\nU-1\nFP\nVAL\n]\n(\nSIG\nU-1-A3\n)\n"
    doc = parse_netlist.parse_protel(text)
    assert doc["nets"]["SIG"] == [{"ref": "U-1", "pin": "A3", "pinfunction": None}]


def test_csv_pinfunction(fixtures):
    doc = parse(fixtures, CSV)
    mcu_nodes = [n for nodes in doc["nets"].values() for n in nodes if n["ref"] == "U1"]
    assert {n["pinfunction"] for n in mcu_nodes if n["pin"] == "34"} == {"PA3"}
    assert doc["nets"]["LED_GREEN"][1] == {"ref": "R1", "pin": "1", "pinfunction": None}


def test_formats_agree_on_mcu_pin_to_net(fixtures):
    def pin_nets(doc):
        return {
            n["pin"]: common.strip_sheet(net)
            for net, nodes in doc["nets"].items()
            for n in nodes
            if n["ref"] == "U1"
        }

    kicad, protel, csv = (parse(fixtures, n) for n in (KICAD, PROTEL, CSV))
    assert pin_nets(kicad)["34"] == "PA3"
    # KiCad names the unnamed net Net-(R5-Pad1); Protel names it NetR5_1.
    k, p = pin_nets(kicad), pin_nets(protel)
    assert {a: b for a, b in k.items() if a != "100"} == {
        a: b for a, b in p.items() if a != "100"
    }
    assert {a: b for a, b in pin_nets(csv).items() if a != "100"} == {
        a: b for a, b in p.items() if a != "100"
    }


def test_kicad_quoted_escapes():
    tree = parse_netlist.parse_sexpr(r'(a "x \"y\" z" b)')
    assert tree == [["a", 'x "y" z', "b"]]


def test_kicad_unbalanced_raises():
    with pytest.raises(parse_netlist.NetlistError):
        parse_netlist.parse_sexpr("(export (nets)")


def test_csv_missing_column(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("ref,pin\nU1,1\n")
    with pytest.raises(parse_netlist.NetlistError, match="net"):
        parse_netlist.parse_file(f)


def test_unknown_format_fails(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("hello\n")
    with pytest.raises(parse_netlist.NetlistError, match="detect"):
        parse_netlist.parse_file(f)


def test_main_writes_json(fixtures, tmp_path):
    out = tmp_path / "nets.json"
    assert parse_netlist.main([str(fixtures / KICAD), "-o", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["format"] == "kicad"
    assert set(doc) == {"format", "components", "nets"}


def test_main_bad_file_exit_1(tmp_path, capsys):
    f = tmp_path / "bad.net"
    f.write_text("(export (nets")
    assert parse_netlist.main([str(f)]) == 1
    assert "unbalanced" in capsys.readouterr().err


def test_help_runs_as_script(scripts_dir):
    r = subprocess.run(
        [sys.executable, str(scripts_dir / "parse_netlist.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "--format" in r.stdout
