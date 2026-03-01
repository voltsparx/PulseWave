#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT}/build/out"

cmake -S "${ROOT}/build" -B "${BUILD_DIR}"
cmake --build "${BUILD_DIR}" --config Release

echo "Native core built in ${BUILD_DIR}"

