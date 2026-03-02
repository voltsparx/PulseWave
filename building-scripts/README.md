# Build Script Layout

`manage.py` is the shared cross-platform engine.

Packaging backend:

- `build/package.py` builds the distributable binary with Nuitka (`--onefile`).

Interactive entrypoints (menu with `test/install/upgrade/update/uninstall/doctor`):

- Linux/macOS:
  - `linux-install.sh`
- Windows PowerShell:
  - `windows-install.ps1`

Default install target when `--bin-dir` is not provided:

- Linux/macOS: `~/.local/bin`
- Windows: `%LOCALAPPDATA%\Programs\PulseWave11\bin`

Each wrapper also supports non-interactive passthrough:

- `linux-install.sh install --bin-dir /custom/bin`
- `windows-install.ps1 install --bin-dir C:\custom\bin`
- `linux-install.sh update --sync-repo --remote origin`
- `windows-install.ps1 doctor`

`doctor` also reports Nuitka availability/version for the selected Python interpreter.

Dependency behavior:

- `test`, `install`, `upgrade`, and `update` automatically run:
  - `python -m pip install -r requirements.txt`
- If `pip` is missing for the selected Python interpreter, the manager attempts:
  - `python -m ensurepip --upgrade`
