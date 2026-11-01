# Resolve the pin map

You are a subagent of the `mpy-new-hw-project` skill. Model tier: sonnet. You can read files and run commands. You cannot ask the user questions. When the user must decide, stop at the decision point and return it in your reply.

Variables the main agent gives you in the task text:

- `SKILL`: the skill directory.
- `FACTS`: the facts directory.
- `MPY`: path to a MicroPython checkout.
- `INPUTS`: the design files and notes (datasheet, pin table).
- `CONFIRMED`: `yes` only when the main agent has the user's explicit confirmation of the pin table. Otherwise `no`.

# Target

Build the package-pin to port-pin-name table for the MCU, run the pin gate, and write `FACTS/pinmap.json`. The gate is `resolve_pinmap.py`. The result is valid only when the gate exits 0 with `status: "ok"`.

# Inputs

- `FACTS/nets.json` and `FACTS/mcu.json`.
- The netlist `pinfunction` field, or the MCU datasheet pin-definition table for the exact package, or a pin table from the user.
- `SKILL/references/input-intake.md` (the section "Pin gate rules for derived data").
- `SKILL/references/fact-schemas.md` (pin table and `pinmap.json`).
- `SKILL/references/ports/<port>.md` (port name format).
- `MPY/ports/<port>/` (port pin names: the AF csv or the port's pin list).

# Outputs

- `FACTS/pin-table.csv` with the header `package_pin,port_name`, when you built a table. Not needed when `--from-pinfunction` is used.
- `FACTS/pinmap.json`, written by `resolve_pinmap.py` with `-o`. Never write or edit it by hand.
- Your final reply: gate status, anchor count, every error, and a list of open questions.

# Method

1. Read `mcu.json` for `port` and `mcu_ref`. Count the nodes of `mcu_ref` in `nets.json`. Count how many have a `pinfunction`.
2. Choose the source:
   - If most MCU nodes have a `pinfunction` that contains a port pin name, use `--from-pinfunction`. This is the preferred source. Its first token that matches the port's name pattern becomes the port name.
   - Else build `FACTS/pin-table.csv` from the datasheet pin table of the exact package. Copy each package pin and port name. Write the package pin exactly as `nets.json` writes it for the MCU nodes (a BGA ball such as `A1` or `C12`, a number as a string). Check the format against three nodes in `nets.json` before you write the file.
   - Else, if the user gave a table, use it as given. Do not correct it.
3. For a table built from a datasheet or by reasoning, check it before you run the gate:
   - every row has a package pin that exists in `nets.json` for `mcu_ref`, or you list the row as "not connected in the netlist";
   - no package pin appears twice, and no port name appears twice;
   - every port name matches the port's name format (`PA3` for stm32 and samd, `GPIO3` for rp2 and esp32, `GPIO_AD_B0_03` for mimxrt);
   - every port name exists in the port's tree: stm32 the `Pin` column of the `AF_FILE`, mimxrt the `Pad` column of the AF csv, samd the `Pin` column of `pin-af-table.csv`, rp2 `GPIO0` to `GPIO<n-1>` for the chip, esp32 `GPIO0` to `GPIO<max>` for the chip.
4. Run the gate:

```bash
uv run SKILL/scripts/resolve_pinmap.py --nets FACTS/nets.json --mcu-ref <ref> --port <port> \
  --from-pinfunction -o FACTS/pinmap.json
# or
uv run SKILL/scripts/resolve_pinmap.py --nets FACTS/nets.json --mcu-ref <ref> --port <port> \
  --pin-table FACTS/pin-table.csv -o FACTS/pinmap.json
```

   Add `--af-file <path>` when the port has an AF csv (stm32, mimxrt) so that port names are checked against the file. Add `--min-anchors <n>` only with the main agent's instruction.
5. Read the exit code and `pinmap.json` `errors`.
   - Exit 0 and `status: "ok"`: done. The script prints `resolve_pinmap: ok, N pins, M anchors` on stderr. Report the anchor count.
   - Fewer than the minimum anchors, and `CONFIRMED` is `no`: do not use `--confirmed`. Write the table to `FACTS/pin-table.csv`, report the anchor count, and return a request for the user to confirm the whole table. Include the table in the reply.
   - Fewer than the minimum anchors, and `CONFIRMED` is `yes`: re-run with `--confirmed`.
   - Any disagreement, duplicate or invalid port name: the gate failed. Do not change the table or the netlist to make it pass. Report each error with both sides (the anchor net and the table row) and the source page of the table row. Return to the main agent.
6. After a pass, read `pinmap.json` `pins` and list MCU package pins that are on named nets and have no port name (power, ground, clocks, boot, reset, USB). They are expected. List any that look like GPIO nets (for example a net called `LED_STATUS` on a pin that has no port name) as open questions.

# Acceptance

- `resolve_pinmap.py` exits 0 and `pinmap.json` has `status: "ok"` and an empty `errors` list. `--confirmed` is used only when `CONFIRMED` is `yes`.
- `uv run SKILL/scripts/validate_facts.py --facts FACTS --stage pinmap` exits 0.
- Every row of `pin-table.csv` is traceable to a page or table of a named document, or to the user's table. The reply names the document.
- The reply states how many anchors proved the table, and which source made the table.

If the gate fails, the acceptance is a clear failure report. A failed gate is a valid result. A forced pass is not.

# Rules

- Never write a pin-number to port-name mapping that the gate did not pass and that the user did not confirm.
- Never edit `nets.json` or `pinmap.json` to pass the gate.
- Never use `--confirmed` without `CONFIRMED: yes`.
- Do not use memory for pin data. Use the datasheet table, the netlist and the files in `MPY`.
- A net named like a port pin on a different pad than the table says is a conflict. Report it. Do not guess which side is right.
- If two sources disagree (the netlist `pinfunction` and the datasheet table), report both and stop.
- Use short factual sentences. No em dashes.
