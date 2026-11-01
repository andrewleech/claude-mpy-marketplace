# mpremote

Plugin for MicroPython device interaction via mpremote, for Claude Code, oh-my-pi and Codex.

## Skills

### live-session
Persistent mpremote session using PTY for sending commands and capturing output. This is the **preferred method** for any interaction that involves multiple commands or devices running asyncio. Avoids the Ctrl+C problem that kills asyncio event loops.

### file-transfer
Copying files to and from MicroPython devices. Covers `mpremote fs cp` syntax, directory operations, bulk transfers, and backup patterns.

### device-interaction
General mpremote usage: connecting, running code, checking device state, filesystem inspection, device management. Emphasizes the `resume` subcommand for non-disruptive access.

## Installation

Install from the `mpy-marketplace` marketplace. See the [repository README](../../README.md) for Claude Code, oh-my-pi and Codex commands, for example `claude plugin install mpremote@mpy-marketplace`.

## Prerequisites

- mpremote installed (`pip install mpremote`)
- MicroPython device connected via USB serial
- Recommended: mpy-dev for device registry (`uv tool install git+https://gitlab.com/alelec/mpy-dev.git`)
