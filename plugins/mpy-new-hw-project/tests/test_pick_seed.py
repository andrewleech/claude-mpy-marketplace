import json
import subprocess
import sys
from pathlib import Path

import pytest

import pick_seed

REAL = Path("/home/corona/micropython")


def make_board(root, port, name, files):
    d = root / "ports" / port / "boards" / name
    d.mkdir(parents=True)
    for fname, text in files.items():
        (d / fname).write_text(text if isinstance(text, str) else json.dumps(text))


def stm32(
    root,
    name,
    series,
    cmsis,
    mcu,
    product=None,
    vendor="ST Microelectronics",
    features=None,
):
    info = {"mcu": mcu, "product": product or name, "vendor": vendor}
    if features is not None:
        info["features"] = features
    make_board(
        root, "stm32", name,
        {
            "board.json": info,
            "mpconfigboard.mk": (
                f"MCU_SERIES = {series}\nCMSIS_MCU = {cmsis}\n"
                f"AF_FILE = boards/{cmsis[:-2].lower()}_af.csv\nFROZEN_MANIFEST = $(BOARD_DIR)/manifest.py\n"
            ),
        },
    )  # fmt: skip


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "mp"
    # Alphabetical order puts PYBD and DISC boards ahead of NUCLEO_F767ZI.
    stm32(
        root, "NUCLEO_F767ZI", "f7", "STM32F767xx", "stm32f7", "Nucleo F767ZI",
        features=["Ethernet", "USB"],
    )  # fmt: skip
    stm32(root, "NUCLEO_F746ZG", "f7", "STM32F746xx", "stm32f7", "Nucleo F746ZG")
    stm32(
        root,
        "PYBD_SF6",
        "f7",
        "STM32F767xx",
        "stm32f7",
        "Pyboard D-series SF6",
        "George Robotics",
    )
    stm32(
        root, "ACME_F767_CUSTOM", "f7", "STM32F767xx", "stm32f7", "Acme custom", "Acme"
    )
    stm32(root, "NUCLEO_H743ZI", "h7", "STM32H743xx", "stm32h7", "Nucleo H743ZI")
    stm32(
        root,
        "VCC_GND_H743VI",
        "h7",
        "STM32H743xx",
        "stm32h7",
        "VCC-GND H743VI",
        "VCC-GND",
    )
    stm32(root, "STM32H7A3_X", "h7", "STM32H7A3xxQ", "stm32h7", "H7A3 board")
    stm32(root, "NUCLEO_WB55", "wb", "STM32WB55xx", "stm32wb", "Nucleo WB55")
    (root / "ports" / "stm32" / "boards" / "common_isr_ram").mkdir()  # not a board
    (root / "ports" / "stm32" / "boards" / "deploy.md").write_text("x")

    make_board(
        root, "rp2", "RPI_PICO",
        {
            "board.json": {"mcu": "rp2040", "product": "Pico", "vendor": "Raspberry Pi"},
            "mpconfigboard.cmake": 'set(PICO_BOARD "pico")\nset(PICO_PLATFORM "rp2040")\n',
        },
    )  # fmt: skip
    make_board(
        root, "rp2", "RPI_PICO2",
        {
            "board.json": {"mcu": "rp2350", "product": "Pico 2", "vendor": "Raspberry Pi"},
            "mpconfigboard.cmake": 'set(PICO_BOARD "pico2")\n',
        },
    )  # fmt: skip
    make_board(
        root, "rp2", "ACME_RV",
        {
            "board.json": {"mcu": "rp2350", "product": "Acme RV", "vendor": "Acme"},
            "mpconfigboard.cmake": 'set(PICO_PLATFORM "rp2350-riscv")\n',
        },
    )  # fmt: skip
    make_board(
        root, "rp2", "ACME_350",
        {
            "board.json": {"mcu": "rp2350", "product": "Acme 350", "vendor": "Acme"},
            "mpconfigboard.cmake": 'set(PICO_PLATFORM "rp2350")\n',
        },
    )  # fmt: skip

    esp = root / "ports" / "esp32" / "boards"
    esp.mkdir(parents=True)
    (esp / "mpconfigboard_esp32s3_common.cmake").write_text("set(IDF_TARGET esp32s3)\n")
    (esp / "mpconfigboard_esp32_common.cmake").write_text("set(IDF_TARGET esp32)\n")
    make_board(
        root, "esp32", "ESP32_GENERIC_S3",
        {
            "board.json": {"mcu": "esp32s3", "product": "ESP32-S3", "vendor": "Espressif"},
            "mpconfigboard.cmake": "include(boards/mpconfigboard_esp32s3_common.cmake)\n",
        },
    )  # fmt: skip
    make_board(
        root, "esp32", "SEEED_XIAO_ESP32S3",
        {
            "board.json": {"mcu": "esp32s3", "product": "XIAO ESP32S3", "vendor": "Seeed"},
            "mpconfigboard.cmake": "include(boards/mpconfigboard_esp32s3_common.cmake)\n",
        },
    )  # fmt: skip
    make_board(
        root, "esp32", "ESP32_GENERIC",
        {
            "board.json": {"mcu": "esp32", "product": "ESP32", "vendor": "Espressif"},
            "mpconfigboard.cmake": "include(boards/mpconfigboard_esp32_common.cmake)\n",
        },
    )  # fmt: skip

    def mimx(name, series, variant):
        make_board(
            root, "mimxrt", name,
            {
                "board.json": {"mcu": "mimxrt", "product": name, "vendor": "NXP"},
                "mpconfigboard.mk": f"MCU_SERIES = {series}\nMCU_VARIANT = {variant}\n",
            },
        )  # fmt: skip

    mimx("MIMXRT1060_EVK", "MIMXRT1062", "MIMXRT1062DVJ6A")
    mimx("TEENSY40", "MIMXRT1062", "MIMXRT1062DVJ6A")
    mimx("MIMXRT1062_CUSTOM", "MIMXRT1062", "MIMXRT1062DVL6A")
    mimx("MIMXRT1064_EVK", "MIMXRT1064", "MIMXRT1064DVL6A")

    def samd(name, series, cmsis):
        make_board(
            root, "samd", name,
            {
                "board.json": {"mcu": series.lower(), "product": name, "vendor": "Adafruit"},
                "mpconfigboard.mk": f"MCU_SERIES = {series}\nCMSIS_MCU = {cmsis}\n",
            },
        )  # fmt: skip

    samd("FEATHER_M4", "SAMD51", "SAMD51J19A")
    samd("GENERIC_D51P19", "SAMD51", "SAMD51P19A")
    samd("ITSYBITSY_M0", "SAMD21", "SAMD21G18A")
    return root


