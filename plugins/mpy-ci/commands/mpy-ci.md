---
name: mpy-ci
description: Run MicroPython CI pipeline locally using Docker
argument-hint: "[target ...]"
allowed-tools: ["Bash", "Read"]
---

Run the MicroPython local CI pipeline. Use the arguments as CI targets.

Parse the user's input for target names. Valid targets include:
- Port builds: `stm32`, `unix`, `unix-qemu`, `esp32`, `esp8266`, `rp2`, `qemu`, `cc3200`, `mimxrt`, `nrf`, `powerpc`, `renesas`, `samd`, `alif`, `webassembly`, `windows`, `zephyr`
- Code checks: `format`, `codespell`, `ruff`, `biome`, `docs`, `examples`, `mpy-format`, `mpremote`
- Meta targets: `all-checks`, `all`

If no targets are specified, default to `all-checks`.

If `ci/ci-local.sh` does not exist in the current directory, inform the user they need to install it first:
```bash
mkdir -p ci/
cp ${CLAUDE_PLUGIN_ROOT}/skills/mpy-ci/scripts/ci-local.sh ci/ci-local.sh
cp ${CLAUDE_PLUGIN_ROOT}/skills/mpy-ci/assets/Dockerfile ci/Dockerfile
chmod +x ci/ci-local.sh
```

Execute:

```bash
./ci/ci-local.sh <TARGETS>
```

Present the output to the user. If a target fails, show the relevant error output and suggest fixes.
