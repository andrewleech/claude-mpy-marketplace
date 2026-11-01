---
name: mpy-new-hw-project
description: Create a new MicroPython project for custom hardware
argument-hint: "[design files or description] [--port stm32|rp2|esp32|mimxrt|samd]"
allowed-tools: ["Bash", "Read", "Write", "Edit", "Glob", "Grep", "Task"]
---

Create a new MicroPython project for the user's custom hardware.

Use the `mpy-new-hw-project` skill and follow its pipeline. Treat the arguments as the design inputs: file paths (netlist, BOM, pin table, datasheets), a short hardware description, or a port name. If an input is missing, ask the user for it.
