# UI/Theming Reference Notes

The PulseWave CLI theme and rendering updates were informed by the following open-source docs and standards:

- Rich documentation:
  - Console API: https://rich.readthedocs.io/en/latest/reference/console.html
  - Panel API: https://rich.readthedocs.io/en/latest/reference/panel.html
  - Box presets (`SQUARE`, `ROUNDED`, `HEAVY`, `DOUBLE`, etc.): https://rich.readthedocs.io/en/latest/reference/box.html
- CAVA project docs (terminal visualizer behavior and Unicode bar usage):
  - https://github.com/karlstav/cava
  - https://github.com/karlstav/cava/blob/master/TERMINAL.md
- Unicode Block Elements chart (bar glyph families):
  - https://www.unicode.org/charts/nameslist/n_2580.html
- Microsoft terminal VT sequence docs (ANSI SGR color handling):
  - https://learn.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences
- No Color convention (user-controlled color disable):
  - https://no-color.org/

## Implementation Impacts

- Added border presets aligned to common TUI box styles (single/double/rounded/heavy/ascii).
- Added theme-controlled progress glyphs and visualizer level sets.
- Added ANSI style parser with basic/full mode support:
  - named colors + attributes in `basic`
  - 256-color and truecolor in `full`
- Added `NO_COLOR` handling.
- Added UTF fallback behavior for non-UTF terminals.