def ranked(checkout, port, mcu):
    boards = pick_seed.load_boards(pick_seed.LocalSource(checkout), port)
    ordered, supported = pick_seed.rank(port, mcu, boards)
    return ordered, supported


def names(boards):
    return [b.name for b in boards]


def test_load_boards_reads_identifiers(checkout):
    boards = {
        b.name: b
        for b in pick_seed.load_boards(pick_seed.LocalSource(checkout), "stm32")
    }
    assert "common_isr_ram" not in boards
    b = boards["NUCLEO_F767ZI"]
    assert (b.mcu_series, b.cmsis_mcu, b.af_file) == (
        "f7",
        "STM32F767xx",
        "boards/stm32f767_af.csv",
    )
    assert (b.vendor, b.product, b.board_mcu) == (
        "ST Microelectronics",
        "Nucleo F767ZI",
        "stm32f7",
    )


def test_stm32_exact_first_then_series_then_port(checkout):
    ordered, supported = ranked(checkout, "stm32", "STM32F767ZI")
    assert supported
    assert ordered[0].name == "NUCLEO_F767ZI"
    assert ordered[0].tier == pick_seed.TIER_EXACT
    assert "exact MCU match" in ordered[0].reason and "STM32F767xx" in ordered[0].reason
    tiers = [b.tier for b in ordered]
    assert tiers == sorted(tiers)
    assert set(names(ordered)[:3]) == {"NUCLEO_F767ZI", "PYBD_SF6", "ACME_F767_CUSTOM"}
    assert names(ordered)[3] == "NUCLEO_F746ZG"
    assert ordered[3].tier == pick_seed.TIER_SERIES
    assert ordered[-1].tier == pick_seed.TIER_PORT
    assert [b.rank for b in ordered] == list(range(1, len(ordered) + 1))


def test_stm32_name_containing_part_beats_reference_prefix(checkout):
    ordered, _ = ranked(checkout, "stm32", "STM32H743VI")
    assert names(ordered)[:2] == ["VCC_GND_H743VI", "NUCLEO_H743ZI"]


def test_stm32_two_letter_series_and_part_suffix_variants(checkout):
    ordered, supported = ranked(checkout, "stm32", "stm32wb55rg")
    assert supported and ordered[0].name == "NUCLEO_WB55"
    ordered, _ = ranked(checkout, "stm32", "STM32H7A3ZIT6Q")
    assert ordered[0].name == "STM32H7A3_X" and ordered[0].tier == pick_seed.TIER_EXACT


