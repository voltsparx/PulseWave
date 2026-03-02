from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .app import PulseWave11App
from .core.player import PlaybackController
from .ui.themes import ThemeManager
from .utils.paths import config_home, initialize_config_home


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pulsewave-11", description="PulseWave-11 retro CLI music player")
    parser.add_argument("--config", type=Path, help="Path to config JSON file")
    parser.add_argument("--theme", type=str, help="Theme override")
    parser.add_argument("--color-mode", choices=["off", "basic", "full"], help="Color rendering mode")
    parser.add_argument("--backend", choices=PlaybackController.available_backends(), help="Audio backend override")
    parser.add_argument("--scan-only", action="store_true", help="Index library and exit")
    parser.add_argument("--play", type=str, help="Local file path to play immediately")
    parser.add_argument("--version", action="version", version=f"pulsewave-11 {__version__}")
    parser.add_argument("--list-themes", action="store_true", help="List installed themes and exit")
    parser.add_argument("--show-config-home", action="store_true", help="Print config home path and exit")
    parser.add_argument("--doctor", action="store_true", help="Print backend/runtime diagnostics and exit")
    parser.add_argument(
        "-C",
        "--command",
        action="append",
        default=[],
        help="Execute command (can be repeated), then exit",
    )
    parser.add_argument(
        "--stdin-commands",
        action="store_true",
        help="Read commands from stdin (one per line), execute, then exit",
    )
    parser.add_argument(
        "--print-status",
        action="store_true",
        help="Print final status message after non-interactive command execution",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        selected_config_home = initialize_config_home()
    except OSError as exc:
        print(f"Config setup failed: {exc}", file=sys.stderr)
        return 2

    if args.show_config_home:
        print(str(selected_config_home))
        return 0

    if args.list_themes:
        manager = ThemeManager(Path.cwd() / "themes")
        print("\n".join(manager.available_themes()))
        return 0

    if args.doctor:
        payload = {
            "version": __version__,
            "config_home": str(config_home()),
            "available_backends": PlaybackController.available_backends(),
            "backend_capabilities": PlaybackController.backend_capabilities(),
            "platform": __import__("platform").platform(),
            "python": __import__("sys").version.split()[0],
        }
        print(json.dumps(payload, indent=2))
        return 0

    app = PulseWave11App(
        config_path=args.config,
        theme_override=args.theme,
        color_mode_override=args.color_mode,
        backend_override=args.backend,
    )

    if args.scan_only:
        app.bootstrap()
        print(app.state.status_message)
        return 0

    if args.play:
        app.handle_input(f'add "{args.play}"')

    scripted_commands: list[str] = list(args.command or [])
    if args.stdin_commands:
        for line in sys.stdin:
            cmd = line.strip()
            if cmd:
                scripted_commands.append(cmd)
    if scripted_commands:
        app.bootstrap()
        for command in scripted_commands:
            app.handle_input(command)
            if app._should_quit:
                break
        if args.print_status or app.state.last_error:
            payload = app.state.last_error if app.state.last_error else app.state.status_message
            print(payload)
        return 0 if not app.state.last_error else 1

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
