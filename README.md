# 🎵 PulseWave-11 (v1.0.0)

PulseWave-11 is a keyboard-first retro CLI music player with a GUI-like terminal interface.

👤 Author: `voltsparx`  
📬 Contact: `voltsparx@gmail.com`

## ✨ At a Glance

- 🐍 Python-first orchestration for UI, search, playlists, settings
- ⚙️ Optional Cython + C++ acceleration for performance-critical paths
- 🎛️ CLI that feels like a GUI: panels, themes, visualizer, runtime settings
- 🔁 Live responsive layout: split/stacked/compact + real-time terminal resize reflow
- 🧠 Built using reverse-engineering insights from open-source tools (`cmus`, `ncmpcpp`, `mpv`)
- 🧩 Extensible by design: plugins, snapshots, scripting, and optional LAN streaming

## 🧠 Open-Source Reverse Engineering Basis

This project was built by reverse-engineering architecture and UX patterns from open-source CLI media tools (notably `cmus`, `ncmpcpp`, and `mpv`) and adapting those ideas into a new Python + C++ hybrid implementation.

No source code was copied directly; reverse engineering was used for methods, interaction models, and robustness patterns.

## 🚀 Quick Start

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run:

```bash
python -m pulsewave-11
# or, after install
pulsewave-11
```

## ✅ Verification Status (March 3, 2026)

Verified in this repository state:

- `python -m pytest -q` -> `35 passed`
- `python -m compileall -q pulsewave-11 tests building-scripts native/bindings` -> passed
- `python -m pulsewave-11 --version` -> `pulsewave-11 1.0.0`
- `python -m pulsewave-11 --doctor` -> passed

Note:

- Optional runtime backends can depend on local machine setup (`native`, `mpv`).

## 🧾 First-Run Config Setup

On first launch, PulseWave-11 asks where to create the config directory.

- Default config dir: `~/.pulsewave-11-config/`
- Pointer file: `~/.pulsewave-11-config-location`
- Override env var: `PULSEWAVE_11_CONFIG_HOME=/custom/path`

Config contents:

- `config.json`
- `library.json`
- `logs/pulsewave-11.log`
- `cache/`

## 🕹️ How To Use Properly

Recommended first-time flow:

1. Launch:

```bash
python -m pulsewave-11
```

2. Configure music folders and scan:

```text
settings show
settings set music_dirs /path/to/Music,/path/to/MoreMusic
scan
```

3. Search and play:

```text
search your song or artist
play 1
```

4. Manage playlists while listening:

```text
playlist create Favorites
like
playlist add Favorites current
playlist load Favorites
```

5. Add shortcut aliases:

```text
alias set chill search lo-fi && play 1
chill
```

6. Review events/errors:

```text
events show 10
events clear
```

7. Save/restore a full session snapshot:

```text
snapshot save focus-session
snapshot list
snapshot load focus-session
```

8. Automate command flows with script files:

```text
script run ./automation/playlist_bootstrap.pw11
```

9. Automate non-interactive runs:

```bash
pulsewave-11 -C "search lofi" -C "play 1" --print-status
cat commands.txt | pulsewave-11 --stdin-commands --print-status
```

Operational tips:

- Run `backends` in-app or `pulsewave-11 --doctor` for diagnostics.
- Use `settings set ui.event_log_size <n>` to tune event history size.
- Resize your terminal anytime; layout reflows live.
- Use `vizpreset chars <levels>` and `vizpreset save <name>` to build/save custom ASCII visual styles.
- Start LAN streaming with `lanstream start [port]` and share `playlist.m3u` on your local network.
- Use `plugins reload` after adding/removing plugin files in your plugins directory.

### 🖥️ Windows vs Linux/macOS Examples

Windows PowerShell:

```powershell
# Run directly from source
python -m pulsewave-11

# Interactive installer menu
powershell -ExecutionPolicy Bypass -File .\building-scripts\windows-install.ps1

# Non-interactive install to custom bin
python .\building-scripts\manage.py install --bin-dir "$HOME\AppData\Local\Programs\PulseWave11\bin"

# Command automation from file
Get-Content .\commands.txt | python -m pulsewave-11 --stdin-commands --print-status

# Custom config home
$env:PULSEWAVE_11_CONFIG_HOME="C:\music\pulsewave-11-config"
python -m pulsewave-11
```

Linux/macOS:

```bash
# Run directly from source
python3 -m pulsewave-11

# Interactive installer menu
bash ./building-scripts/linux-install.sh

# Non-interactive install to custom bin
python3 ./building-scripts/manage.py install --bin-dir ~/.local/bin

# Command automation from file
cat commands.txt | python3 -m pulsewave-11 --stdin-commands --print-status

# Custom config home
export PULSEWAVE_11_CONFIG_HOME="$HOME/.config/pulsewave-11"
python3 -m pulsewave-11
```

## 🌟 Core Features

- Queue, repeat, shuffle
- Play/pause/next/previous/seek/volume/speed controls
- Search across local + YouTube Music integration paths
- Playlist + category model
- Runtime settings panel in the interface
- Theme system with monochrome and color themes
- Responsive layout with live resize reflow
- Quick-search and raw command mode with completion/history
- Sleep timer, session persistence, recently played
- Keybinding action chains (`action1|action2|action3`)
- Command aliases/macros with argument forwarding and chaining
- In-app event log with bounded history
- Visualizer preset editor (`vizpreset`) with custom ASCII level strings
- Smart metadata cache for ASCII art thumbnails and synced `.lrc` lyrics
- Plugin API and runtime plugin manager commands
- Session snapshots for queue/playlist/visualizer restoration
- Script runner with `sleep`/`wait` directives for automation
- Performance metrics panel (CPU/RAM/frame time)
- Optional LAN HTTP playlist/audio streaming
- Signal metrics (RMS/Peak/Crest), Python fallback + optional native acceleration