def test_stm32_series_only_support(checkout):
    ordered, supported = ranked(checkout, "stm32", "STM32F777NI")
    assert supported
    assert all(b.tier != pick_seed.TIER_EXACT for b in ordered)
    assert ordered[0].tier == pick_seed.TIER_SERIES
    assert "MCU_SERIES f7" in ordered[0].reason


def test_stm32_unsupported_series(checkout):
    ordered, supported = ranked(checkout, "stm32", "STM32G474RE")
    assert not supported
    assert {b.tier for b in ordered} == {pick_seed.TIER_PORT}


def test_rp2_platform_from_cmake_or_board_json(checkout):
    ordered, supported = ranked(checkout, "rp2", "RP2350A")
    assert supported
    assert names(ordered) == ["RPI_PICO2", "ACME_350", "ACME_RV", "RPI_PICO"]
    assert [b.tier for b in ordered] == [1, 1, 2, 3]
    assert "RISC-V" in ordered[2].reason
    ordered, _ = ranked(checkout, "rp2", "rp2040")
    assert names(ordered)[0] == "RPI_PICO"


def test_rp2_platform_from_sdk_board_header(tmp_path):
    root = tmp_path / "mp"
    hdr = root / "lib" / "pico-sdk" / "src" / "boards" / "include" / "boards"
    hdr.mkdir(parents=True)
    (hdr / "pico.h").write_text("pico_board_cmake_set(PICO_PLATFORM, rp2040)\n")
    (hdr / "pico2.h").write_text("// x\npico_board_cmake_set(PICO_PLATFORM, rp2350)\n")
    for name, board in (
        ("A_PICO", "pico"),
        ("B_PICO2", "pico2"),
        ("C_NOHDR", "custom"),
    ):
        make_board(
            root, "rp2", name, {"mpconfigboard.cmake": f'set(PICO_BOARD "{board}")\n'}
        )
    make_board(root, "rp2", "D_NONE", {"mpconfigboard.cmake": "# nothing\n"})
    boards = pick_seed.load_boards(pick_seed.LocalSource(root), "rp2")
    plat = {b.name: b.pico_platform for b in boards}
    assert plat == {
        "A_PICO": "rp2040",
        "B_PICO2": "rp2350",
        "C_NOHDR": "",
        "D_NONE": "",
    }
    ordered, supported = pick_seed.rank("rp2", "RP2350A", boards)
    assert supported and ordered[0].name == "B_PICO2" and ordered[0].tier == 1
    ordered, _ = pick_seed.rank("rp2", "RP2040", boards)
    assert ordered[0].name == "A_PICO" and ordered[0].tier == 1
    rest = {b.name: b for b in ordered[1:]}
    assert (
        "custom not available; ranked without PICO_PLATFORM" in rest["C_NOHDR"].reason
    )
    assert rest["C_NOHDR"].tier == pick_seed.TIER_PORT
    assert "no PICO_PLATFORM or PICO_BOARD" in rest["D_NONE"].reason


def test_esp32_follows_cmake_include(checkout):
    ordered, supported = ranked(checkout, "esp32", "ESP32-S3-WROOM-1")
    assert supported
    assert names(ordered) == ["ESP32_GENERIC_S3", "SEEED_XIAO_ESP32S3", "ESP32_GENERIC"]
    assert ordered[0].idf_target == "esp32s3"
    ordered, _ = ranked(checkout, "esp32", "ESP32-WROOM-32E")
    assert ordered[0].name == "ESP32_GENERIC"


def test_esp32_unsupported_chip(checkout):
    _, supported = ranked(checkout, "esp32", "ESP32-C3")
    assert not supported


def test_mimxrt_variant_then_series(checkout):
    ordered, supported = ranked(checkout, "mimxrt", "MIMXRT1062DVJ6A")
    assert supported
    assert names(ordered)[:2] == ["MIMXRT1060_EVK", "TEENSY40"]
    assert ordered[0].tier == 1
    third = ordered[2]
    assert third.name == "MIMXRT1062_CUSTOM" and third.tier == pick_seed.TIER_SERIES
    assert (
        ordered[3].name == "MIMXRT1064_EVK" and ordered[3].tier == pick_seed.TIER_PORT
    )


def test_mimxrt_series_name_and_free_text(checkout):
    for text in ("MIMXRT1062", "i.MX RT1062", "imxrt1062"):
        ordered, _ = ranked(checkout, "mimxrt", text)
        assert {b.name for b in ordered if b.tier == 1} == {
            "MIMXRT1060_EVK", "TEENSY40", "MIMXRT1062_CUSTOM",
        }, text  # fmt: skip


