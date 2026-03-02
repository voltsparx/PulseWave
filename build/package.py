from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def prepare_staging(root: Path) -> Path:
    source_pkg = root / "pulsewave-11"
    if not source_pkg.exists():
        raise FileNotFoundError(f"Missing package directory: {source_pkg}")

    staging_root = root / "build" / ".staging"
    cleanup_staging_root(staging_root)
    staging_dir = staging_root / f"run-{int(time.time() * 1000)}"
    staging_dir.mkdir(parents=True, exist_ok=True)

    shutil.copytree(source_pkg, staging_dir / "pulsewave_11")
    (staging_dir / "pulsewave_11_cli.py").write_text(
        "from pulsewave_11.cli import main\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf-8",
    )
    return staging_dir


def safe_delete(path: Path) -> None:
    if not path.exists():
        return
    last_exc: OSError | None = None
    for _ in range(6):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return
        except OSError as exc:
            last_exc = exc
            time.sleep(0.4)
    if last_exc is not None:
        raise last_exc


def cleanup_staging_root(staging_root: Path) -> None:
    if not staging_root.exists():
        return
    for child in staging_root.iterdir():
        if not child.name.startswith("run-"):
            continue
        try:
            safe_delete(child)
        except OSError:
            # Keep going; stale locked dirs will be retried on next run.
            continue
    try:
        if not any(staging_root.iterdir()):
            safe_delete(staging_root)
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Build PulseWave-11 single binary with PyInstaller")
    parser.add_argument("--with-native", action="store_true", help="Attempt building Cython native module first")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    spec = root / "build" / "pulsewave-11.spec"

    if args.with_native:
        setup_py = root / "native" / "bindings" / "setup.py"
        if setup_py.exists():
            run([sys.executable, str(setup_py), "build_ext", "--inplace"], cwd=root)
        else:
            print("native/bindings/setup.py not found; skipping native build.")

    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")

    staging_dir = prepare_staging(root)
    env["PULSEWAVE11_STAGING"] = str(staging_dir)
    try:
        safe_delete(root / "dist" / ("pulsewave-11.exe" if os.name == "nt" else "pulsewave-11"))
    except OSError:
        pass
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)]
    print("+", " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=str(root), check=True, env=env)
    finally:
        try:
            safe_delete(staging_dir)
        except OSError:
            pass

    print(f"Built binary at: {root / 'dist' / ('pulsewave-11.exe' if os.name == 'nt' else 'pulsewave-11')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
