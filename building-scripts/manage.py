#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

APP_NAME = "pulsewave-11"
CONFIG_POINTER_FILE = Path.home() / ".pulsewave-11-config-location"
DEFAULT_CONFIG_HOME = Path.home() / ".pulsewave-11-config"
INSTALL_RECORD = Path.home() / ".pulsewave-11-install.json"
PROFILE_BLOCK_BEGIN = "# >>> pulsewave-11 path >>>"
PROFILE_BLOCK_END = "# <<< pulsewave-11 path <<<"

ROOT = Path(__file__).resolve().parents[1]
REQ_FILE = ROOT / "requirements.txt"
PACKAGE_SCRIPT = ROOT / "build" / "package.py"


class ScriptError(RuntimeError):
    pass


@dataclass
class InstallState:
    app: str
    platform: str
    bin_dir: str
    binary_path: str
    path_managed: bool
    installed_at_utc: str
    version: str = ""
    binary_sha256: str = ""


def _binary_name() -> str:
    return f"{APP_NAME}.exe" if os.name == "nt" else APP_NAME


def _dist_binary() -> Path:
    return ROOT / "dist" / _binary_name()


def _normalize_path(path: Path) -> str:
    value = str(path.expanduser().resolve())
    return value.lower() if os.name == "nt" else value


def _default_bin_dir() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return (Path(local_app_data) / "Programs" / "PulseWave11" / "bin").resolve()
        return (Path.home() / "AppData" / "Local" / "Programs" / "PulseWave11" / "bin").resolve()
    return (Path.home() / ".local" / "bin").resolve()


def _run(cmd: Sequence[str], *, cwd: Path | None = None) -> None:
    printable = " ".join(str(part) for part in cmd)
    print(f"+ {printable}")
    subprocess.run(list(cmd), cwd=str(cwd) if cwd else None, check=True)


