# Reverse Engineering Notes

## Inputs Audited

- `temp/cava`
- `temp/Tusic`

`blueprint.txt` references `cmus/mpv/ncmpcpp`, but those folders are not present in `temp/` in this workspace. Actual available references were used instead.

## What Was Adopted

1. CAVA-inspired visualizer method:
   - Chunk waveform samples into fixed bins.
   - Compute RMS energy per bin.
   - Normalize against peak.
   - Convert into terminal bar levels (`▁▂▃▄▅▆▇█`).
   - Add smoothing to prevent flicker.

2. Tusic-inspired architecture boundaries:
   - Dedicated search/integration layer (`core/search.py`, `integrations/*`).
   - Playback abstraction (`core/player.py`) detached from UI.
   - Stream resolving separated from UI logic.
   - Event loop only orchestrates actions and state rendering.

3. Robustness upgrades beyond references:
   - Config manager with defaults + merge strategy.
   - Queue manager with explicit repeat/shuffle semantics.
   - Backend fallback if optional dependencies are missing.
   - Native bridge and C++ stubs for future performance path.

