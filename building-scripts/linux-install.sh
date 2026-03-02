#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

run_manage() {
  "${PYTHON_BIN}" "${SCRIPT_DIR}/manage.py" "$@"
}

ask_yes_no() {
  local prompt="$1"
  local default="$2"
  local answer
  while true; do
    read -r -p "${prompt} " answer
    answer="${answer:-$default}"
    case "${answer}" in
      y|Y|yes|YES) return 0 ;;
      n|N|no|NO) return 1 ;;
      *) echo "Please answer y or n." ;;
    esac
  done
}

if [[ $# -gt 0 ]]; then
  run_manage "$@"
  exit $?
fi

echo "PulseWave-11 Linux Setup"
echo "1) test"
echo "2) install"
echo "3) upgrade"
echo "4) update"
echo "5) uninstall"
echo "6) doctor"
read -r -p "Choose an option [1-6]: " choice

case "${choice}" in
  1)
    args=(test)
    if ask_yes_no "Build with native extension? [y/N]" "n"; then
      args+=(--with-native)
    fi
    run_manage "${args[@]}"
    ;;
  2)
    args=(install)
    echo "Install location:"
    echo "1) local bin (default: ~/.local/bin)"
    echo "2) custom location"
    read -r -p "Choose [1-2]: " loc_choice
    if [[ "${loc_choice}" == "2" ]]; then
      read -r -p "Enter custom bin directory: " custom_bin
      if [[ -z "${custom_bin}" ]]; then
        echo "Custom bin directory cannot be empty."
        exit 1
      fi
      args+=(--bin-dir "${custom_bin}")
    fi
    if ! ask_yes_no "Add install directory to PATH? [Y/n]" "y"; then
      args+=(--no-path)
    fi
    if ask_yes_no "Build with native extension? [y/N]" "n"; then
      args+=(--with-native)
    fi
    if ask_yes_no "Skip build and use existing dist binary? [y/N]" "n"; then
      args+=(--skip-build)
    fi
    run_manage "${args[@]}"
    ;;
  3)
    args=(upgrade)
    if ask_yes_no "Use custom bin directory override? [y/N]" "n"; then
      read -r -p "Enter custom bin directory: " custom_bin
      if [[ -z "${custom_bin}" ]]; then
        echo "Custom bin directory cannot be empty."
        exit 1
      fi
      args+=(--bin-dir "${custom_bin}")
    fi
    if ! ask_yes_no "Update PATH during upgrade? [Y/n]" "y"; then
      args+=(--no-path)
    fi
    if ask_yes_no "Build with native extension? [y/N]" "n"; then
      args+=(--with-native)
    fi
    if ask_yes_no "Skip build and use existing dist binary? [y/N]" "n"; then
      args+=(--skip-build)
    fi
    run_manage "${args[@]}"
    ;;
  4)
    args=(update)
    if ask_yes_no "Sync repo with git pull before update? [y/N]" "n"; then
      args+=(--sync-repo)
      read -r -p "Git remote [origin]: " git_remote
      git_remote="${git_remote:-origin}"
      args+=(--remote "${git_remote}")
      read -r -p "Git branch (optional, blank for default): " git_branch
      if [[ -n "${git_branch}" ]]; then
        args+=(--branch "${git_branch}")
      fi
    fi
    echo "Install location:"
    echo "1) existing/default location"
    echo "2) custom location"
    read -r -p "Choose [1-2]: " loc_choice
    if [[ "${loc_choice}" == "2" ]]; then
      read -r -p "Enter custom bin directory: " custom_bin
      if [[ -z "${custom_bin}" ]]; then
        echo "Custom bin directory cannot be empty."
        exit 1
      fi
      args+=(--bin-dir "${custom_bin}")
    fi
    if ! ask_yes_no "Update PATH during update? [Y/n]" "y"; then
      args+=(--no-path)
    fi
    if ask_yes_no "Build with native extension? [y/N]" "n"; then
      args+=(--with-native)
    fi
    if ask_yes_no "Skip build and use existing dist binary? [y/N]" "n"; then
      args+=(--skip-build)
    fi
    run_manage "${args[@]}"
    ;;
  5)
    args=(uninstall)
    if ask_yes_no "Use custom bin directory? [y/N]" "n"; then
      read -r -p "Enter custom bin directory: " custom_bin
      if [[ -z "${custom_bin}" ]]; then
        echo "Custom bin directory cannot be empty."
        exit 1
      fi
      args+=(--bin-dir "${custom_bin}")
    fi
    if ask_yes_no "Keep PATH unchanged? [y/N]" "n"; then
      args+=(--keep-path)
    fi
    if ask_yes_no "Purge config directory too? [y/N]" "n"; then
      args+=(--purge-config)
    fi
    run_manage "${args[@]}"
    ;;
  6)
    run_manage doctor
    ;;
  *)
    echo "Invalid option: ${choice}"
    exit 1
    ;;
esac
