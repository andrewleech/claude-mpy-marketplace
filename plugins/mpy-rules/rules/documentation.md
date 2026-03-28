---
paths:
  - "docs/**/*.rst"
---

# MicroPython Documentation Style

Style guide for RST documentation in the MicroPython docs/ directory,
derived from existing content conventions.

## RST Heading Hierarchy

Use consistent heading markers throughout:

```rst
Top-level title
===============

Section
-------

Subsection
~~~~~~~~~~
```

Top-level titles in library docs use `=` both above and below the title:

```rst
:mod:`machine` -- functions related to the hardware
====================================================
```

## Tone and Voice

- Formal, technical, and concise. No marketing language.
- Use imperative mood for instructions: "Create a new Pin object",
  "Initialise the pin".
- Avoid second person "you". Use passive voice or direct imperatives.
- State facts directly: "Returns the CPU frequency in hertz."
- Do not explain obvious things or add filler.

## API Reference Structure

Library docs in `docs/library/` follow this structure:

1. Module directive with synopsis
2. Module description (1-2 paragraphs)
3. CPython reference via `|see_cpython_module|` substitution
4. Classes section (with `.. toctree::` if multiple classes)
5. For each class:
   - Constructor (`.. class::` directive)
   - Methods (`.. method::` directives, grouped by purpose)
   - Constants (`.. data::` directives)

Method documentation pattern:

```rst
.. method:: Pin.value([value])

   Get or set the digital logic level of the pin:

     - With no argument, return 0 or 1 depending on the logic level of the pin.
     - With ``value`` given, set the logic level of the pin. ``value`` can be
       anything that converts to a boolean.
```

Key conventions:
- Optional parameters in square brackets in the signature
- Description starts with a verb: "Get", "Set", "Return", "Construct"
- Return values stated explicitly: "Returns a bytes object"
- Types in double backticks: ``int``, ``bytes``, ``bool``
- Parameter names in italics: *value*, *timeout_ms*

## Code Examples

- Use `.. code-block:: python3` for Python examples
- Use `.. code-block:: c` for C code, `.. code-block:: bash` for shell
- REPL examples show `>>>` and `...` prompts with output
- Non-REPL code has no prompts
- Include comments explaining what the code does
- Show imports explicitly: `import machine` or `from machine import Pin`

REPL format:

```rst
::

   >>> import machine
   >>> machine.freq()
   160000000
```

Script format:

```rst
.. code-block:: python3

   import network
   nic = network.WLAN(network.STA_IF)
   nic.active(True)
   nic.connect('ssid', 'password')
```

## Cross-References

Use RST roles for internal links:
- `:mod:`machine`` for modules
- `:class:`Pin`` for classes
- `:meth:`Pin.init`` for methods
- `:func:`reset`` for functions
- `:data:`machine.IDLE`` for constants
- `:ref:`label`` for arbitrary cross-references
- `:doc:`/path/to/file`` for document links
- `:term:`MCU`` for glossary terms

Create anchors with `.. _label_name:` before sections that need cross-referencing.

## Informational Directives

- `.. note::` for important additional information
- `.. warning::` for things that could cause problems
- `.. versionadded:: 1.x` for new features
- `.. deprecated:: 1.x` for deprecated features

Use sparingly. Most information belongs in the main text.

## CPython Differences

- Reference CPython equivalents via `|see_cpython_module|` substitution
  at the top of module docs
- Note MicroPython-specific behavior explicitly
- When an API deviates from CPython, state it directly:
  "Unlike CPython, this function does not support..."

## Port-Specific Content

- Use `Availability:` at the end of function/method descriptions to note
  which ports support a feature: "Availability: ESP32, WiPy."
- Port-specific sections use headings, not inline notes
- Hardware-specific parameters documented with their constraints

## Line Length and Formatting

- Wrap prose at natural word boundaries, roughly 80-90 characters
- Multiple sentences on the same line are acceptable
- Continuation lines indent to align with the opening text
- Code blocks use whatever line length is readable
- Lists use `*` or `-` for unordered, numbered with `1.`, `2.`, etc.

## Constants and Data

```rst
.. data:: Pin.IN

   Initialise the pin to input mode.

.. data:: Pin.OUT

   Initialise the pin to output mode.
```

Group related constants together. Provide a one-line description for each.

## Tables

Use grid-style tables with explicit widths when needed:

```rst
.. table::
   :widths: 20 60 20

   +------------+----------------------------+--------+
   | Parameter  | Description                | Type   |
   +============+============================+========+
   | freq       | Clock frequency in Hz      | int    |
   +------------+----------------------------+--------+
```

For simple lists, prefer definition lists or bullet points over tables.