def _run_check(cmd: Sequence[str], *, cwd: Path | None = None) -> bool:
    result = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _nuitka_info(python_exe: str) -> tuple[bool, str]:
    result = subprocess.run(
        [python_exe, "-m", "nuitka", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        line = result.stdout.strip().splitlines()
        return True, (line[0] if line else "unknown")
    err = result.stderr.strip() or result.stdout.strip() or "not installed"
    return False, err


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _app_version() -> str:
    init_file = ROOT / "pulsewave-11" / "__init__.py"
    if not init_file.exists():
        return ""
    text = init_file.read_text(encoding="utf-8")
    marker = '__version__ = "'
    idx = text.find(marker)
    if idx < 0:
        return ""
    start = idx + len(marker)
    end = text.find('"', start)
    if end < 0:
        return ""
    return text[start:end]


def _sync_repo(*, remote: str, branch: str | None) -> None:
    if not (ROOT / ".git").exists():
        raise ScriptError(f"Repository metadata not found at {ROOT / '.git'}")
    if not _command_exists("git"):
        raise ScriptError("Git is not available on PATH.")
    cmd = ["git", "pull", "--ff-only", remote]
    if branch:
        cmd.append(branch)
    _run(cmd, cwd=ROOT)


def _ensure_requirements(python_exe: str) -> None:
    if not REQ_FILE.exists():
        raise ScriptError(f"Missing requirements file: {REQ_FILE}")
    if not _run_check([python_exe, "-m", "pip", "--version"], cwd=ROOT):
        print("pip not found for selected Python. Bootstrapping pip via ensurepip...")
        if not _run_check([python_exe, "-m", "ensurepip", "--upgrade"], cwd=ROOT):
            raise ScriptError(
                "pip is unavailable and could not be bootstrapped with ensurepip. "
                "Install/repair Python pip support and retry."
            )
    print(f"Installing Python dependencies from {REQ_FILE} ...")
    _run([python_exe, "-m", "pip", "install", "-r", str(REQ_FILE)], cwd=ROOT)


def _build_binary(python_exe: str, with_native: bool) -> Path:
    if not PACKAGE_SCRIPT.exists():
        raise ScriptError(f"Packaging script not found: {PACKAGE_SCRIPT}")
    cmd = [python_exe, str(PACKAGE_SCRIPT)]
    if with_native:
        cmd.append("--with-native")
    _run(cmd, cwd=ROOT)
    built = _dist_binary()
    if not built.exists():
        raise ScriptError(f"Build completed but binary not found: {built}")
    return built


def _copy_binary(source: Path, destination: Path, *, force: bool) -> None:
    if not source.exists():
        raise ScriptError(f"Source binary not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        raise ScriptError(
            f"Binary already exists at {destination}. Use `upgrade` or `--force`."
        )

    tmp_target = destination.with_name(destination.name + ".tmp")
    shutil.copy2(source, tmp_target)
    if os.name != "nt":
        current_mode = tmp_target.stat().st_mode
        tmp_target.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    _replace_with_retry(tmp_target, destination)


def _replace_with_retry(source: Path, destination: Path) -> None:
    last_exc: OSError | None = None
    for _ in range(8):
        try:
            source.replace(destination)
            return
        except OSError as exc:
            last_exc = exc
            time.sleep(0.25)
    try:
        source.unlink(missing_ok=True)
    except OSError:
        pass
    if last_exc is not None:
        raise ScriptError(
            f"Could not replace binary at {destination}. "
            "If it is running, close it and retry."
        ) from last_exc


def _unlink_with_retry(path: Path) -> bool:
    if not path.exists():
        return False
    last_exc: OSError | None = None
    for _ in range(8):
        try:
            path.unlink()
            return True
        except OSError as exc:
            last_exc = exc
            time.sleep(0.25)
    if last_exc is not None:
        raise ScriptError(
            f"Could not remove binary at {path}. "
            "If it is running, close it and retry."
        ) from last_exc
    return False


def _load_install_state() -> InstallState | None:
    if not INSTALL_RECORD.exists():
        return None
    try:
        raw = json.loads(INSTALL_RECORD.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    required = {"app", "platform", "bin_dir", "binary_path", "path_managed", "installed_at_utc"}
    if not required.issubset(raw):
        return None
    return InstallState(
        app=str(raw["app"]),
        platform=str(raw["platform"]),
        bin_dir=str(raw["bin_dir"]),
        binary_path=str(raw["binary_path"]),
        path_managed=bool(raw["path_managed"]),
        installed_at_utc=str(raw["installed_at_utc"]),
        version=str(raw.get("version", "")),
        binary_sha256=str(raw.get("binary_sha256", "")),
    )


def _save_install_state(state: InstallState) -> None:
    INSTALL_RECORD.write_text(json.dumps(asdict(state), indent=2) + "\n", encoding="utf-8")


def _remove_install_state() -> None:
    try:
        INSTALL_RECORD.unlink()
    except FileNotFoundError:
        return


def _unix_profile_file() -> Path:
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return Path.home() / ".zshrc"
    if "bash" in shell:
        return Path.home() / ".bashrc"
    return Path.home() / ".profile"


def _strip_profile_block(text: str) -> str:
    start = text.find(PROFILE_BLOCK_BEGIN)
    while start != -1:
        end = text.find(PROFILE_BLOCK_END, start)
        if end == -1:
            text = text[:start]
            break
        end_line = text.find("\n", end)
        if end_line == -1:
            end_line = len(text)
        else:
            end_line += 1
        text = text[:start] + text[end_line:]
        start = text.find(PROFILE_BLOCK_BEGIN)
    return text


def _ensure_path_on_unix(bin_dir: Path) -> bool:
    profile = _unix_profile_file()
    original = profile.read_text(encoding="utf-8") if profile.exists() else ""
    cleaned = _strip_profile_block(original).rstrip()
    block = (
        f"{PROFILE_BLOCK_BEGIN}\n"
        f'export PATH="{bin_dir}:$PATH"\n'
        f"{PROFILE_BLOCK_END}\n"
    )
    updated = f"{cleaned}\n\n{block}" if cleaned else block
    if updated == original:
        return False
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(updated, encoding="utf-8")
    return True


def _remove_path_on_unix() -> bool:
    profile = _unix_profile_file()
    if not profile.exists():
        return False
    original = profile.read_text(encoding="utf-8")
    updated = _strip_profile_block(original)
    if updated == original:
        return False
    profile.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return True


def _ensure_path_on_windows(bin_dir: Path) -> bool:
    import winreg  # type: ignore

    key_path = r"Environment"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current = ""
        entries = [entry for entry in str(current).split(";") if entry]
        normalized_entries = {_normalize_path(Path(item)) for item in entries}
        target = _normalize_path(bin_dir)
        if target in normalized_entries:
            return False
        entries.append(str(bin_dir))
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(entries))
    _broadcast_path_change_windows()
    return True


def _remove_path_on_windows(bin_dir: Path) -> bool:
    import winreg  # type: ignore

    key_path = r"Environment"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        try:
            current, _ = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            return False
        entries = [entry for entry in str(current).split(";") if entry]
        target = _normalize_path(bin_dir)
        kept = [item for item in entries if _normalize_path(Path(item)) != target]
        if len(kept) == len(entries):
            return False
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(kept))
    _broadcast_path_change_windows()
    return True


def _broadcast_path_change_windows() -> None:
    try:
        import ctypes

        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(  # type: ignore[attr-defined]
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            1000,
            None,
        )
    except Exception:
        pass


def _ensure_path(bin_dir: Path) -> bool:
    if os.name == "nt":
        return _ensure_path_on_windows(bin_dir)
    return _ensure_path_on_unix(bin_dir)


def _remove_path(bin_dir: Path) -> bool:
    if os.name == "nt":
        return _remove_path_on_windows(bin_dir)
    return _remove_path_on_unix()


def _cleanup_empty_dir(path: Path) -> None:
    try:
        if path.exists() and path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        return


def _is_safe_to_remove(path: Path) -> bool:
    expanded = path.expanduser()
    if expanded == Path.home():
        return False
    if os.name == "nt":
        return len(expanded.parts) > 1
    return expanded != Path("/")


def cmd_test(args: argparse.Namespace) -> int:
    _ensure_requirements(args.python)
    binary = _build_binary(args.python, with_native=args.with_native)
    if args.smoke:
        _run([str(binary), "--version"], cwd=ROOT)
    digest = _sha256_file(binary)
    print(f"Test binary ready: {binary}")
    print(f"SHA256: {digest}")
    return 0


def _install_or_upgrade(args: argparse.Namespace, *, upgrade_mode: bool) -> int:
    existing = _load_install_state()
    bin_dir = Path(args.bin_dir).expanduser().resolve() if args.bin_dir else None
    if bin_dir is None:
        if upgrade_mode and existing is not None:
            bin_dir = Path(existing.bin_dir).expanduser().resolve()
        else:
            bin_dir = _default_bin_dir()

    _ensure_requirements(args.python)
    if not args.skip_build:
        source_binary = _build_binary(args.python, with_native=args.with_native)
    else:
        source_binary = _dist_binary()
        if not source_binary.exists():
            raise ScriptError(f"`--skip-build` set but binary does not exist: {source_binary}")

    destination = bin_dir / _binary_name()
    force_write = bool(args.force or upgrade_mode)
    if upgrade_mode and not destination.exists():
        raise ScriptError(f"No installed binary found at {destination}. Run install first.")

    backup: Path | None = None
    if upgrade_mode and destination.exists():
        backup = destination.with_name(destination.name + ".bak")
        shutil.copy2(destination, backup)

    try:
        _copy_binary(source_binary, destination, force=force_write)
    except Exception:
        if backup is not None and backup.exists():
            _replace_with_retry(backup, destination)
            print(f"Upgrade failed. Rolled back previous binary at: {destination}")
        raise
    finally:
        if backup is not None and backup.exists():
            try:
                backup.unlink()
            except OSError:
                pass

    path_changed = False
    if not args.no_path:
        path_changed = _ensure_path(bin_dir)

    binary_hash = _sha256_file(destination)
    state = InstallState(
        app=APP_NAME,
        platform=platform.platform(),
        bin_dir=str(bin_dir),
        binary_path=str(destination),
        path_managed=not args.no_path,
        installed_at_utc=datetime.now(timezone.utc).isoformat(),
        version=_app_version(),
        binary_sha256=binary_hash,
    )
    _save_install_state(state)

    action = "Upgraded" if upgrade_mode else "Installed"
    print(f"{action} binary: {destination}")
    print(f"SHA256: {binary_hash}")
    if path_changed:
        print("PATH updated for new shells.")
    elif not args.no_path:
        print("PATH already contained install directory.")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    return _install_or_upgrade(args, upgrade_mode=False)


def cmd_upgrade(args: argparse.Namespace) -> int:
    return _install_or_upgrade(args, upgrade_mode=True)


def cmd_update(args: argparse.Namespace) -> int:
    if args.sync_repo:
        _sync_repo(remote=args.remote, branch=args.branch)
    existing = _load_install_state()
    return _install_or_upgrade(args, upgrade_mode=existing is not None)


def cmd_uninstall(args: argparse.Namespace) -> int:
    state = _load_install_state()
    bin_dir = Path(args.bin_dir).expanduser().resolve() if args.bin_dir else None
    if bin_dir is None and state is not None:
        bin_dir = Path(state.bin_dir).expanduser().resolve()
    if bin_dir is None:
        bin_dir = _default_bin_dir()

    binary = bin_dir / _binary_name()
    removed_binary = _unlink_with_retry(binary)

    removed_path = False
    if not args.keep_path:
        removed_path = _remove_path(bin_dir)

    if removed_binary:
        print(f"Removed binary: {binary}")
    else:
        print(f"Binary not found (already removed): {binary}")

    if removed_path:
        print("Removed PATH entry from profile/user environment.")
    elif not args.keep_path:
        print("No managed PATH entry found.")

    _cleanup_empty_dir(bin_dir)

    if args.purge_config:
        config_home = DEFAULT_CONFIG_HOME
        if CONFIG_POINTER_FILE.exists():
            raw = CONFIG_POINTER_FILE.read_text(encoding="utf-8").strip()
            if raw:
                config_home = Path(raw).expanduser()
        if config_home.exists() and config_home.is_dir() and _is_safe_to_remove(config_home):
            shutil.rmtree(config_home)
            print(f"Removed config directory: {config_home}")
        try:
            CONFIG_POINTER_FILE.unlink()
        except FileNotFoundError:
            pass

    _remove_install_state()
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    state = _load_install_state()
    dist_binary = _dist_binary()
    install_binary = Path(state.binary_path).expanduser() if state else None
    nuitka_available, nuitka_detail = _nuitka_info(args.python)
    payload = {
        "app": APP_NAME,
        "version": _app_version(),
        "platform": platform.platform(),
        "python_executable": args.python,
        "python_version": sys.version.split()[0],
        "nuitka_available": nuitka_available,
        "nuitka_detail": nuitka_detail,
        "requirements_file_exists": REQ_FILE.exists(),
        "package_script_exists": PACKAGE_SCRIPT.exists(),
        "dist_binary_exists": dist_binary.exists(),
        "dist_binary_sha256": _sha256_file(dist_binary) if dist_binary.exists() else "",
        "git_available": _command_exists("git"),
        "vc_cl_available": _command_exists("cl"),
        "clang_available": _command_exists("clang"),
        "install_state": asdict(state) if state else None,
        "installed_binary_exists": bool(install_binary and install_binary.exists()),
        "installed_binary_sha256": _sha256_file(install_binary) if install_binary and install_binary.exists() else "",
    }
    print(json.dumps(payload, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pulsewave-11-build",
        description="Cross-platform PulseWave-11 build/install manager",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    test_p = sub.add_parser("test", help="Build binary in repo dist/ for testing")
    test_p.add_argument("--python", default=sys.executable, help="Python executable to use")
    test_p.add_argument("--with-native", action="store_true", help="Try building native extension before packaging")
    test_p.add_argument("--smoke", action="store_true", help="Run built binary with --version after build")
    test_p.set_defaults(func=cmd_test)

    install_p = sub.add_parser("install", help="Install binary into local/custom bin and add PATH")
    install_p.add_argument("--python", default=sys.executable, help="Python executable to use")
    install_p.add_argument("--with-native", action="store_true", help="Try building native extension before packaging")
    install_p.add_argument("--bin-dir", help="Custom install bin directory")
    install_p.add_argument("--skip-build", action="store_true", help="Use existing dist binary")
    install_p.add_argument("--no-path", action="store_true", help="Do not add install directory to PATH")
    install_p.add_argument("--force", action="store_true", help="Overwrite existing installed binary")
    install_p.set_defaults(func=cmd_install)

    upgrade_p = sub.add_parser("upgrade", help="Upgrade existing installed binary in place")
    upgrade_p.add_argument("--python", default=sys.executable, help="Python executable to use")
    upgrade_p.add_argument("--with-native", action="store_true", help="Try building native extension before packaging")
    upgrade_p.add_argument("--bin-dir", help="Custom install bin directory (overrides stored state)")
    upgrade_p.add_argument("--skip-build", action="store_true", help="Use existing dist binary")
    upgrade_p.add_argument("--no-path", action="store_true", help="Do not modify PATH during upgrade")
    upgrade_p.add_argument("--force", action="store_true", help="Force overwrite")
    upgrade_p.set_defaults(func=cmd_upgrade)

    update_p = sub.add_parser("update", help="Update source (optional) and install/upgrade binary")
    update_p.add_argument("--python", default=sys.executable, help="Python executable to use")
    update_p.add_argument("--with-native", action="store_true", help="Try building native extension before packaging")
    update_p.add_argument("--bin-dir", help="Custom install bin directory")
    update_p.add_argument("--skip-build", action="store_true", help="Use existing dist binary")
    update_p.add_argument("--no-path", action="store_true", help="Do not modify PATH during update")
    update_p.add_argument("--force", action="store_true", help="Force overwrite")
    update_p.add_argument("--sync-repo", action="store_true", help="Run git pull --ff-only before build")
    update_p.add_argument("--remote", default="origin", help="Git remote for --sync-repo")
    update_p.add_argument("--branch", help="Optional branch for --sync-repo")
    update_p.set_defaults(func=cmd_update)

    uninstall_p = sub.add_parser("uninstall", help="Uninstall binary and cleanup PATH entry")
    uninstall_p.add_argument("--bin-dir", help="Custom install bin directory")
    uninstall_p.add_argument("--keep-path", action="store_true", help="Do not edit PATH/profile")
    uninstall_p.add_argument(
        "--purge-config",
        action="store_true",
        help="Also delete PulseWave-11 config directory and pointer file",
    )
    uninstall_p.set_defaults(func=cmd_uninstall)

    doctor_p = sub.add_parser("doctor", help="Print environment/build/install diagnostics")
    doctor_p.add_argument("--python", default=sys.executable, help="Python executable to inspect")
    doctor_p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ScriptError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: command failed with exit code {exc.returncode}", file=sys.stderr)
        return int(exc.returncode or 1)
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"ERROR: unexpected failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
