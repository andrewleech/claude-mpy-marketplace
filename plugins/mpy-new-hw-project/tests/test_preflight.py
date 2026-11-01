import json
import subprocess
import sys

import pytest

import preflight

SCRIPTS = [
    "parse_netlist",
    "validate_facts",
    "resolve_pinmap",
    "gen_pins_csv",
    "pick_seed",
    "preflight",
]


def fake_env(monkeypatch, present, network=True, identity=True, usable=True):
    monkeypatch.setattr(
        preflight.shutil, "which", lambda t: f"/usr/bin/{t}" if t in present else None
    )
    monkeypatch.setattr(preflight, "network_reachable", lambda *a, **k: network)
    monkeypatch.setattr(preflight, "container_usable", lambda t: usable)
    monkeypatch.setattr(preflight, "_git_config", lambda k: "x" if identity else "")


def test_all_present(monkeypatch):
    fake_env(monkeypatch, {"uv", "make", "git", "docker", "gh"})
    rep = preflight.check()
    assert rep["ok"] is True and rep["missing"] == []
    assert rep["tools"]["container"] == "docker"


def test_podman_counts_as_container(monkeypatch):
    fake_env(monkeypatch, {"uv", "make", "git", "podman"})
    rep = preflight.check()
    assert rep["ok"] is True
    assert rep["tools"]["container"] == "podman"
    assert any("gh not found" in n for n in rep["notes"])


def test_missing_items_reported(monkeypatch):
    fake_env(monkeypatch, {"git"}, network=False, identity=False)
    rep = preflight.check()
    assert rep["ok"] is False
    assert set(rep["missing"]) == {
        "uv",
        "make",
        "docker or podman",
        "network access to github.com",
        "git identity (user.name and user.email)",
    }
    assert any("build steps are skipped" in n for n in rep["notes"])


def test_unusable_runtime_is_a_note(monkeypatch):
    fake_env(monkeypatch, {"uv", "make", "git", "docker"}, usable=False)
    rep = preflight.check()
    assert rep["ok"] is True
    assert any("docker info" in n for n in rep["notes"])


def test_micropython_dir_check(monkeypatch, tmp_path):
    fake_env(monkeypatch, {"uv", "make", "git", "docker"})
    assert "MicroPython checkout" in preflight.check(tmp_path)["missing"][0]
    (tmp_path / "ports").mkdir()
    (tmp_path / "py").mkdir()
    assert preflight.check(tmp_path)["ok"] is True


def test_main_exit_code(monkeypatch, capsys):
    fake_env(monkeypatch, set())
    assert preflight.main([]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


@pytest.mark.parametrize("script", SCRIPTS)
def test_every_script_has_help(scripts_dir, script):
    r = subprocess.run(
        [sys.executable, str(scripts_dir / f"{script}.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    assert "usage:" in r.stdout
    head = (scripts_dir / f"{script}.py").read_text().splitlines()
    assert "# /// script" in head[:3]
    assert '# requires-python = ">=3.10"' in head[:5]
    assert "# dependencies = []" in head[:6]