def test_samd_exact_cmsis_then_series(checkout):
    ordered, supported = ranked(checkout, "samd", "ATSAMD51J19A-AU")
    assert supported
    assert names(ordered) == ["FEATHER_M4", "GENERIC_D51P19", "ITSYBITSY_M0"]
    assert [b.tier for b in ordered] == [1, 2, 3]
    ordered, _ = ranked(checkout, "samd", "SAMD51J20A")
    assert ordered[0].name == "FEATHER_M4" and ordered[0].tier == pick_seed.TIER_SERIES


def test_cli_json_and_exit_codes(checkout, capsys):
    rc = pick_seed.main(
        [
            "--micropython",
            str(checkout),
            "--port",
            "stm32",
            "--mcu",
            "STM32F767ZI",
            "--json",
        ]
    )
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["supported"] is True
    assert doc["candidates"][0]["name"] == "NUCLEO_F767ZI"
    assert doc["candidates"][0]["tier"] == "exact"
    assert len(doc["candidates"]) == 8

    rc = pick_seed.main(
        [
            "--micropython",
            str(checkout),
            "--port",
            "stm32",
            "--mcu",
            "STM32G474RE",
            "--json",
        ]
    )
    assert rc == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["supported"] is False
    assert doc["candidates"] == []
    assert "tie" not in doc


