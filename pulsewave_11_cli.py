"""Console script shim for PulseWave-11 packaging."""

from __future__ import annotations

from importlib import import_module


def main() -> int:
    cli_main = import_module("pulsewave-11.cli").main
    return int(cli_main())


if __name__ == "__main__":
    raise SystemExit(main())
