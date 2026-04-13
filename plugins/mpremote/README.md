# mpremote

Claude Code plugin for MicroPython device interaction via mpremote.

## Skills

### live-session
Persistent mpremote session using PTY for sending commands and capturing output. This is the **preferred method** for any interaction that involves multiple commands or devices running asyncio. Avoids the Ctrl+C problem that kills asyncio event loops.

### file-transfer
Copying files to and from MicroPython devices. Covers `mpremote fs cp` syntax, directory operations, bulk transfers, and backup patterns.

### device-interaction
General mpremote usage: connecting, running code, checking device state, filesystem inspection, device management. Emphasizes the `resume` subcommand for non-disruptive access.

## Installation

```bash
claude --plugin-dir ~/claude-mpy-marketplace/plugins/mpremote
```

Or add to your Claude Code settings.

## Prerequisites

- mpremote installed (`pip install mpremote`)
- MicroPython device connected via USB serial
- Recommended: mpy-dev for device registry (`uv tool install git+https://gitlab.com/alelec/mpy-dev.git`)
