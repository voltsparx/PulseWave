# PulseWave

Minimal retro CLI music player blueprint implemented as a modular hybrid architecture:
- Python for orchestration, UI, search, config.
- Cython bridge stub for native bindings.
- C++ core skeleton for playback and DSP expansion.

## Reverse-Engineering Inputs Used

From `temp/cava`:
- Visualizer pipeline shape: samples -> energy bins -> normalization -> bar levels.
- Raw bar-oriented output model suited for terminal rendering.

From `temp/Tusic`:
- Separation of concerns between API/search, resolver, player, and event loop.
- Reliable strategy for stream URL resolution via `yt-dlp`.
- Local persistence and queue-first playback behavior.

## Current MVP

- Modular package layout matching `blueprint.txt`.
- Queue manager with repeat/shuffle behaviors.
- Local file scanning and fuzzy search.
- Optional YouTube Music search and stream resolve (`ytmusicapi` + `yt-dlp`).
- GUI-like retro panel renderer + ASCII visualizer fallback.
- Configurable theme and keybinding model.
- Native/Cython scaffolding aligned to future low-latency engine work.

## Project Structure

```text
pulsewave/
  core/           # state, queue, player, search, config
  ui/             # renderer, components, themes, keybinds, visualizer
  integrations/   # local scanner, ytmusic wrapper
  utils/          # logger, helpers
native/
  audio/          # audio engine + decoder skeleton
  dsp/            # FFT + visualizer skeleton
  bindings/       # Cython bridge stub
themes/           # default, amber, green, ice
build/            # CMake build entry
```

## Run

```bash
python -m pulsewave
```

Optional flags:

```bash
python -m pulsewave --scan-only
python -m pulsewave --theme amber --color-mode basic
python -m pulsewave --play "/path/to/song.mp3"
```

## Commands in App

- `search <query>`
- `play <search-index>`
- `add <local-path>`
- `next`, `prev`, `seek <seconds>`, `volume <0-100>`
- `repeat off|one|all`
- `shuffle on|off`
- `theme <name>`
- `help`, `status`, `quit`

## Themes

Built in:
- `default`
- `blackwhite`
- `amber`
- `green`
- `ice`
- `neon_city`

Theme files:
- `black_white`
- `graphite`
- `sunset_tape`

Examples:

```bash
python -m pulsewave --theme black_white --color-mode basic
python -m pulsewave --theme neon_city --color-mode full
```

`NO_COLOR=1` disables ANSI colors regardless of theme.

## Native Build (Skeleton)

```bash
cmake -S build -B build/out
cmake --build build/out
```

## Notes

- If `python-mpv` is available, backend auto-selects MPV.
- Without it, PulseWave uses a simulated backend to keep UI/architecture testable.