def test_unsupported_text_output_has_only_the_message(checkout, capsys):
    rc = pick_seed.main(
        ["--micropython", str(checkout), "--port", "stm32", "--mcu", "STM32G474RE"]
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "has no board for STM32G474RE" in captured.err


def test_tie_at_the_top_tier_lists_features(checkout, capsys):
    pick_seed.main(
        [
            "--micropython",
            str(checkout),
            "--port",
            "stm32",
            "--mcu",
            "STM32F767ZI",
            "--json",
        ]
    )
    doc = json.loads(capsys.readouterr().out)
    assert doc["tie"] is True
    by_name = {c["name"]: c for c in doc["candidates"]}
    assert by_name["NUCLEO_F767ZI"]["features"] == ["Ethernet", "USB"]
    assert "features" not in by_name["NUCLEO_F746ZG"]  # series tier is not tied
    assert "mpconfigboard.h defines" in doc["tie_note"]
    pick_seed.main(
        ["--micropython", str(checkout), "--port", "stm32", "--mcu", "STM32F767ZI"]
    )
    out = capsys.readouterr().out
    assert "features: Ethernet, USB" in out
    assert "features: none listed" in out
    assert "share tier exact" in out


def test_single_best_board_is_not_a_tie(checkout, capsys):
    pick_seed.main(
        [
            "--micropython",
            str(checkout),
            "--port",
            "samd",
            "--mcu",
            "SAMD51J19A",
            "--json",
        ]
    )
    doc = json.loads(capsys.readouterr().out)
    assert "tie" not in doc
    assert all("features" not in c for c in doc["candidates"])


def test_cli_limit_and_list(checkout, capsys):
    pick_seed.main(
        ["--micropython", str(checkout), "--port", "stm32", "--mcu", "STM32F767ZI",
         "--limit", "2", "--json"]
    )  # fmt: skip
    assert len(json.loads(capsys.readouterr().out)["candidates"]) == 2
    rc = pick_seed.main(["--micropython", str(checkout), "--port", "stm32", "--list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "port stm32: 8 boards" in out and "ACME_F767_CUSTOM" in out


def test_cli_text_output_has_reason(checkout, capsys):
    pick_seed.main(
        ["--micropython", str(checkout), "--port", "samd", "--mcu", "SAMD51J19A"]
    )
    out = capsys.readouterr().out
    assert "1. FEATHER_M4" in out
    assert "exact: exact MCU match: CMSIS_MCU SAMD51J19A" in out


def test_cli_requires_mcu_or_list(checkout):
    with pytest.raises(SystemExit) as e:
        pick_seed.main(["--micropython", str(checkout), "--port", "stm32"])
    assert e.value.code == 2


def test_missing_port_dir(tmp_path, capsys):
    (tmp_path / "ports").mkdir()
    rc = pick_seed.main(["--micropython", str(tmp_path), "--port", "stm32", "--list"])
    assert rc == 1
    assert "does not exist" in capsys.readouterr().err


def test_parse_mk_ignores_recipes_and_comments():
    text = (
        "MCU_SERIES = f7  # series\nCMSIS_MCU ?= STM32F767xx\n"
        "deploy: $(BUILD)/firmware.bin\n\t$(ECHO) MCU_VARIANT = x\nOTHER = 1\n"
    )
    assert pick_seed.parse_mk(text) == {"MCU_SERIES": "f7", "CMSIS_MCU": "STM32F767xx"}


def test_parse_cmake_set_forms():
    class Src:
        def read(self, port, rel):
            return None

    v = pick_seed.parse_cmake(
        'set(PICO_PLATFORM "rp2350")\nset( IDF_TARGET  esp32c3 )\n', "rp2", Src()
    )
    assert v == {"PICO_PLATFORM": "rp2350", "IDF_TARGET": "esp32c3"}


def test_remote_source_uses_tree_listing_and_raw_files(monkeypatch):
    tree = {
        "truncated": False,
        "tree": [
            {"path": "ports/rp2/boards/RPI_PICO/board.json", "type": "blob"},
            {"path": "ports/rp2/boards/RPI_PICO/mpconfigboard.cmake", "type": "blob"},
            {"path": "ports/rp2/boards/RPI_PICO/pins.csv", "type": "blob"},
            {"path": "ports/rp2/boards/deploy.md", "type": "blob"},
            {"path": "ports/stm32/boards/X/board.json", "type": "blob"},
            {"path": "ports/rp2/boards", "type": "tree"},
        ],
    }
    files = {
        "ports/rp2/boards/RPI_PICO/board.json": json.dumps(
            {"mcu": "rp2040", "product": "Pico", "vendor": "RPi"}
        ),
        "ports/rp2/boards/RPI_PICO/mpconfigboard.cmake": 'set(PICO_PLATFORM "rp2040")\n',
    }
    src = pick_seed.RemoteSource("master")
    monkeypatch.setattr(pick_seed.shutil, "which", lambda _: None)

    class Resp:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.data

    def fake_urlopen(req, timeout=0):
        url = req if isinstance(req, str) else req.full_url
        if url.startswith(
            "https://api.github.com/repos/micropython/micropython/git/trees/master"
        ):
            return Resp(json.dumps(tree).encode())
        prefix = "https://raw.githubusercontent.com/micropython/micropython/master/"
        assert url.startswith(prefix), url
        return Resp(files[url[len(prefix) :]].encode())

    monkeypatch.setattr(pick_seed.urllib.request, "urlopen", fake_urlopen)
    assert src.boards("rp2") == ["RPI_PICO"]
    boards = pick_seed.load_boards(src, "rp2")
    assert boards[0].pico_platform == "rp2040" and boards[0].vendor == "RPi"


@pytest.mark.skipif(
    not (REAL / "ports" / "stm32" / "boards").is_dir(), reason="no MicroPython checkout"
)
def test_real_checkout_stm32_f767():
    boards = pick_seed.load_boards(pick_seed.LocalSource(REAL), "stm32")
    ordered, supported = pick_seed.rank("stm32", "STM32F767ZI", boards)
    assert supported
    assert ordered[0].name == "NUCLEO_F767ZI"
    assert (ordered[0].mcu_series, ordered[0].cmsis_mcu) == ("f7", "STM32F767xx")
    assert ordered[0].af_file == "boards/stm32f767_af.csv"


@pytest.mark.skipif(
    not (REAL / "ports" / "rp2" / "boards").is_dir(), reason="no MicroPython checkout"
)
def test_real_checkout_other_ports():
    src = pick_seed.LocalSource(REAL)
    for port, mcu, first_tier in (
        ("rp2", "RP2040", 1),
        ("esp32", "ESP32-S3", 1),
        ("mimxrt", "MIMXRT1062DVJ6A", 1),
        ("samd", "SAMD21G18A", 1),
    ):
        ordered, supported = pick_seed.rank(port, mcu, pick_seed.load_boards(src, port))
        assert supported and ordered[0].tier == first_tier, port


@pytest.mark.skipif(
    not (
        REAL / "lib" / "pico-sdk" / "src" / "boards" / "include" / "boards" / "pico2.h"
    ).is_file(),
    reason="no pico-sdk in MicroPython checkout",
)
def test_real_checkout_rp2_pico_vs_pico2():
    boards = {
        b.name: b for b in pick_seed.load_boards(pick_seed.LocalSource(REAL), "rp2")
    }
    assert boards["RPI_PICO2"].pico_platform == "rp2350"
    assert boards["RPI_PICO"].pico_platform == "rp2040"


def test_help_runs_as_script(scripts_dir):
    r = subprocess.run(
        [sys.executable, str(scripts_dir / "pick_seed.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and "--remote" in r.stdout
