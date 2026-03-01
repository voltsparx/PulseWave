from __future__ import annotations

import argparse
from pathlib import Path

from pulsewave.app import PulseWaveApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pulsewave", description="PulseWave retro CLI music player")
    parser.add_argument("--config", type=Path, help="Path to config JSON file")
    parser.add_argument("--theme", type=str, help="Theme override")
    parser.add_argument("--color-mode", choices=["off", "basic", "full"], help="Color rendering mode")
    parser.add_argument("--scan-only", action="store_true", help="Index library and exit")
    parser.add_argument("--play", type=str, help="Local file path to play immediately")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    app = PulseWaveApp(
        config_path=args.config,
        theme_override=args.theme,
        color_mode_override=args.color_mode,
    )

    if args.scan_only:
        app.bootstrap()
        print(app.state.status_message)
        return 0

    if args.play:
        app.handle_input(f'add "{args.play}"')

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