## ⌨️ Keyboard Controls

| Key | Action |
|---|---|
| `Space` | Play/Pause |
| `n` / `p` | Next / Previous |
| `+` / `-` | Volume up/down |
| `]` / `[` | Seek forward/backward |
| `m` | Mute toggle |
| `.` / `;` | Speed up/down |
| `x` / `z` | Cycle repeat / toggle shuffle |
| `t` / `g` / `f` | Theme / color mode / visualizer mode |
| `,` | Toggle settings panel |
| `j` / `k` / `l` / `u` | Settings navigation and adjust |
| `:` | Raw command mode (`Tab` completion, arrow history) |
| `q` | Quit |

## 🧪 CLI Flags

```bash
pulsewave-11 --version
pulsewave-11 --doctor
pulsewave-11 --show-config-home
pulsewave-11 --list-themes
pulsewave-11 --backend native
pulsewave-11 --theme black_white --color-mode basic
pulsewave-11 --scan-only
pulsewave-11 --play "/path/to/song.mp3"
pulsewave-11 -C "settings"
pulsewave-11 -C "search lofi" -C "play 1" --print-status
cat commands.txt | pulsewave-11 --stdin-commands --print-status
```

## 💬 In-App Commands

Playback and control:

- `search <query>`
- `play <search-index|current|next|prev|path>`
- `add <local-path>`
- `seek <seconds>`
- `volume <0-100>`
- `speed <0.5-2.0>`
- `repeat off|one|all`
- `shuffle on|off`
- `sleep <minutes|off>`
- `theme <name>`
- `alias list|set|delete`
- `events show [count]|clear`
- `vizpreset list|save|load|delete|chars`
- `lyrics show|on|off`
- `metadata show|refresh`
- `plugins list|reload`
- `snapshot list|save|load|delete`
- `script run <path>`
- `perf on|off|status`
- `lanstream start [port]|stop|status`
- `status`, `keymap`, `help`, `quit`

Library and settings:

- `settings [show|hide|get|set ...]`
- `category list|add|use`
- `playlist list|create|add|load|show|use|delete|rename`
- `like`
- `scan`
- `backends`
- `config-home`

Plugin notes:

- Plugin directory: `<config-home>/plugins`
- Hook names currently supported:
  - `on_app_start(app)`
  - `on_tick(app)`
  - `on_track_change(app, track)`
  - `on_command(app, parts)`

## 🎨 Themes

Included themes:

- `default`
- `blackwhite`
- `black_white`
- `amber`
- `green`
- `ice`
- `graphite`
- `neon_city`
- `sunset_tape`

Set `NO_COLOR=1` to disable ANSI colors.

## 🏛️ Architecture

Main app controllers:

- `InputController`: raw/line input, key handling, command entry UX
- `CommandController`: command/action dispatch
- `LibrarySettingsController`: settings/category/playlist runtime logic
- `PlaybackRuntimeController`: playback lifecycle, queue transitions, runtime controls

Native acceleration path:

- Cython module: `pulsewave_11_native`
- Optional native visualizer bins via `compute_fft_bins`
- Python fallback always available when native extension is missing

## 📦 Build and Package

Build native extension first (optional, enables hybrid path):

```bash
python native/bindings/setup.py build_ext --inplace
```

Build single-file binary with Nuitka:

```bash
python build/package.py
python build/package.py --with-native
python build/package.py --debug-nuitka
```

Wrapper scripts:

```bash
bash build/package.sh
powershell -ExecutionPolicy Bypass -File build/package.ps1
```

Output:

- `dist/pulsewave-11.exe` on Windows
- `dist/pulsewave-11` on Linux/macOS

## 🧰 Cross-Platform Install / Upgrade / Uninstall

Directory: `building-scripts/`

Interactive wrappers:

- Linux/macOS: `building-scripts/linux-install.sh`
- Windows: `building-scripts/windows-install.ps1`

Each wrapper provides:

- `test`
- `install`
- `upgrade`
- `update` (optional `git pull --ff-only` + install/upgrade)
- `uninstall`
- `doctor`
- Auto dependency install for `test/install/upgrade/update` from `requirements.txt` (with `ensurepip` fallback)

Default install location (when `--bin-dir` is not set):

- Linux/macOS: `~/.local/bin`
- Windows: `%LOCALAPPDATA%\Programs\PulseWave11\bin`

Non-interactive examples:

```bash
python building-scripts/manage.py test --with-native
python building-scripts/manage.py install --bin-dir ~/.local/bin
python building-scripts/manage.py upgrade --skip-build
python building-scripts/manage.py update --sync-repo --remote origin
python building-scripts/manage.py uninstall --purge-config
python building-scripts/manage.py doctor
```

## 🪟 Build Prerequisites

Nuitka build requirements:

- Windows: Microsoft Visual C++ 14.0+ Build Tools
- Linux/macOS: working C toolchain (`gcc`/`clang`) and Python development headers

Native extension (`--with-native`) also uses the same compiler toolchain.

## 🧪 Development Checks

```bash
python -m compileall -q pulsewave-11 tests native/bindings
python -m pytest -q
python -m pulsewave-11 --doctor
```

## 🧹 Repository Hygiene

The repo ignores generated artifacts (dist, staging, build outputs, extension binaries, caches). Source of truth:

- `pulsewave-11/`
- `native/`
- `themes/`
- `build/`
- `building-scripts/`
